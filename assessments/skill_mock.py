"""Focused mocks using the existing protected assessment and response routes."""
from decimal import Decimal
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from attempts.models import StudentResponse, TestAttempt
from attempts.services import create_attempt_for_test
from .models import MockTest
from .skill_mock_data import SKILLS, SLUGS


def skill_for_test(test):
    if test.program.code != "cambridge-general" or test.delivery_mode != "full_mock":
        return None
    return next((skill for skill, slug in SLUGS.items() if test.slug == slug), None)


def active_mock(user):
    return (TestAttempt.objects.select_related("mock_test", "mock_test__program")
            .filter(user=user, mock_test__slug__in=SLUGS.values(),
                    status=TestAttempt.Status.IN_PROGRESS)
            .order_by("started_at", "pk").first())


def contents(test):
    """Do not advertise an empty/partially configured or mixed-skill test as ready."""
    skill = skill_for_test(test)
    sections = list(test.sections.all())
    if not skill or len(sections) != 1 or sections[0].skill != skill:
        return []
    parts = list(sections[0].parts.filter(is_active=True).order_by("order"))
    if not parts:
        return []
    seen = set()
    for part in parts:
        assignments = list(part.question_assignments.filter(question__is_active=True)
                           .select_related("question", "question__stimulus")
                           .order_by("order"))
        if not assignments or any(a.question.skill != skill for a in assignments):
            return []
        # The shared runner requires each question to appear once per attempt.
        ids = {a.question_id for a in assignments}
        if seen.intersection(ids):
            return []
        seen.update(ids)
        if skill == "listening" and any(
            not (a.question.prompt_audio or
                 (a.question.stimulus and a.question.stimulus.audio_file))
            for a in assignments
        ):
            return []
        part.mock_question_count = min(part.question_count or len(assignments), len(assignments))
    return parts


@login_required
def hub(request):
    tests = {t.slug: t for t in MockTest.objects.select_related("program")
             .filter(slug__in=SLUGS.values(), is_published=True)}
    active = active_mock(request.user)
    rows = []
    for skill in SKILLS:
        test = tests.get(SLUGS[skill])
        parts = contents(test) if test else []
        resume = bool(active and test and active.mock_test_id == test.pk)
        rows.append({
            "key": skill, "label": skill.title(), "parts": len(parts),
            "questions": sum(p.mock_question_count for p in parts),
            "available": bool(parts) and (not active or resume),
            "action": "RESUME" if resume else ("START" if parts and not active else "UNAVAILABLE"),
            "url": reverse("attempts:dispatch", args=[active.pk]) if resume else
                   (reverse("assessments:test_detail", args=[test.slug]) if test else ""),
        })
    return render(request, "skill_mock/hub.html", {"rows": rows, "active_mock": active})


def detail(request, test, error=""):
    parts = contents(test)
    return render(request, "skill_mock/detail.html", {
        "mock_test": test, "skill": skill_for_test(test), "parts": parts,
        "total": sum(p.mock_question_count for p in parts),
        "active_mock": active_mock(request.user), "error": error,
    }, status=409 if error else 200)


@transaction.atomic
def start(request, test):
    # Serialize mock starts per learner on databases supporting row locks.
    # A repeated click resumes the same attempt, including across skill links.
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    active = active_mock(request.user)
    if active:
        return redirect("attempts:dispatch", attempt_id=active.pk)
    if not contents(test):
        return detail(request, test, "This mock is not ready yet. Please contact your instructor.")
    attempt = create_attempt_for_test(user=request.user, mock_test=test)
    attempt.metadata = {
        "practice_mode": "skill_mock", "mock_skill": skill_for_test(test),
        "mock_version": "v29", "single_test": True,
    }
    attempt.save(update_fields=["metadata"])
    return redirect("attempts:dispatch", attempt_id=attempt.pk)


def validate_objective(item, payload):
    """Reject blank/foreign selections rather than consuming a mock question."""
    question = item.question
    if question.question_type in ("single_choice", "multiple_choice"):
        values = ([payload.get("option", "")] if question.question_type == "single_choice"
                  else payload.getlist("options"))
        allowed = {str(pk) for pk in question.options.values_list("pk", flat=True)}
        if not values or any(str(value) not in allowed for value in values):
            return HttpResponseBadRequest("Select an answer from this question before continuing.")
    elif question.question_type in ("short_answer", "gap_fill"):
        if not str(payload.get("text", "")).strip():
            return HttpResponseBadRequest("Enter an answer before continuing.")
    return None


def queue_review(response, task):
    """A broker outage must not discard an answer or strand the mock runner."""
    try:
        task.delay(response.pk)
    except Exception:
        logging.getLogger(__name__).exception("Mock answer saved, but review could not be queued")
        StudentResponse.objects.filter(pk=response.pk).update(
            review_status=StudentResponse.ReviewStatus.PENDING,
            ai_feedback={"status": "queue_unavailable", "summary": "Answer saved. Instructor review is needed because automatic review is temporarily unavailable."},
        )


def results(request, attempt):
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:dispatch", attempt_id=attempt.pk)
    responses = list(StudentResponse.objects.filter(attempt_question__attempt=attempt)
                     .select_related("attempt_question__question", "attempt_question__part")
                     .order_by("attempt_question__order"))
    pending = any(r.final_score is None or r.review_status in (
        StudentResponse.ReviewStatus.PENDING, StudentResponse.ReviewStatus.AI_QUEUED,
    ) for r in responses)
    score = sum((r.final_score or Decimal("0") for r in responses), Decimal("0"))
    if not pending and attempt.status in (TestAttempt.Status.SUBMITTED, TestAttempt.Status.GRADING, TestAttempt.Status.COMPLETED):
        attempt.status = TestAttempt.Status.COMPLETED
        attempt.overall_score = score
        attempt.completed_at = attempt.completed_at or timezone.now()
        attempt.save(update_fields=["status", "overall_score", "completed_at"])
    return render(request, "skill_mock/results.html", {
        "attempt": attempt, "skill": skill_for_test(attempt.mock_test),
        "responses": responses, "pending": pending, "score": score,
        "answered": len(responses), "total": attempt.attempt_questions.count(),
    })
