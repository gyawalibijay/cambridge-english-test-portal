from decimal import Decimal, InvalidOperation

from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .marking import mark_objective_question
from .models import AttemptQuestion, StudentResponse, TestAttempt
from .services import next_unanswered_question


def _owned_attempt(request, attempt_id):
    queryset = TestAttempt.objects.select_related("mock_test", "mock_test__program")
    if request.user.is_staff:
        return get_object_or_404(queryset, pk=attempt_id)
    return get_object_or_404(queryset, pk=attempt_id, user=request.user)


def _finish_attempt(attempt):
    attempt.status = TestAttempt.Status.SUBMITTED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at"])



# B1_LISTENING_AUTHORITATIVE_TIMER_V34_6_3
LISTENING_PART_TIMER_DEFAULT_SECONDS = 5 * 60


def _is_listening_item(item):
    return str(getattr(item.question, "skill", "") or "").lower() == "listening"


def _listening_part_timer_seconds():
    """
    Five minutes per Listening Part by default.

    The current Listening workflow has Parts 1-5, so this yields a 25-minute
    total when all five Parts are present. A future deployment can override
    this without another code patch by defining
    CAMBRIDGE_LISTENING_PART_SECONDS in Django settings.
    """
    raw = getattr(
        settings,
        "CAMBRIDGE_LISTENING_PART_SECONDS",
        LISTENING_PART_TIMER_DEFAULT_SECONDS,
    )

    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        seconds = LISTENING_PART_TIMER_DEFAULT_SECONDS

    # Prevent an accidental zero or absurd value from breaking the exam.
    return max(60, min(seconds, 60 * 60))


def _listening_part_timer_state(attempt, item):
    """
    Persistent server-owned timer for this attempt + Listening Part.

    The deadline is written only when that Part is first opened. Moving among
    questions in the same Part or refreshing the page does not reset it.
    """
    if not _is_listening_item(item):
        return None

    duration = _listening_part_timer_seconds()
    now_ts = timezone.now().timestamp()

    metadata = dict(attempt.metadata or {})
    timers = metadata.get("listening_part_timers_v3463")

    if not isinstance(timers, dict):
        timers = {}

    key = str(item.part_id)
    entry = timers.get(key)

    deadline = None
    stored_duration = duration

    if isinstance(entry, dict):
        try:
            deadline = float(entry.get("deadline"))
        except (TypeError, ValueError):
            deadline = None

        try:
            stored_duration = int(entry.get("duration") or duration)
        except (TypeError, ValueError):
            stored_duration = duration

    if not deadline or deadline <= 0:
        deadline = now_ts + duration
        stored_duration = duration

        timers[key] = {
            "deadline": deadline,
            "duration": stored_duration,
        }
        metadata["listening_part_timers_v3463"] = timers

        attempt.metadata = metadata
        attempt.save(update_fields=["metadata"])

    remaining_ms = max(
        0,
        int(round((deadline - now_ts) * 1000)),
    )

    remaining_seconds = max(
        0,
        (remaining_ms + 999) // 1000,
    )

    return {
        "deadline": deadline,
        "duration_seconds": stored_duration,
        "remaining_ms": remaining_ms,
        "remaining_seconds": remaining_seconds,
        "initial_display": (
            f"{remaining_seconds // 60:02d}:"
            f"{remaining_seconds % 60:02d}"
        ),
    }


def _expire_listening_part(attempt, part):
    """
    Enforce the deadline on the server.

    Existing answers are preserved. Only unanswered questions in the expired
    Listening Part receive timed-out zero-score responses.
    """
    unanswered = (
        attempt.attempt_questions
        .filter(part=part, response__isnull=True)
        .select_related("question")
        .order_by("order")
    )

    expired = 0

    for question_item in unanswered:
        response, created = StudentResponse.objects.get_or_create(
            attempt_question=question_item,
        )

        if not created:
            continue

        response.answer_data = {
            "timed_out": True,
            "reason": "listening_part_timer_expired",
        }
        response.is_correct = False
        response.auto_score = Decimal("0.00")
        response.final_score = Decimal("0.00")
        response.review_status = StudentResponse.ReviewStatus.AUTO_GRADED
        response.save(
            update_fields=[
                "answer_data",
                "is_correct",
                "auto_score",
                "final_score",
                "review_status",
            ]
        )
        expired += 1

    return expired
