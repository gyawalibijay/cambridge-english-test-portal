"""Read-only dashboard projections. No demo scores or wall-clock practice time."""
from collections import defaultdict
from datetime import timedelta
from math import isfinite

from django.urls import reverse
from django.utils import timezone

from attempts.models import StudentResponse


SKILLS = ("speaking", "listening", "reading", "writing")


def _minutes(seconds):
    minutes = int(seconds // 60)
    return f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes} min"


def _mean(values):
    return round(sum(values) / len(values)) if values else None


def build_reference_dashboard(user, score_for_response, level_for_response):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    rows = list(StudentResponse.objects.filter(
        attempt_question__attempt__user=user
    ).exclude(attempt_question__attempt__status="cancelled").select_related(
        "attempt_question__question", "attempt_question__part",
        "attempt_question__attempt__mock_test"
    ).order_by("created_at", "pk"))
    groups = defaultdict(list)
    response_scores = {}
    activity = {}
    days = set()
    seconds_today = seconds_week = seconds_total = 0.0
    count_today = 0
    for response in rows:
        aq = response.attempt_question
        skill = str(aq.question.skill).lower()
        if skill not in SKILLS:
            continue
        day = timezone.localtime(response.created_at).date()
        days.add(day)
        raw_seconds = float(response.duration_seconds or 0)
        seconds = max(0, raw_seconds) if isfinite(raw_seconds) else 0
        seconds_total += seconds
        if day == today:
            seconds_today += seconds
            count_today += 1
        if week_start <= day <= today:
            seconds_week += seconds
        feedback = response.ai_feedback if isinstance(response.ai_feedback, dict) else {}
        invalid = feedback.get("status") in ("no_speech", "invalid_audio", "blank_audio")
        score = 0 if invalid else score_for_response(response)
        response_scores[response.pk] = score
        level = None if invalid else level_for_response(response)
        groups[skill].append({"day": day, "score": score, "level": level,
                              "mistake": response.is_correct is False})
        key = (aq.attempt_id, skill, aq.part_id)
        item = activity.setdefault(key, {
            "key": skill, "label": f"{skill.title()} Part {aq.part.order}",
            "date": response.created_at, "scores": [], "count": 0,
            "url": reverse("results:attempt_report", args=[aq.attempt_id]),
        })
        item["date"] = max(item["date"], response.created_at)
        item["count"] += 1
        if score is not None:
            item["scores"].append(score)
    streak = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    calendar = [{"label": (week_start + timedelta(days=i)).strftime("%a")[0],
                 "date": week_start + timedelta(days=i),
                 "active": week_start + timedelta(days=i) in days,
                 "today": week_start + timedelta(days=i) == today} for i in range(7)]
    skills = []
    for skill in SKILLS:
        records = groups[skill]
        scores = [r["score"] for r in records if r["score"] is not None]
        recent = [r["score"] for r in records if r["score"] is not None and week_start <= r["day"] <= today]
        previous = [r["score"] for r in records if r["score"] is not None and week_start - timedelta(days=7) <= r["day"] < week_start]
        delta = _mean(recent) - _mean(previous) if recent and previous else None
        levels = [r["level"] for r in records if r["level"]]
        count = sum(r["day"] == today for r in records)
        skills.append({"key": skill, "label": skill.title(), "today": count,
                       "goal": 10, "goal_pct": min(100, count * 10),
                       "score": _mean(scores), "level": levels[-1] if levels else None,
                       "trend": "Improving" if delta is not None and delta > 0 else "Stable" if delta == 0 else None,
                       "delta": delta, "best": max(scores) if scores else None,
                       "mistakes": sum(r["mistake"] for r in records),
                       "url": reverse("student_practice_skill", args=[skill])})
    scored_skills = [s for s in skills if s["score"] is not None]
    focus = min(scored_skills, key=lambda s: s["score"]) if scored_skills else skills[0]
    events = sorted(activity.values(), key=lambda x: x["date"], reverse=True)
    for event in events:
        event["score"] = _mean(event.pop("scores"))
    best = max((e for e in events if e["score"] is not None),
               key=lambda e: e["score"], default=None)
    # Only genuinely full four-skill attempts qualify as mock results.
    attempt_skills = defaultdict(set)
    for aq_attempt, skill, _part in activity:
        attempt_skills[aq_attempt].add(skill)
    full_ids = {pk for pk, present in attempt_skills.items() if present == set(SKILLS)}
    last_mock = next((r.attempt_question.attempt for r in reversed(rows)
                      if r.attempt_question.attempt_id in full_ids and
                      r.attempt_question.attempt.status == "completed"), None)
    mock_result = None
    if last_mock:
        mock_scores = [response_scores.get(r.pk) for r in rows if r.attempt_question.attempt_id == last_mock.pk]
        mock_result = {"date": last_mock.completed_at, "score": _mean([s for s in mock_scores if s is not None]),
                       "url": reverse("results:attempt_report", args=[last_mock.pk])}
    return {"reference": {"today": today, "skills": skills, "focus": focus,
            "readiness": _mean([s["score"] for s in scored_skills]),
            "questions": count_today, "question_goal": 40,
            "goal_pct": min(100, round(count_today / 40 * 100)),
            "remaining": max(0, 40 - count_today), "streak": streak, "calendar": calendar,
            "minutes_today": int(seconds_today // 60), "time_pct": min(100, round(seconds_today / 1800 * 100)),
            "time_today": _minutes(seconds_today), "time_week": _minutes(seconds_week), "time_total": _minutes(seconds_total),
            "minutes_remaining": max(0, 30 - int(seconds_today // 60)),
            "best": best, "activity": events[:5], "mistakes": sum(s["mistakes"] for s in skills),
            "mock": mock_result}}
