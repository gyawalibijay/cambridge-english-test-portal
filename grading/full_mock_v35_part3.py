"""Staff review workspace for Cambridge continuous Full Mocks."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from attempts.full_mock_v35_part2 import is_continuous_full_mock
from attempts.full_mock_v35_part3 import summary_for_attempt
from attempts.models import TestAttempt


def _require_staff(user):
    allowed = user.is_superuser or user.is_staff or getattr(user, "role", "") in {"admin", "evaluator"}
    if not allowed:
        raise PermissionDenied


@login_required
def queue(request):
    _require_staff(request.user)
    attempts = list(
        TestAttempt.objects
        .filter(mock_test__delivery_mode="full_mock")
        .exclude(status=TestAttempt.Status.CANCELLED)
        .select_related("user", "mock_test", "mock_test__program")
        .order_by("-started_at", "-pk")[:120]
    )
    rows = []
    for attempt in attempts:
        if not is_continuous_full_mock(attempt):
            continue
        summary = summary_for_attempt(attempt, sync=attempt.status != TestAttempt.Status.IN_PROGRESS)
        rows.append({
            "attempt": summary["attempt"],
            "summary": summary,
            "needs_attention": bool(summary["pending_review"] or summary["qa_issues"]),
        })
    return render(request, "grading/full_mock_queue_v35.html", {"rows": rows})


@login_required
def attempt_detail(request, attempt_id):
    _require_staff(request.user)
    attempt = get_object_or_404(
        TestAttempt.objects.select_related("user", "mock_test", "mock_test__program"),
        pk=attempt_id,
        mock_test__delivery_mode="full_mock",
    )
    if not is_continuous_full_mock(attempt):
        raise PermissionDenied
    summary = summary_for_attempt(attempt, sync=attempt.status != TestAttempt.Status.IN_PROGRESS)
    subjective = [
        row for row in summary["response_rows"]
        if row["skill"] in {"speaking", "writing"}
    ]
    return render(request, "grading/full_mock_attempt_v35.html", {
        "attempt": summary["attempt"],
        "summary": summary,
        "subjective": subjective,
    })