# /B1_LISTENING_AUTHORITATIVE_TIMER_V34_6_3

def _route_for_item(item):
    qtype = item.question.question_type
    if qtype in {
        item.question.Type.RECORDED_RESPONSE,
        item.question.Type.READ_ALOUD,
        item.question.Type.INTERVIEW_RESPONSE,
    }:
        return "attempts:speaking_runner"
    if qtype == item.question.Type.LONG_TEXT:
        return "attempts:writing_runner"
    return "attempts:objective_runner"


def _next_url(attempt):
    item = next_unanswered_question(attempt)
    if item is None:
        _finish_attempt(attempt)
        return reverse("attempts:complete", kwargs={"attempt_id": attempt.pk})
    return reverse(_route_for_item(item), kwargs={"attempt_id": attempt.pk})


@login_required
def dispatch(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.mock_test.slug == "cambridge-reading-reference-practice":
        return redirect("assessments:reading_runner", attempt_id=attempt.pk)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)
    return redirect(_next_url(attempt))


@login_required
@ensure_csrf_cookie
def speaking_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    if _route_for_item(item) != "attempts:speaking_runner":
        return redirect(_next_url(attempt))

    total = attempt.attempt_questions.count()
    answered = StudentResponse.objects.filter(attempt_question__attempt=attempt).count()
    part_total = attempt.attempt_questions.filter(part=item.part).count()
    part_position = attempt.attempt_questions.filter(part=item.part, order__lte=item.order).count()

    # ADMIN CONTENT AUDIO V14.14:
    # question Admin upload -> shared Stimulus audio -> empty URL/browser voice fallback
    prompt_audio_url = ""
    if item.question.prompt_audio:
        prompt_audio_url = item.question.prompt_audio.url
    elif item.question.stimulus and item.question.stimulus.audio_file:
        prompt_audio_url = item.question.stimulus.audio_file.url

    return render(
        request,
        "attempts/speaking_runner.html",
        {
            "attempt": attempt,
            "item": item,
            "total": total,
            "answered": answered,
            "part_total": part_total,
            "part_position": part_position,
            "prompt_audio_url": prompt_audio_url,
            "preparation_seconds": (
                item.question.preparation_seconds
                if item.question.preparation_seconds is not None
                else item.part.preparation_seconds
            ),
            "response_seconds": (
                item.question.response_seconds
                if item.question.response_seconds is not None
                else item.part.response_seconds
            ),
            "minimum_response_seconds": getattr(item.part, "minimum_response_seconds", None),
        },
    )


@login_required
@require_POST
def submit_speaking_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return JsonResponse({"error": "Attempt is not active."}, status=400)

    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part"),
        pk=question_id,
        attempt=attempt,
    )
    audio = request.FILES.get("audio")
    if (attempt.metadata or {}).get("practice_mode") == "skill_mock":
        if _route_for_item(item) != "attempts:speaking_runner":
            return JsonResponse({"error": "This question does not accept a recording."}, status=400)
        current = next_unanswered_question(attempt)
        if current is None or current.pk != item.pk:
            return JsonResponse({"ok": True, "next_url": _next_url(attempt)})
    if audio is None:
        return JsonResponse({"error": "No audio recording was received."}, status=400)

    duration = None
    duration_value = request.POST.get("duration_seconds")
    if duration_value:
        try:
            duration = Decimal(duration_value)
        except (InvalidOperation, TypeError):
            duration = None

    response, _ = StudentResponse.objects.get_or_create(attempt_question=item)
    response.audio_response = audio
    response.duration_seconds = duration
    response.review_status = StudentResponse.ReviewStatus.AI_QUEUED
    response.ai_feedback = {
        "status": "queued",
        "engine": "local whisper.cpp",
        "paid_api_used": False,
    }
    response.save()

    from grading.tasks import grade_speaking_response
    # B1_FULL_MOCK_SAFE_AI_QUEUE_V35_1
    if (attempt.metadata or {}).get("practice_mode") in {"skill_mock", "full_mock"}:
        from assessments.skill_mock import queue_review
        queue_review(response, grade_speaking_response)
    else:
        grade_speaking_response.delay(response.pk)
    # /B1_FULL_MOCK_SAFE_AI_QUEUE_V35_1

    return JsonResponse({"ok": True, "next_url": _next_url(attempt)})


