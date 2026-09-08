from statistics import mean

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from attempts.models import StudentResponse, TestAttempt


BLANK_MARKERS = {
    "[blank_audio]",
    "blank_audio",
    "[blank audio]",
    "[no_speech]",
    "[no speech]",
    "no_speech",
    "[silence]",
    "silence",
}


def _feedback(response):
    value = response.ai_feedback
    return value if isinstance(value, dict) else {}


def _transcript(response):
    feedback = _feedback(response)

    for value in (
        feedback.get("transcript"),
        feedback.get("text"),
        feedback.get("transcription"),
        feedback.get("recognized_text"),
        response.text_response,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _blank_speech(response):
    try:
        if response.attempt_question.question.skill != "speaking":
            return False
    except Exception:
        return False

    feedback = _feedback(response)
    transcript = _transcript(response).lower().strip()

    return (
        transcript in BLANK_MARKERS
        or str(feedback.get("status", "")).lower().strip()
        in {"blank_audio", "no_speech", "silence"}
    )


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


def _score_percent(response):
    if _blank_speech(response):
        return None

    raw = _raw_score(response)

    if raw is None:
        return None

    skill = response.attempt_question.question.skill
    points = float(response.attempt_question.points or 0)

    # Speaking/Writing local practice scores are stored on a 0-100 scale.
    if skill in {"speaking", "writing"}:
        return round(max(0.0, min(100.0, raw)), 1)

    # Objective Reading/Listening scores are normally point based.
    if points > 0:
        return round(max(0.0, min(100.0, raw / points * 100)), 1)

    return None


def _extract_metric(feedback, names):
    containers = [
        feedback,
        feedback.get("rubric"),
        feedback.get("scores"),
        feedback.get("breakdown"),
    ]

    for container in containers:
        if not isinstance(container, dict):
            continue

        for name in names:
            value = container.get(name)

            if isinstance(value, dict):
                value = (
                    value.get("score")
                    or value.get("value")
                    or value.get("earned")
                )

            try:
                if value is not None:
                    return round(float(value), 1)
            except (TypeError, ValueError):
                pass

    return None


def _list_value(feedback, key):
    value = feedback.get(key)

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _response_row(response):
    feedback = _feedback(response)
    transcript = _transcript(response)
    blank = _blank_speech(response)
    question = response.attempt_question.question
    part = response.attempt_question.part

    if blank:
        transcript_display = "No usable speech detected."
        strengths = []
        improvements = [
            "No usable speech was detected in this recording.",
            "Check the microphone and record the answer again.",
        ]
        cefr = None
    else:
        transcript_display = transcript
        strengths = _list_value(feedback, "strengths")
        improvements = _list_value(feedback, "improvements")

        cefr = (
            feedback.get("practice_cefr")
            or feedback.get("cefr_estimate")
            or feedback.get("cefr")
            or feedback.get("estimated_cefr")
        )

    return {
        "response": response,
        "question": question,
        "part": part,
        "skill": question.skill,
        "score_percent": _score_percent(response),
        "is_blank_audio": blank,
        "transcript": transcript_display,
        "cefr": cefr,
        "strengths": strengths,
        "improvements": improvements,
        "task": None if blank else _extract_metric(
            feedback,
            ["task_achievement", "task", "task_completion", "task_score"],
        ),
        "language": None if blank else _extract_metric(
            feedback,
            ["grammar", "language", "language_control"],
        ),
        "vocabulary": None if blank else _extract_metric(
            feedback,
            ["vocabulary", "lexical_resource", "vocab"],
        ),
        "fluency": None if blank else _extract_metric(
            feedback,
            ["fluency", "fluency_score"],
        ),
        "intelligibility": None if blank else _extract_metric(
            feedback,
            ["pronunciation_intelligibility", "intelligibility", "pronunciation", "clarity"],
        ),
        "coherence": None if blank else _extract_metric(
            feedback,
            ["coherence", "discourse_management"],
        ),
        "assessment_status": feedback.get("assessment_status"),
        "feedback": feedback,
    }


def _attempt_summary(attempt):
    responses = (
        StudentResponse.objects
        .filter(attempt_question__attempt=attempt)
        .select_related(
            "attempt_question__question",
            "attempt_question__part",
        )
    )

    rows = [_response_row(response) for response in responses]
    scored = [
        row["score_percent"]
        for row in rows
        if row["score_percent"] is not None
    ]

    average = round(mean(scored), 1) if scored else None

    return {
        "attempt": attempt,
        "response_count": len(rows),
        "score_percent": average,
    }


@login_required
def results_index(request):
    attempts = (
        TestAttempt.objects
        .filter(user=request.user)
        .exclude(status="cancelled")
        .select_related(
            "mock_test",
            "mock_test__program",
        )
        .order_by("-started_at")
    )

    summaries = [
        _attempt_summary(attempt)
        for attempt in attempts
    ]

    scored = [
        item["score_percent"]
        for item in summaries
        if item["score_percent"] is not None
    ]

    context = {
        "summaries": summaries,
        "attempt_count": len(summaries),
        "scored_count": len(scored),
        "average_score": (
            round(mean(scored), 1)
            if scored
            else None
        ),
    }

    return render(
        request,
        "results/results_v2.html",
        context,
    )


@login_required
def attempt_report(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt.objects.select_related(
            "mock_test",
            "mock_test__program",
        ),
        pk=attempt_id,
    )

    if (
        attempt.user_id != request.user.id
        and not request.user.is_staff
    ):
        return get_object_or_404(
            TestAttempt,
            pk=-1,
        )

    responses = (
        StudentResponse.objects
        .filter(attempt_question__attempt=attempt)
        .select_related(
            "attempt_question__question",
            "attempt_question__part",
        )
        .order_by("attempt_question__order")
    )

    rows = [_response_row(response) for response in responses]

    scored = [
        row["score_percent"]
        for row in rows
        if row["score_percent"] is not None
    ]

    context = {
        "attempt": attempt,
        "rows": rows,
        "score_percent": (
            round(mean(scored), 1)
            if scored
            else None
        ),
        "blank_count": sum(
            1 for row in rows if row["is_blank_audio"]
        ),
        "b1_assessment": (attempt.metadata or {}).get("b1_assessment"),
    }

    return render(
        request,
        "results/report_v2.html",
        context,
    )

# === B1_FULL_MOCK_RESULTS_HISTORY_V35_PART3 START ===
_B1_P3_ORIGINAL_ATTEMPT_SUMMARY = _attempt_summary
_B1_P3_ORIGINAL_ATTEMPT_REPORT = attempt_report


def _attempt_summary(attempt):
    from attempts.full_mock_v35_part2 import is_continuous_full_mock
    if not is_continuous_full_mock(attempt):
        return _B1_P3_ORIGINAL_ATTEMPT_SUMMARY(attempt)
    from attempts.full_mock_v35_part3 import summary_for_attempt
    summary = summary_for_attempt(attempt, sync=True)
    return {
        "attempt": summary["attempt"],
        "response_count": summary["response_count"],
        "score_percent": summary["overall_percent"],
    }


@login_required
def attempt_report(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt.objects.select_related("mock_test", "mock_test__program"),
        pk=attempt_id,
    )
    if attempt.user_id != request.user.id and not request.user.is_staff:
        return get_object_or_404(TestAttempt, pk=-1)
    from attempts.full_mock_v35_part2 import is_continuous_full_mock
    if is_continuous_full_mock(attempt):
        from attempts.full_mock_v35_part3 import result_view
        return result_view(request, attempt)
    return _B1_P3_ORIGINAL_ATTEMPT_REPORT(request, attempt_id)
# === B1_FULL_MOCK_RESULTS_HISTORY_V35_PART3 END ===

