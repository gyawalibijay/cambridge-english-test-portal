"""Cambridge Full Mock Part 2: transitions, authoritative section timers and expiry."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import StudentResponse, TestAttempt
from .services import next_unanswered_question

VERSION = "35.1"
META_KEY = "full_mock_v35_part2"
SKILL_ORDER = ("reading", "listening", "speaking", "writing")
FALLBACK_SECONDS = {
    "reading": 25 * 60,
    "listening": 25 * 60,
    "speaking": 12 * 60,
    "writing": 30 * 60,
}


def is_continuous_full_mock(attempt):
    """True only for multi-section Full Mocks, never the legacy single-skill mocks."""
    if getattr(attempt.mock_test, "delivery_mode", "") != "full_mock":
        return False
    if (attempt.metadata or {}).get("practice_mode") == "skill_mock":
        return False
    try:
        sections = list(attempt.mock_test.sections.order_by("order").values_list("skill", flat=True))
    except Exception:
        return False
    return len(sections) == 4 and tuple(str(x).lower() for x in sections) == SKILL_ORDER


def section_seconds(section):
    value = int(getattr(section, "duration_seconds", 0) or 0)
    if value > 0:
        return max(60, min(value, 3 * 60 * 60))
    return FALLBACK_SECONDS.get(str(getattr(section, "skill", "")).lower(), 15 * 60)


def _root(attempt):
    metadata = dict(attempt.metadata or {})
    root = metadata.get(META_KEY)
    if not isinstance(root, dict):
        root = {}
    timers = root.get("section_timers")
    if not isinstance(timers, dict):
        timers = {}
    root["section_timers"] = timers
    root["version"] = VERSION
    metadata[META_KEY] = root
    return metadata, root, timers


def timer_state(attempt, section):
    metadata, root, timers = _root(attempt)
    entry = timers.get(str(section.pk))
    if not isinstance(entry, dict):
        return None
    try:
        deadline = float(entry.get("deadline"))
    except (TypeError, ValueError):
        return None
    try:
        duration = int(entry.get("duration") or section_seconds(section))
    except (TypeError, ValueError):
        duration = section_seconds(section)
    now_ts = timezone.now().timestamp()
    remaining_ms = max(0, int(round((deadline - now_ts) * 1000)))
    return {
        "deadline": deadline,
        "duration_seconds": duration,
        "remaining_ms": remaining_ms,
        "remaining_seconds": (remaining_ms + 999) // 1000,
        "started_at": entry.get("started_at"),
        "finished_at": entry.get("finished_at"),
    }


@transaction.atomic
def start_section(attempt, section):
    locked = TestAttempt.objects.select_for_update().select_related("mock_test").get(pk=attempt.pk)
    if locked.status != TestAttempt.Status.IN_PROGRESS:
        return locked, None
    metadata, root, timers = _root(locked)
    key = str(section.pk)
    entry = timers.get(key)
    if not isinstance(entry, dict) or not entry.get("deadline"):
        now = timezone.now()
        duration = section_seconds(section)
        entry = {
            "skill": str(section.skill),
            "section_id": section.pk,
            "started_at": now.isoformat(),
            "deadline": now.timestamp() + duration,
            "duration": duration,
        }
        timers[key] = entry
        root["active_section_id"] = section.pk
        metadata[META_KEY] = root
        locked.metadata = metadata
        locked.save(update_fields=["metadata"])
    return locked, timer_state(locked, section)


def _timeout_defaults(item, section):
    data = {
        "answer_data": {
            "timed_out": True,
            "reason": "full_mock_section_timer_expired",
            "section_id": section.pk,
            "skill": str(section.skill),
        },
        "final_score": Decimal("0.00"),
        "review_status": StudentResponse.ReviewStatus.AUTO_GRADED,
    }
    qtype = str(getattr(item.question, "question_type", ""))
    if qtype in {"single_choice", "multiple_choice", "short_answer", "gap_fill", "ordering"}:
        data.update({"is_correct": False, "auto_score": Decimal("0.00")})
    return data


@transaction.atomic
def expire_section(attempt, section):
    locked = TestAttempt.objects.select_for_update().select_related("mock_test").get(pk=attempt.pk)
    if locked.status != TestAttempt.Status.IN_PROGRESS:
        return 0
    unanswered = list(
        locked.attempt_questions
        .filter(part__section=section, response__isnull=True)
        .select_related("question", "part")
        .order_by("order")
    )
    expired = 0
    for item in unanswered:
        _, created = StudentResponse.objects.get_or_create(
            attempt_question=item,
            defaults=_timeout_defaults(item, section),
        )
        expired += int(created)

    metadata, root, timers = _root(locked)
    key = str(section.pk)
    entry = timers.get(key)
    if not isinstance(entry, dict):
        entry = {
            "skill": str(section.skill),
            "section_id": section.pk,
            "duration": section_seconds(section),
        }
    entry["finished_at"] = timezone.now().isoformat()
    entry["expired"] = True
    entry["timed_out_questions"] = expired
    timers[key] = entry
    root["active_section_id"] = None
    metadata[META_KEY] = root
    locked.metadata = metadata
    locked.save(update_fields=["metadata"])
    return expired


@transaction.atomic
def sync_completed_sections(attempt):
    locked = TestAttempt.objects.select_for_update().select_related("mock_test").get(pk=attempt.pk)
    if not is_continuous_full_mock(locked):
        return locked
    metadata, root, timers = _root(locked)
    changed = False
    for section in locked.mock_test.sections.order_by("order"):
        key = str(section.pk)
        entry = timers.get(key)
        if not isinstance(entry, dict) or not entry.get("deadline") or entry.get("finished_at"):
            continue
        if not locked.attempt_questions.filter(part__section=section, response__isnull=True).exists():
            entry["finished_at"] = timezone.now().isoformat()
            entry["expired"] = False
            timers[key] = entry
            if root.get("active_section_id") == section.pk:
                root["active_section_id"] = None
            changed = True
    if changed:
        metadata[META_KEY] = root
        locked.metadata = metadata
        locked.save(update_fields=["metadata"])
    return locked


def prepare_item(attempt, item):
    """Return gate/run/expired for the current question's section."""
    if not is_continuous_full_mock(attempt):
        return {"action": "practice"}
    section = item.part.section
    state = timer_state(attempt, section)
    if state is None:
        return {"action": "gate", "section": section}
    if state["remaining_ms"] <= 0:
        expire_section(attempt, section)
        return {"action": "expired", "section": section}
    return {"action": "run", "section": section, "timer": state}


