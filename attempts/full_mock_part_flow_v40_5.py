from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from attempts.models import TestAttempt
from . import full_mock_v35_part2 as legacy_flow

VERSION = "40.8.3"
META_KEY = "full_mock_part_flow_v40_8_3"
OLD_KEYS = ("full_mock_part_flow_v40_5", "full_mock_part_flow_v40_4")
SKILLS = ("reading", "listening", "speaking", "writing")
LABELS = {s: s.title() for s in SKILLS}


def is_part_flow_attempt(attempt):
    return bool(legacy_flow.is_continuous_full_mock(attempt))


def _owned(request, attempt_id):
    return get_object_or_404(
        TestAttempt.objects.select_related("mock_test", "mock_test__program"),
        pk=attempt_id,
        user=request.user,
    )


def selection(attempt):
    metadata = dict(attempt.metadata or {})
    data = metadata.get(META_KEY)
    if isinstance(data, dict):
        return dict(data)
    for key in OLD_KEYS:
        data = metadata.get(key)
        if isinstance(data, dict):
            return dict(data)
    return {}


def _write(attempt, data):
    metadata = dict(attempt.metadata or {})
    for key in OLD_KEYS:
        metadata.pop(key, None)
    if data:
        metadata[META_KEY] = data
    else:
        metadata.pop(META_KEY, None)
    attempt.metadata = metadata
    attempt.save(update_fields=["metadata"])
    return attempt


def has_selection(attempt):
    return bool(selection(attempt).get("selected_part_id"))


def clear_selection(attempt):
    return _write(attempt, {})


def select_part(attempt, section, part):
    return _write(
        attempt,
        {
            "selected_skill": str(section.skill).lower(),
            "selected_section_id": section.pk,
            "selected_part_id": part.pk,
            "selected_part_order": int(part.order),
        },
    )


def selected_next(attempt):
    part_id = selection(attempt).get("selected_part_id")
    if not part_id:
        return None
    return (
        attempt.attempt_questions
        .filter(part_id=part_id, response__isnull=True)
        .select_related("question", "question__stimulus", "part", "part__section")
        .order_by("order", "pk")
        .first()
    )


def _part_counts(attempt, part):
    qs = attempt.attempt_questions.filter(part=part)
    return qs.count(), qs.filter(response__isnull=False).count()


def _all_done(attempt):
    return not attempt.attempt_questions.filter(response__isnull=True).exists()


def _finish(attempt):
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        attempt.status = TestAttempt.Status.SUBMITTED
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])
    return attempt


def _parts_url(attempt, skill):
    if skill in SKILLS:
        return reverse(
            "attempts:full_mock_parts",
            kwargs={"attempt_id": attempt.pk, "skill": skill},
        )
    return reverse("student_mock_tests")


def sync_attempt(attempt):
    if not is_part_flow_attempt(attempt):
        return attempt
    attempt.refresh_from_db(fields=["metadata", "status"])
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return attempt
    if has_selection(attempt) and selected_next(attempt) is None:
        clear_selection(attempt)
        attempt.refresh_from_db(fields=["metadata"])
    if _all_done(attempt):
        clear_selection(attempt)
        _finish(attempt)
    return attempt


def next_url_for_attempt(attempt):
    attempt.refresh_from_db(fields=["metadata", "status"])
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return reverse("attempts:complete", kwargs={"attempt_id": attempt.pk})

    data = selection(attempt)
    skill = str(data.get("selected_skill") or "").lower()
    item = selected_next(attempt)

    if item is not None:
        from . import views
        return reverse(views._route_for_item(item), kwargs={"attempt_id": attempt.pk})

    if data.get("selected_part_id"):
        clear_selection(attempt)
        if _all_done(attempt):
            _finish(attempt)
            return reverse("attempts:complete", kwargs={"attempt_id": attempt.pk})
        return _parts_url(attempt, skill)

    if _all_done(attempt):
        _finish(attempt)
        return reverse("attempts:complete", kwargs={"attempt_id": attempt.pk})

    return reverse("student_mock_tests")


