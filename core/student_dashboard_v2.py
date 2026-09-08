from statistics import mean

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from assessments.models import MockTest
from attempts.models import StudentResponse, TestAttempt


def _first_published(program_code, slugs):
    for slug in slugs:
        test = (
            MockTest.objects
            .filter(
                program__code=program_code,
                slug=slug,
                is_published=True,
            )
            .select_related("program")
            .first()
        )
        if test:
            return test
    return None


def _raw_score(response):
    if response.evaluator_score is not None:
        return float(response.evaluator_score)
    if response.final_score is not None:
        return float(response.final_score)
    if response.ai_score is not None:
        return float(response.ai_score)
    if response.auto_score is not None:
        return float(response.auto_score)
    return None


def _response_percent(response):
    raw = _raw_score(response)
    if raw is None:
        return None

    try:
        skill = response.attempt_question.question.skill
    except Exception:
        skill = ""

    points = float(response.attempt_question.points or 0)

    if skill in {"speaking", "writing"}:
        percent = raw
    elif points > 0:
        if raw > points and raw <= 100:
            percent = raw
        else:
            percent = raw / points * 100.0
    else:
        percent = raw

    return round(max(0.0, min(100.0, percent)), 1)


def _attempt_percent(attempt):
    responses = (
        StudentResponse.objects
        .filter(attempt_question__attempt=attempt)
        .select_related("attempt_question__question")
    )

    percents = []

    for response in responses:
        percent = _response_percent(response)
        if percent is not None:
            percents.append(percent)

    if not percents:
        return None

    return round(mean(percents), 1)


@login_required
def dashboard_v2(request):
    program_code = "cambridge-general"

    specs = [
        {
            "key": "speaking",
            "title": "Speaking",
            "parts": 5,
            "minutes": 12,
            "icon": "◉",
            "description": "Record, replay and review your spoken answers.",
            "slugs": ["cambridge-speaking-practice-1"],
        },
        {
            "key": "listening",
            "title": "Listening",
            "parts": 5,
            "minutes": 25,
            "icon": "♫",
            "description": "Audio-led objective practice with automatic marking.",
            "slugs": ["cambridge-listening-practice-1"],
        },
        {
            "key": "reading",
            "title": "Reading",
            "parts": 5,
            "minutes": 25,
            "icon": "▤",
            "description": "Short texts, sentence completion and comprehension.",
            "slugs": [
                "cambridge-reading-practice-1",
                "cambridge-reading-source-samples",
            ],
        },
        {
            "key": "writing",
            "title": "Writing",
            "parts": 2,
            "minutes": 30,
            "icon": "✎",
            "description": "Personal email and formal reply with live word count.",
            "slugs": [
                "cambridge-writing-practice-1",
                "cambridge-writing-source-samples",
            ],
        },
    ]

    skill_cards = []
    completed_skills = 0

    for spec in specs:
        test = _first_published(program_code, spec["slugs"])

        latest_attempt = None
        completed = False
        in_progress = False
        latest_percent = None

        if test:
            latest_attempt = (
                TestAttempt.objects
                .filter(user=request.user, mock_test=test)
                .order_by("-started_at")
                .first()
            )

        if latest_attempt:
            in_progress = latest_attempt.status == "in_progress"
            completed = latest_attempt.status in {
                "submitted",
                "grading",
                "completed",
            }
            latest_percent = _attempt_percent(latest_attempt)

        if completed:
            completed_skills += 1

        skill_cards.append(
            {
                **spec,
                "test": test,
                "latest_attempt": latest_attempt,
                "completed": completed,
                "in_progress": in_progress,
                "latest_percent": latest_percent,
            }
        )

    attempts = (
        TestAttempt.objects
        .filter(user=request.user)
        .exclude(status="cancelled")
        .select_related("mock_test", "mock_test__program")
        .order_by("-started_at")
    )

    attempt_count = attempts.count()

    completed_count = attempts.filter(
        status__in=["submitted", "grading", "completed"]
    ).count()

    response_qs = (
        StudentResponse.objects
        .filter(attempt_question__attempt__user=request.user)
        .select_related("attempt_question__question")
    )

    response_count = response_qs.count()

    scored_response_percents = []

    for response in response_qs:
        percent = _response_percent(response)
        if percent is not None:
            scored_response_percents.append(percent)

    average_score = (
        round(mean(scored_response_percents), 1)
        if scored_response_percents
        else None
    )

    recent_attempts = [
        {
            "attempt": attempt,
            "percent": _attempt_percent(attempt),
        }
        for attempt in attempts[:6]
    ]

    completion_pct = int(round(completed_skills / 4 * 100))

    first_name = (
        request.user.first_name.strip()
        if request.user.first_name
        else request.user.username.split("@")[0]
    )

    context = {
        "first_name": first_name,
        "skill_cards": skill_cards,
        "attempt_count": attempt_count,
        "completed_count": completed_count,
        "response_count": response_count,
        "average_score": average_score,
        "completion_pct": completion_pct,
        "completed_skills": completed_skills,
        "recent_attempts": recent_attempts,
    }

    return render(
        request,
        "core/student_dashboard_v2.html",
        context,
    )