@login_required
def objective_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.mock_test.slug == "cambridge-reading-reference-practice":
        return redirect("assessments:reading_runner", attempt_id=attempt.pk)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    if _route_for_item(item) != "attempts:objective_runner":
        return redirect(_next_url(attempt))

    listening_timer = _listening_part_timer_state(
        attempt,
        item,
    )

    if (
        listening_timer is not None
        and listening_timer["remaining_ms"] <= 0
    ):
        _expire_listening_part(
            attempt,
            item.part,
        )
        return redirect(_next_url(attempt))

    # B1_MOCK_PART_LOCAL_OBJECTIVE_PROGRESS_V40_8_3 START
    total = attempt.attempt_questions.count()
    _b1_mock_part_position = None
    _b1_mock_part_total = None
    _b1_mock_part_progress_percent = None
    try:
        from . import full_mock_part_flow_v40_5 as _b1_mock_part_flow
        if _b1_mock_part_flow.is_part_flow_attempt(attempt):
            _sel = _b1_mock_part_flow.selection(attempt)
            _pid = _sel.get("selected_part_id")
            if _pid and int(_pid) == int(item.part_id):
                _part_qs = (
                    attempt.attempt_questions
                    .filter(part_id=_pid)
                    .order_by("order", "pk")
                )
                _part_ids = list(_part_qs.values_list("pk", flat=True))
                _b1_mock_part_total = len(_part_ids)
                if item.pk in _part_ids:
                    _b1_mock_part_position = _part_ids.index(item.pk) + 1
                if _b1_mock_part_total:
                    total = _b1_mock_part_total
                if _b1_mock_part_position and _b1_mock_part_total:
                    _b1_mock_part_progress_percent = round(
                        (_b1_mock_part_position / _b1_mock_part_total) * 100,
                        2,
                    )
    except Exception:
        pass
    # B1_MOCK_PART_LOCAL_OBJECTIVE_PROGRESS_V40_8_3 END
    answered = StudentResponse.objects.filter(attempt_question__attempt=attempt).count()
    stimulus = item.question.stimulus
    # LISTENING AUDIO PRIORITY V14.14:
    # Question-specific Admin audio overrides a shared Stimulus track.
    prompt_audio_url = item.question.prompt_audio.url if item.question.prompt_audio else ""
    stimulus_audio_url = (
        stimulus.audio_file.url
        if stimulus and stimulus.audio_file and not prompt_audio_url
        else ""
    )

    return render(
        request,
        "attempts/objective_runner.html",
        {
            "attempt": attempt,
            "item": item,
            "total": total,
            "answered": answered,
            "stimulus": stimulus,
            "stimulus_audio_url": stimulus_audio_url,
            "prompt_audio_url": prompt_audio_url,
            "max_audio_plays": item.part.max_audio_plays,
            "mock_part_position": _b1_mock_part_position,
            "mock_part_total": _b1_mock_part_total,
            "mock_part_progress_percent": _b1_mock_part_progress_percent,
            "listening_timer_remaining_ms": (
                listening_timer["remaining_ms"]
                if listening_timer is not None
                else None
            ),
            "listening_timer_initial": (
                listening_timer["initial_display"]
                if listening_timer is not None
                else ""
            ),
            "listening_timer_duration_seconds": (
                listening_timer["duration_seconds"]
                if listening_timer is not None
                else None
            ),
        },
    )


@login_required
@require_POST
def submit_objective_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.mock_test.slug == "cambridge-reading-reference-practice":
        from assessments.reading_reference import answer
        return answer(request, attempt_id, question_id=question_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part"),
        pk=question_id,
        attempt=attempt,
    )

    if (attempt.metadata or {}).get("practice_mode") == "skill_mock":
        current = next_unanswered_question(attempt)
        if current is None or current.pk != item.pk:
            return redirect(_next_url(attempt))
        from assessments.skill_mock import validate_objective
        error = validate_objective(item, request.POST)
        if error is not None:
            return error
    try:
        is_correct, answer_data = mark_objective_question(item.question, request.POST)
    except ValueError:
        return redirect("attempts:objective_runner", attempt_id=attempt.pk)

    score = item.points if is_correct else Decimal("0.00")
    response, _ = StudentResponse.objects.get_or_create(attempt_question=item)
    response.answer_data = answer_data
    response.is_correct = is_correct
    response.auto_score = score
    response.final_score = score
    response.review_status = StudentResponse.ReviewStatus.AUTO_GRADED
    response.save()

    return redirect(_next_url(attempt))