def gate_url(attempt):
    return reverse("attempts:full_mock_section", kwargs={"attempt_id": attempt.pk})


def _owned(request, attempt_id):
    qs = TestAttempt.objects.select_related("mock_test", "mock_test__program")
    if request.user.is_staff:
        return get_object_or_404(qs, pk=attempt_id)
    return get_object_or_404(qs, pk=attempt_id, user=request.user)


def _finish_empty(attempt):
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        attempt.status = TestAttempt.Status.SUBMITTED
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])


def _section_rows(attempt, current_section):
    rows = []
    for section in attempt.mock_test.sections.order_by("order"):
        total = attempt.attempt_questions.filter(part__section=section).count()
        answered = StudentResponse.objects.filter(
            attempt_question__attempt=attempt,
            attempt_question__part__section=section,
        ).count()
        rows.append({
            "section": section,
            "total": total,
            "answered": answered,
            "complete": bool(total and answered >= total),
            "current": section.pk == current_section.pk,
            "duration_minutes": max(1, round(section_seconds(section) / 60)),
        })
    return rows


@login_required
@require_http_methods(["GET", "POST"])
def section_gate(request, attempt_id):
    attempt = _owned(request, attempt_id)
    if not is_continuous_full_mock(attempt):
        return redirect("attempts:dispatch", attempt_id=attempt.pk)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("attempts:complete", attempt_id=attempt.pk)

    sync_completed_sections(attempt)
    attempt.refresh_from_db(fields=["metadata", "status"])
    item = next_unanswered_question(attempt)
    if item is None:
        _finish_empty(attempt)
        return redirect("attempts:complete", attempt_id=attempt.pk)
    section = item.part.section
    state = timer_state(attempt, section)

    if state is not None and state["remaining_ms"] <= 0:
        expire_section(attempt, section)
        return redirect("attempts:dispatch", attempt_id=attempt.pk)
    if state is not None:
        return redirect("attempts:dispatch", attempt_id=attempt.pk)

    if request.method == "POST":
        start_section(attempt, section)
        return redirect("attempts:dispatch", attempt_id=attempt.pk)

    rows = _section_rows(attempt, section)
    previous = next((row for row in reversed(rows[: max(0, section.order - 1)]) if row["complete"]), None)
    return render(request, "full_mock_v35/transition.html", {
        "attempt": attempt,
        "section": section,
        "rows": rows,
        "previous": previous,
        "duration_minutes": max(1, round(section_seconds(section) / 60)),
        "section_number": section.order,
        "section_total": len(rows),
    })


@login_required
@require_http_methods(["GET"])
def timer_json(request, attempt_id):
    attempt = _owned(request, attempt_id)
    if not is_continuous_full_mock(attempt) or attempt.status != TestAttempt.Status.IN_PROGRESS:
        return JsonResponse({"active": False, "complete": True})
    item = next_unanswered_question(attempt)
    if item is None:
        _finish_empty(attempt)
        return JsonResponse({
            "active": False,
            "complete": True,
            "next_url": reverse("attempts:complete", args=[attempt.pk]),
        })
    result = prepare_item(attempt, item)
    if result["action"] == "gate":
        return JsonResponse({
            "active": False,
            "gate": True,
            "next_url": gate_url(attempt),
        })
    if result["action"] == "expired":
        return JsonResponse({
            "active": False,
            "expired": True,
            "next_url": reverse("attempts:dispatch", args=[attempt.pk]),
        })
    timer = result["timer"]
    return JsonResponse({
        "active": True,
        "section_id": result["section"].pk,
        "skill": str(result["section"].skill),
        "remaining_ms": timer["remaining_ms"],
        "duration_seconds": timer["duration_seconds"],
    })