def part_rows(attempt, section):
    rows=[]
    skill=str(section.skill).lower()
    for part in section.parts.filter(is_active=True).order_by("order", "pk"):
        total, answered = _part_counts(attempt, part)
        rows.append(
            {
                "part": part,
                "number": int(part.order),
                "label": f"{LABELS.get(skill, skill.title())} Part {part.order}",
                "complete": bool(total and answered >= total),
                "answered": answered,
                "total": total,
                "start_url": reverse(
                    "attempts:full_mock_part_start",
                    kwargs={
                        "attempt_id": attempt.pk,
                        "skill": skill,
                        "part_no": int(part.order),
                    },
                ),
            }
        )
    return rows


@login_required
@require_GET
def skill_parts(request, attempt_id, skill):
    skill=str(skill).lower()
    if skill not in SKILLS:
        return redirect("student_mock_tests")

    attempt=_owned(request,attempt_id)
    if not is_part_flow_attempt(attempt):
        return redirect("attempts:dispatch",attempt_id=attempt.pk)

    sync_attempt(attempt)
    attempt.refresh_from_db(fields=["metadata","status"])
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete",attempt_id=attempt.pk)

    section=attempt.mock_test.sections.filter(skill=skill).order_by("order","pk").first()
    if section is None:
        return redirect("student_mock_tests")

    clear_selection(attempt)
    return render(
        request,
        "full_mock_v35/part_selector.html",
        {
            "attempt":attempt,
            "skill_label":LABELS.get(skill,skill.title()),
            "parts":part_rows(attempt,section),
        },
    )


@login_required
@require_GET
@transaction.atomic
def start_part(request, attempt_id, skill, part_no):
    skill=str(skill).lower()
    if skill not in SKILLS:
        return redirect("student_mock_tests")

    attempt=_owned(request,attempt_id)
    if not is_part_flow_attempt(attempt):
        return redirect("attempts:dispatch",attempt_id=attempt.pk)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete",attempt_id=attempt.pk)

    section=attempt.mock_test.sections.filter(skill=skill).order_by("order","pk").first()
    if section is None:
        return redirect("student_mock_tests")

    part=section.parts.filter(is_active=True,order=int(part_no)).order_by("pk").first()
    if part is None:
        return redirect("attempts:full_mock_parts",attempt_id=attempt.pk,skill=skill)

    total,answered=_part_counts(attempt,part)
    if not total or answered>=total:
        return redirect("attempts:full_mock_parts",attempt_id=attempt.pk,skill=skill)

    select_part(attempt,section,part)
    return redirect("attempts:dispatch",attempt_id=attempt.pk)


# ------------------------------------------------------------------
# Backward-compatible endpoints still referenced by existing attempts/urls.py.
# Older V40.5/V40.6 routes call:
#   full_mock_part_flow_v40_5.overview
#   full_mock_part_flow_v40_5.parts
# V40.8.2 replaced the module but accidentally omitted those names, causing
# Django URL loading to fail with AttributeError before validation completed.
# Keep these compatibility names while preserving the new one-Part behavior.
# ------------------------------------------------------------------

@login_required
@require_GET
def overview(request, attempt_id):
    attempt = _owned(request, attempt_id)

    if not is_part_flow_attempt(attempt):
        return redirect("student_mock_tests")

    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    # There is only one skill hub now: /mock-tests/.
    # Never render the old duplicate /attempt/<id>/section/ or /mock/ hub.
    clear_selection(attempt)
    return redirect("student_mock_tests")


@login_required
@require_GET
def parts(request, attempt_id, skill):
    # Compatibility name for the old V40.5 URL route.
    # The actual implementation is the V40.8.3 Practice-style Part selector.
    return skill_parts(request, attempt_id, skill)


@login_required
@require_GET
def timer_json(request, attempt_id):
    attempt=_owned(request,attempt_id)
    data=selection(attempt) if is_part_flow_attempt(attempt) else {}
    return JsonResponse(
        {
            "active":bool(data.get("selected_part_id")),
            "skill":data.get("selected_skill"),
            "part_id":data.get("selected_part_id"),
        }
    )