@login_required
def complete(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if (attempt.metadata or {}).get("practice_mode") == "skill_mock":
        from assessments.skill_mock import results
        return results(request, attempt)

    responses = list(
        StudentResponse.objects
        .filter(attempt_question__attempt=attempt)
        .select_related(
            "attempt_question",
            "attempt_question__part",
            "attempt_question__question",
        )
        .order_by("attempt_question__order")
    )

    has_ai_pending = False
    has_ai_errors = False

    for response in responses:
        feedback = response.ai_feedback or {}
        if response.review_status == StudentResponse.ReviewStatus.AI_QUEUED:
            has_ai_pending = True
        if feedback.get("status") in {"queued", "processing"}:
            has_ai_pending = True
        if feedback.get("status") == "error":
            has_ai_errors = True

    return render(
        request,
        "attempts/complete.html",
        {
            "attempt": attempt,
            "responses": responses,
            "has_ai_pending": has_ai_pending,
            "has_ai_errors": has_ai_errors,
        },
    )


def _writing_runtime_context(attempt, item):
    """UI-only timing/progress values for the Cambridge-style writing runner."""
    seconds = int(getattr(item.part, "response_seconds", 0) or 0)

    if not seconds:
        section = item.part.section
        section_seconds = int(getattr(section, "duration_seconds", 0) or 900)

        try:
            active_part_count = section.parts.filter(is_active=True).count() or 1
        except Exception:
            active_part_count = 1

        seconds = max(60, int(round(section_seconds / active_part_count)))

    part_total = attempt.attempt_questions.filter(part=item.part).count() or 1
    part_answered = StudentResponse.objects.filter(
        attempt_question__attempt=attempt,
        attempt_question__part=item.part,
    ).count()

    return {
        "writing_duration_seconds": seconds,
        "writing_duration_minutes": max(1, int(round(seconds / 60))),
        "writing_part_total": part_total,
        "writing_question_number": min(part_answered + 1, part_total),
    }


@login_required
def writing_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    if _route_for_item(item) != "attempts:writing_runner":
        return redirect(_next_url(attempt))

    total = attempt.attempt_questions.count()
    answered = StudentResponse.objects.filter(attempt_question__attempt=attempt).count()

    return render(
        request,
        "attempts/writing_runner.html",
        {
            "attempt": attempt,
            "item": item,
            "total": total,
            "answered": answered,
            "min_word_count": item.question.min_word_count or item.part.min_word_count or 0,
            "max_word_count": item.question.max_word_count,
            **_writing_runtime_context(attempt, item),
        },
    )


@login_required
@require_POST
def submit_writing_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part"),
        pk=question_id,
        attempt=attempt,
    )

    if (attempt.metadata or {}).get("practice_mode") == "skill_mock":
        current = next_unanswered_question(attempt)
        if current is None or current.pk != item.pk:
            return redirect(_next_url(attempt))
        if _route_for_item(item) != "attempts:writing_runner":
            return redirect(_next_url(attempt))
    text_response = request.POST.get("text_response", "").strip()
    word_count = len([word for word in text_response.split() if word])
    minimum = item.question.min_word_count or item.part.min_word_count or 0
    maximum = item.question.max_word_count

    context = {
        "attempt": attempt,
        "item": item,
        "total": attempt.attempt_questions.count(),
        "answered": StudentResponse.objects.filter(attempt_question__attempt=attempt).count(),
        "min_word_count": minimum,
        "max_word_count": maximum,
        **_writing_runtime_context(attempt, item),
        "submitted_text": text_response,
    }

    if word_count < minimum:
        context["writing_error"] = (
            f"Your response has {word_count} words. This task requires at least {minimum} words."
        )
        return render(request, "attempts/writing_runner.html", context)

    if maximum and word_count > maximum:
        context["writing_error"] = (
            f"Your response has {word_count} words. The configured maximum is {maximum} words."
        )
        return render(request, "attempts/writing_runner.html", context)

    response, _ = StudentResponse.objects.get_or_create(attempt_question=item)
    response.text_response = text_response
    response.answer_data = {"word_count": word_count}
    response.review_status = (
        StudentResponse.ReviewStatus.AI_QUEUED
        if item.question.ai_grading_required
        else StudentResponse.ReviewStatus.PENDING
    )
    response.save()

    if item.question.ai_grading_required:
        from grading.tasks import grade_writing_response
        # B1_FULL_MOCK_SAFE_AI_QUEUE_V35_1_WRITING
        if (attempt.metadata or {}).get("practice_mode") in {"skill_mock", "full_mock"}:
            from assessments.skill_mock import queue_review
            queue_review(response, grade_writing_response)
        else:
            grade_writing_response.delay(response.pk)
        # /B1_FULL_MOCK_SAFE_AI_QUEUE_V35_1_WRITING

    return redirect(_next_url(attempt))

