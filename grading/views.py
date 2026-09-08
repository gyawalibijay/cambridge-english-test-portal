from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from attempts.models import StudentResponse


def _require_evaluator(user):
    allowed = user.is_superuser or user.is_staff or getattr(user, "role", "") in {"admin", "evaluator"}
    if not allowed:
        raise PermissionDenied


@login_required
def review_queue(request):
    _require_evaluator(request.user)
    responses = (
        StudentResponse.objects
        .filter(
            attempt_question__question__question_type__in=[
                "long_text",
                "recorded_response",
                "read_aloud",
                "interview_response",
            ]
        )
        .exclude(review_status=StudentResponse.ReviewStatus.REVIEWED)
        .select_related(
            "attempt_question__attempt__user",
            "attempt_question__question",
            "attempt_question__part",
        )
        .order_by("created_at")
    )
    return render(request, "grading/review_queue.html", {"responses": responses})


@login_required
def review_response(request, response_id):
    _require_evaluator(request.user)
    response = get_object_or_404(
        StudentResponse.objects.select_related(
            "attempt_question__attempt__user",
            "attempt_question__attempt__mock_test",
            "attempt_question__question",
            "attempt_question__part",
        ),
        pk=response_id,
    )
    return render(request, "grading/review_response.html", {"response": response})


@login_required
@require_POST
def save_review(request, response_id):
    _require_evaluator(request.user)
    response = get_object_or_404(
        StudentResponse.objects.select_related("attempt_question"),
        pk=response_id,
    )

    score_raw = request.POST.get("evaluator_score", "").strip()
    feedback = request.POST.get("feedback", "").strip()
    score = None
    if score_raw:
        try:
            score = Decimal(score_raw)
        except (InvalidOperation, TypeError):
            score = None

    max_points = response.attempt_question.points
    if score is not None:
        if score < 0:
            score = Decimal("0")
        if score > max_points:
            score = max_points

    response.evaluator_score = score
    response.final_score = (
        score
        if score is not None
        else response.ai_score
        if response.ai_score is not None
        else response.auto_score
    )
    response.feedback = feedback
    response.reviewer = request.user
    response.reviewed_at = timezone.now()
    response.review_status = StudentResponse.ReviewStatus.REVIEWED
    response.save()

    # B1_FULL_MOCK_REVIEW_SYNC_V35_PART3
    try:
        from attempts.full_mock_v35_part2 import is_continuous_full_mock
        from attempts.full_mock_v35_part3 import sync_attempt_result
        attempt = response.attempt_question.attempt
        if is_continuous_full_mock(attempt):
            sync_attempt_result(attempt)
    except Exception:
        # Never lose a saved evaluator review because result aggregation failed.
        pass
    # /B1_FULL_MOCK_REVIEW_SYNC_V35_PART3

    return redirect("grading:review_queue")
