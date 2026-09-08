"""Cambridge Full Mock Part 3: scoring, results, history, review-state and QA."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import StudentResponse, TestAttempt
from .full_mock_v35_part2 import is_continuous_full_mock

VERSION = "35.2"
META_KEY = "full_mock_v35_part3"
SKILL_ORDER = ("reading", "listening", "speaking", "writing")
OBJECTIVE_TYPES = {"single_choice", "multiple_choice", "short_answer", "gap_fill", "ordering"}
SUBJECTIVE_TYPES = {"long_text", "recorded_response", "read_aloud", "interview_response"}
TERMINAL_REVIEW = {
    StudentResponse.ReviewStatus.AUTO_GRADED,
    StudentResponse.ReviewStatus.AI_GRADED,
    StudentResponse.ReviewStatus.REVIEWED,
}


def _d(value, default=None):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _q(value):
    value = _d(value, Decimal("0"))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp(value, low, high):
    value = _d(value, low)
    return min(high, max(low, value))


def _feedback(response):
    value = getattr(response, "ai_feedback", None)
    return value if isinstance(value, dict) else {}


def _timed_out(response):
    data = getattr(response, "answer_data", None)
    return bool(isinstance(data, dict) and data.get("timed_out"))


def _point_score(response):
    """Return earned points on AttemptQuestion.points scale, or None if not scorable yet."""
    item = response.attempt_question
    points = _d(item.points, Decimal("0")) or Decimal("0")
    if points < 0:
        points = Decimal("0")

    if _timed_out(response):
        return Decimal("0")

    # Human evaluator always owns the final point score when present.
    if response.evaluator_score is not None:
        return _q(_clamp(response.evaluator_score, Decimal("0"), points))

    question = item.question
    skill = str(getattr(question, "skill", "") or "").lower()
    qtype = str(getattr(question, "question_type", "") or "").lower()
    feedback = _feedback(response)

    if skill == "speaking":
        # Speaking V3 stores AI score as a percentage but also stores a point
        # equivalent in JSON. Prefer that explicit conversion.
        explicit = _d(feedback.get("points_equivalent"))
        if explicit is not None:
            return _q(_clamp(explicit, Decimal("0"), points))

        percent = _d(feedback.get("score_total"))
        if percent is None:
            percent = _d(feedback.get("overall_score"))
        if percent is None and response.review_status == StudentResponse.ReviewStatus.AI_GRADED:
            percent = _d(response.ai_score)
        if percent is not None:
            percent = _clamp(percent, Decimal("0"), Decimal("100"))
            return _q(points * percent / Decimal("100"))

        return None

    if skill == "writing":
        # Current Writing task already stores scaled point values in ai_score/final_score.
        for value in (response.final_score, response.ai_score, response.auto_score):
            score = _d(value)
            if score is not None:
                return _q(_clamp(score, Decimal("0"), points))
        # Compatibility fallback if an older writing response only kept 0-100 in JSON.
        percent = _d(feedback.get("score_total"))
        if percent is not None:
            percent = _clamp(percent, Decimal("0"), Decimal("100"))
            return _q(points * percent / Decimal("100"))
        return None

    # Reading/Listening objective responses are already point based.
    if qtype in OBJECTIVE_TYPES or skill in {"reading", "listening"}:
        for value in (response.final_score, response.auto_score, response.evaluator_score):
            score = _d(value)
            if score is not None:
                return _q(_clamp(score, Decimal("0"), points))
        return None

    for value in (response.final_score, response.ai_score, response.auto_score):
        score = _d(value)
        if score is not None:
            return _q(_clamp(score, Decimal("0"), points))
    return None


def _needs_review(response):
    if _timed_out(response):
        return False
    item = response.attempt_question
    qtype = str(getattr(item.question, "question_type", "") or "").lower()
    if qtype not in SUBJECTIVE_TYPES:
        return _point_score(response) is None

    feedback = _feedback(response)
    status = str(feedback.get("status", "") or "").lower()
    assessment = str(feedback.get("assessment_status", "") or "").upper()

    if response.review_status in {
        StudentResponse.ReviewStatus.PENDING,
        StudentResponse.ReviewStatus.AI_QUEUED,
    }:
        return True
    if status in {"queued", "processing", "error", "no_speech"}:
        return True
    if assessment in {"PROCESSING", "INSUFFICIENT_EVIDENCE", "HUMAN_REVIEW"}:
        return True
    return _point_score(response) is None


def _response_status(response):
    if _timed_out(response):
        return "Timed out"
    if _needs_review(response):
        feedback = _feedback(response)
        if str(feedback.get("status", "")).lower() in {"queued", "processing"}:
            return "Processing"
        return "Review required"
    if response.review_status == StudentResponse.ReviewStatus.REVIEWED:
        return "Evaluator reviewed"
    if response.review_status == StudentResponse.ReviewStatus.AI_GRADED:
        return "AI-assisted graded"
    if response.review_status == StudentResponse.ReviewStatus.AUTO_GRADED:
        return "Auto graded"
    return response.get_review_status_display()


def _cefr(response):
    feedback = _feedback(response)
    return (
        feedback.get("practice_cefr")
        or feedback.get("cefr_estimate")
        or feedback.get("cefr")
        or feedback.get("estimated_cefr")
    )


def _transcript(response):
    feedback = _feedback(response)
    for value in (
        feedback.get("transcript"),
        feedback.get("text"),
        feedback.get("transcription"),
        response.text_response,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _list_feedback(response, key):
    value = _feedback(response).get(key)
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()][:5]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _attempt_items(attempt):
    return list(
        attempt.attempt_questions
        .select_related("part", "part__section", "question", "response")
        .order_by("order")
    )


def _build(attempt):
    items = _attempt_items(attempt)
    skill_data = {}
    total_points = Decimal("0")
    earned_points = Decimal("0")
    scored_points_max = Decimal("0")
    response_count = 0
    pending_review = 0
    timed_out = 0
    missing_responses = 0
    qa_issues = []

    orders = [item.order for item in items]
    if orders and orders != list(range(1, len(orders) + 1)):
        qa_issues.append("AttemptQuestion order is not contiguous from 1..N.")
    if len(orders) != len(set(orders)):
        qa_issues.append("Duplicate AttemptQuestion.order values detected.")

    sections = list(attempt.mock_test.sections.order_by("order"))
    section_skills = tuple(str(s.skill).lower() for s in sections)
    if section_skills != SKILL_ORDER:
        qa_issues.append("Full Mock section order is not Reading → Listening → Speaking → Writing.")

    for skill in SKILL_ORDER:
        skill_data[skill] = {
            "key": skill,
            "label": skill.title(),
            "total": 0,
            "answered": 0,
            "correct": 0,
            "timed_out": 0,
            "pending": 0,
            "earned_points": Decimal("0"),
            "max_points": Decimal("0"),
            "scored_max_points": Decimal("0"),
            "percent": None,
        }

    response_rows = []
    for item in items:
        skill = str(getattr(item.part.section, "skill", "") or "").lower()
        question_skill = str(getattr(item.question, "skill", "") or "").lower()
        if skill not in skill_data:
            qa_issues.append(f"Unexpected attempt section skill '{skill}' on question {item.pk}.")
            continue
        if question_skill != skill:
            qa_issues.append(
                f"Question {item.question_id} skill '{question_skill}' does not match section '{skill}'."
            )

        points = _d(item.points, Decimal("0")) or Decimal("0")
        points = max(Decimal("0"), points)
        total_points += points
        row = skill_data[skill]
        row["total"] += 1
        row["max_points"] += points

        try:
            response = item.response
        except StudentResponse.DoesNotExist:
            response = None

        point_score = None
        status_label = "Not submitted"
        is_timeout = False
        needs_review = False
        is_correct = None
        review_status = ""
        cefr = None
        transcript = ""
        strengths = []
        improvements = []
        feedback = {}

        if response is None:
            missing_responses += 1
        else:
            response_count += 1
            row["answered"] += 1
            is_timeout = _timed_out(response)
            needs_review = _needs_review(response)
            point_score = _point_score(response)
            status_label = _response_status(response)
            is_correct = response.is_correct
            review_status = response.review_status
            cefr = _cefr(response)
            transcript = _transcript(response)
            strengths = _list_feedback(response, "strengths")
            improvements = _list_feedback(response, "improvements")
            feedback = _feedback(response)

            if is_timeout:
                timed_out += 1
                row["timed_out"] += 1
            if needs_review:
                pending_review += 1
                row["pending"] += 1
            if response.is_correct is True:
                row["correct"] += 1

            if point_score is not None:
                earned_points += point_score
                scored_points_max += points
                row["earned_points"] += point_score
                row["scored_max_points"] += points

        percent = None
        if point_score is not None and points > 0:
            percent = round(float(point_score / points * Decimal("100")), 1)

        response_rows.append({
            "item": item,
            "response": response,
            "skill": skill,
            "skill_label": skill.title(),
            "point_score": point_score,
            "max_points": points,
            "percent": percent,
            "status": status_label,
            "timed_out": is_timeout,
            "needs_review": needs_review,
            "is_correct": is_correct,
            "review_status": review_status,
            "cefr": cefr,
            "transcript": transcript,
            "strengths": strengths,
            "improvements": improvements,
            "feedback": feedback,
        })

    for skill in SKILL_ORDER:
        row = skill_data[skill]
        if (
            row["total"] > 0
            and row["answered"] == row["total"]
            and row["pending"] == 0
            and row["scored_max_points"] == row["max_points"]
            and row["max_points"] > 0
        ):
            row["percent"] = round(
                float(row["earned_points"] / row["max_points"] * Decimal("100")), 1
            )

    all_responses_present = bool(items) and response_count == len(items)
    all_scores_ready = all_responses_present and pending_review == 0 and scored_points_max == total_points

    overall_percent = None
    if all_scores_ready and total_points > 0:
        overall_percent = round(float(earned_points / total_points * Decimal("100")), 1)

    if not items:
        qa_issues.append("Attempt contains no questions.")
    if attempt.status != TestAttempt.Status.IN_PROGRESS and missing_responses:
        qa_issues.append(f"{missing_responses} question(s) have no StudentResponse after submission.")

    result_state = (
        "ready" if all_scores_ready
        else "incomplete" if attempt.status != TestAttempt.Status.IN_PROGRESS and missing_responses
        else "processing"
    )

    return {
        "version": VERSION,
        "attempt": attempt,
        "skills": [skill_data[s] for s in SKILL_ORDER],
        "skill_map": skill_data,
        "response_rows": response_rows,
        "question_count": len(items),
        "response_count": response_count,
        "missing_responses": missing_responses,
        "pending_review": pending_review,
        "timed_out": timed_out,
        "earned_points": _q(earned_points),
        "max_points": _q(total_points),
        "scored_max_points": _q(scored_points_max),
        "overall_percent": overall_percent,
        "result_state": result_state,
        "qa_issues": qa_issues,
        "qa_ok": not qa_issues,
        "all_scores_ready": all_scores_ready,
        "all_responses_present": all_responses_present,
    }


def _serialize(summary):
    skills = {}
    for row in summary["skills"]:
        skills[row["key"]] = {
            "answered": row["answered"],
            "total": row["total"],
            "correct": row["correct"],
            "timed_out": row["timed_out"],
            "pending": row["pending"],
            "earned_points": str(_q(row["earned_points"])),
            "max_points": str(_q(row["max_points"])),
            "percent": row["percent"],
        }
    return {
        "version": VERSION,
        "result_state": summary["result_state"],
        "question_count": summary["question_count"],
        "response_count": summary["response_count"],
        "missing_responses": summary["missing_responses"],
        "pending_review": summary["pending_review"],
        "timed_out": summary["timed_out"],
        "earned_points": str(summary["earned_points"]),
        "max_points": str(summary["max_points"]),
        "overall_percent": summary["overall_percent"],
        "qa_ok": summary["qa_ok"],
        "qa_issues": list(summary["qa_issues"]),
        "skills": skills,
    }


@transaction.atomic
def sync_attempt_result(attempt):
    locked = (
        TestAttempt.objects.select_for_update()
        .select_related("mock_test", "mock_test__program")
        .get(pk=attempt.pk)
    )
    if not is_continuous_full_mock(locked):
        return _build(locked)

    summary = _build(locked)
    metadata = dict(locked.metadata or {})
    previous = metadata.get(META_KEY)
    payload = _serialize(summary)

    if isinstance(previous, dict):
        if previous.get("finalized_at"):
            payload["finalized_at"] = previous.get("finalized_at")
        if previous.get("submitted_at"):
            payload["submitted_at"] = previous.get("submitted_at")

    if locked.status != TestAttempt.Status.IN_PROGRESS:
        payload.setdefault("submitted_at", (locked.completed_at or timezone.now()).isoformat())

    update_fields = []

    if locked.status not in {TestAttempt.Status.IN_PROGRESS, TestAttempt.Status.CANCELLED}:
        if summary["result_state"] == "ready":
            if locked.status != TestAttempt.Status.COMPLETED:
                locked.status = TestAttempt.Status.COMPLETED
                update_fields.append("status")
            if not payload.get("finalized_at"):
                payload["finalized_at"] = timezone.now().isoformat()
            if locked.completed_at is None:
                locked.completed_at = timezone.now()
                update_fields.append("completed_at")
        else:
            if locked.status != TestAttempt.Status.GRADING:
                locked.status = TestAttempt.Status.GRADING
                update_fields.append("status")

    if summary["result_state"] == "ready":
        raw_score = summary["earned_points"]
        raw_max = summary["max_points"]
        if locked.overall_score != raw_score:
            locked.overall_score = raw_score
            update_fields.append("overall_score")
        if locked.max_score != raw_max:
            locked.max_score = raw_max
            update_fields.append("max_score")

    metadata[META_KEY] = payload
    if metadata != (locked.metadata or {}):
        locked.metadata = metadata
        update_fields.append("metadata")

    if update_fields:
        locked.save(update_fields=list(dict.fromkeys(update_fields)))

    locked.refresh_from_db()
    summary["attempt"] = locked
    return summary


def summary_for_attempt(attempt, sync=True):
    if sync and attempt.status not in {TestAttempt.Status.IN_PROGRESS, TestAttempt.Status.CANCELLED}:
        return sync_attempt_result(attempt)
    return _build(attempt)


def history_rows(user, limit=20):
    attempts = list(
        TestAttempt.objects
        .filter(user=user, mock_test__delivery_mode="full_mock")
        .exclude(status=TestAttempt.Status.IN_PROGRESS)
        .select_related("mock_test", "mock_test__program")
        .order_by("-started_at", "-pk")[:limit]
    )
    rows = []
    for attempt in attempts:
        if not is_continuous_full_mock(attempt):
            continue
        if attempt.status == TestAttempt.Status.CANCELLED:
            rows.append({
                "attempt": attempt,
                "state": "cancelled",
                "state_label": "Cancelled",
                "overall_percent": None,
                "pending": 0,
                "result_url": None,
            })
            continue
        summary = sync_attempt_result(attempt)
        state = summary["result_state"]
        rows.append({
            "attempt": summary["attempt"],
            "summary": summary,
            "state": state,
            "state_label": "Result ready" if state == "ready" else "Needs attention" if state == "incomplete" else "Processing",
            "overall_percent": summary["overall_percent"],
            "pending": summary["pending_review"],
            "result_url": reverse("results:attempt_report", args=[attempt.pk]),
        })
    return rows


def result_view(request, attempt):
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:dispatch", attempt_id=attempt.pk)

    summary = sync_attempt_result(attempt)
    attempt = summary["attempt"]
    groups = []
    for skill_row in summary["skills"]:
        rows = [row for row in summary["response_rows"] if row["skill"] == skill_row["key"]]
        groups.append({"summary": skill_row, "rows": rows})

    return render(request, "full_mock_v35/results.html", {
        "attempt": attempt,
        "summary": summary,
        "groups": groups,
        "processing": summary["result_state"] == "processing",
        "incomplete": summary["result_state"] == "incomplete",
        "result_ready": summary["result_state"] == "ready",
        "is_staff": request.user.is_staff,
    })