# === B1_FULL_MOCK_STUDENT_RUNNER_V35_PART2 START ===
# These wrappers affect only multi-section delivery_mode=full_mock attempts.
# All Practice and legacy single-skill mock behavior continues through the
# original functions captured below.
_B1_P2_ORIGINAL_NEXT_URL = _next_url
_B1_P2_ORIGINAL_DISPATCH = dispatch
_B1_P2_ORIGINAL_SPEAKING_RUNNER = speaking_runner
_B1_P2_ORIGINAL_SUBMIT_SPEAKING = submit_speaking_response
_B1_P2_ORIGINAL_OBJECTIVE_RUNNER = objective_runner
_B1_P2_ORIGINAL_SUBMIT_OBJECTIVE = submit_objective_response
_B1_P2_ORIGINAL_WRITING_RUNNER = writing_runner
_B1_P2_ORIGINAL_SUBMIT_WRITING = submit_writing_response
_B1_P2_ORIGINAL_LISTENING_TIMER_STATE = _listening_part_timer_state


def _b1_p2_flow():
    from . import full_mock_v35_part2
    return full_mock_v35_part2


def _listening_part_timer_state(attempt, item):
    # Full Mock Listening owns one 25-minute section deadline. Do not also start
    # the Practice-only five-minute-per-Part clock.
    if _b1_p2_flow().is_continuous_full_mock(attempt):
        return None
    return _B1_P2_ORIGINAL_LISTENING_TIMER_STATE(attempt, item)


def _next_url(attempt):
    flow = _b1_p2_flow()
    if not flow.is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_NEXT_URL(attempt)

    flow.sync_completed_sections(attempt)
    attempt.refresh_from_db(fields=["metadata", "status"])
    for _ in range(8):
        item = next_unanswered_question(attempt)
        if item is None:
            _finish_attempt(attempt)
            return reverse("attempts:complete", kwargs={"attempt_id": attempt.pk})
        state = flow.prepare_item(attempt, item)
        if state["action"] == "expired":
            attempt.refresh_from_db(fields=["metadata", "status"])
            continue
        if state["action"] == "gate":
            return flow.gate_url(attempt)
        return reverse(_route_for_item(item), kwargs={"attempt_id": attempt.pk})

    return flow.gate_url(attempt)


def _b1_p2_guard_current(attempt, item):
    flow = _b1_p2_flow()
    if not flow.is_continuous_full_mock(attempt):
        return None
    current = next_unanswered_question(attempt)
    if current is None or current.pk != item.pk:
        return _next_url(attempt)
    state = flow.prepare_item(attempt, item)
    if state["action"] != "run":
        return _next_url(attempt)
    return None


@login_required
def dispatch(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_DISPATCH(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)
    return redirect(_next_url(attempt))


@login_required
@ensure_csrf_cookie
def speaking_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_SPEAKING_RUNNER(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)
    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return redirect(guarded)
    return _B1_P2_ORIGINAL_SPEAKING_RUNNER(request, attempt_id)


@login_required
@require_POST
def submit_speaking_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_SUBMIT_SPEAKING(request, attempt_id, question_id)
    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part", "part__section"),
        pk=question_id,
        attempt=attempt,
    )
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return JsonResponse({"ok": True, "next_url": guarded})
    return _B1_P2_ORIGINAL_SUBMIT_SPEAKING(request, attempt_id, question_id)


@login_required
def objective_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_OBJECTIVE_RUNNER(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)
    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return redirect(guarded)
    return _B1_P2_ORIGINAL_OBJECTIVE_RUNNER(request, attempt_id)


@login_required
@require_POST
def submit_objective_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_SUBMIT_OBJECTIVE(request, attempt_id, question_id)
    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part", "part__section"),
        pk=question_id,
        attempt=attempt,
    )
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return redirect(guarded)
    from assessments.skill_mock import validate_objective
    error = validate_objective(item, request.POST)
    if error is not None:
        return error
    return _B1_P2_ORIGINAL_SUBMIT_OBJECTIVE(request, attempt_id, question_id)


@login_required
def writing_runner(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_WRITING_RUNNER(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)
    item = next_unanswered_question(attempt)
    if item is None:
        return redirect(_next_url(attempt))
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return redirect(guarded)
    return _B1_P2_ORIGINAL_WRITING_RUNNER(request, attempt_id)


@login_required
@require_POST
def submit_writing_response(request, attempt_id, question_id):
    attempt = _owned_attempt(request, attempt_id)
    if not _b1_p2_flow().is_continuous_full_mock(attempt):
        return _B1_P2_ORIGINAL_SUBMIT_WRITING(request, attempt_id, question_id)
    item = get_object_or_404(
        AttemptQuestion.objects.select_related("question", "part", "part__section"),
        pk=question_id,
        attempt=attempt,
    )
    guarded = _b1_p2_guard_current(attempt, item)
    if guarded:
        return redirect(guarded)
    return _B1_P2_ORIGINAL_SUBMIT_WRITING(request, attempt_id, question_id)
# === B1_FULL_MOCK_STUDENT_RUNNER_V35_PART2 END ===

# === B1_FULL_MOCK_RESULTS_V35_PART3 START ===
_B1_P3_ORIGINAL_COMPLETE = complete


@login_required
def complete(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    from .full_mock_v35_part2 import is_continuous_full_mock
    if is_continuous_full_mock(attempt):
        from .full_mock_v35_part3 import result_view
        return result_view(request, attempt)
    return _B1_P3_ORIGINAL_COMPLETE(request, attempt_id)
# === B1_FULL_MOCK_RESULTS_V35_PART3 END ===

# === B1_FULL_MOCK_EXACT_PART_ONLY_V40_8_3 START ===
# Full Mock only. Live Practice remains untouched.
_B1_V4083_BASE_NEXT_UNANSWERED = next_unanswered_question
_B1_V4083_BASE_NEXT_URL = _next_url
_B1_V4083_BASE_GUARD_CURRENT = _b1_p2_guard_current


def _b1_v4083_partflow():
    from . import full_mock_part_flow_v40_5
    return full_mock_part_flow_v40_5


def next_unanswered_question(attempt):
    flow=_b1_v4083_partflow()

    if not flow.is_part_flow_attempt(attempt):
        return _B1_V4083_BASE_NEXT_UNANSWERED(attempt)

    if not flow.has_selection(attempt):
        return None

    return flow.selected_next(attempt)


def _next_url(attempt):
    flow=_b1_v4083_partflow()

    if not flow.is_part_flow_attempt(attempt):
        return _B1_V4083_BASE_NEXT_URL(attempt)

    return flow.next_url_for_attempt(attempt)


def _b1_p2_guard_current(attempt,item):
    flow=_b1_v4083_partflow()

    if not flow.is_part_flow_attempt(attempt):
        return _B1_V4083_BASE_GUARD_CURRENT(attempt,item)

    if not flow.has_selection(attempt):
        return _next_url(attempt)

    current=flow.selected_next(attempt)

    if current is None or int(current.pk)!=int(item.pk):
        return _next_url(attempt)

    # Do NOT call the old continuous-section prepare/gate.
    return None
# === B1_FULL_MOCK_EXACT_PART_ONLY_V40_8_3 END ===

