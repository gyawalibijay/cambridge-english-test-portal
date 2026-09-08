"""Student-facing Cambridge Full Mock centre backed by the Part 1 builder."""
from __future__ import annotations
import re

from collections import Counter

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from attempts.full_mock_v35_part2 import is_continuous_full_mock
from attempts.models import TestAttempt
from attempts.services import create_attempt_for_test
from question_bank.models import AcceptableAnswer, OrderingItem, QuestionOption

from .models import MockTest

SKILLS = ("reading", "listening", "speaking", "writing")
PARTS = {"reading": 5, "listening": 5, "speaking": 5, "writing": 2}
MINUTES = {"reading": 25, "listening": 25, "speaking": 12, "writing": 30}


def _is_cambridge(test):
    values = [str(test.program)]
    for name in ("code", "name", "short_name"):
        values.append(str(getattr(test.program, name, "") or ""))
    text = " ".join(values).lower()
    return ("cambridge" in text or "general english" in text or "upskill" in text) and not any(
        token in text for token in ("ielts", "ukvi", "interview")
    )


def _candidate_queryset(published_only=True):
    qs = MockTest.objects.select_related("program").filter(delivery_mode="full_mock")
    if published_only:
        qs = qs.filter(is_published=True)
    return qs.order_by("pk")


def _has_key(question):
    qtype = str(question.question_type)
    if qtype in {"single_choice", "multiple_choice"}:
        return QuestionOption.objects.filter(question=question, is_correct=True).exists()
    if qtype in {"short_answer", "gap_fill"}:
        return AcceptableAnswer.objects.filter(question=question).exclude(answer_text="").exists()
    if qtype == "ordering":
        return OrderingItem.objects.filter(question=question).count() >= 2
    return True


def readiness(test):
    errors = []
    if not _is_cambridge(test):
        return {"ready": False, "errors": ["This is not the Cambridge / General English program."], "sections": []}
    sections = list(test.sections.order_by("order"))
    if [str(section.skill).lower() for section in sections] != list(SKILLS):
        errors.append("The section order must be Reading → Listening → Speaking → Writing.")

    rows = []
    all_ids = []
    for position, skill in enumerate(SKILLS, start=1):
        section = next((s for s in sections if str(s.skill).lower() == skill), None)
        if section is None:
            errors.append(f"{skill.title()}: section missing.")
            continue
        parts = list(section.parts.filter(is_active=True).order_by("order"))
        if len(parts) != PARTS[skill] or [part.order for part in parts] != list(range(1, PARTS[skill] + 1)):
            errors.append(f"{skill.title()}: expected exactly {PARTS[skill]} active Parts in order.")
        question_total = 0
        for part in parts:
            assignments = list(
                part.question_assignments.filter(question__is_active=True)
                .select_related("question", "question__stimulus")
                .order_by("order", "pk")
            )
            if not assignments:
                errors.append(f"{skill.title()} Part {part.order}: no questions assigned.")
                continue
            question_total += len(assignments)
            orders = [a.order for a in assignments]
            if len(orders) != len(set(orders)):
                errors.append(f"{skill.title()} Part {part.order}: duplicate placement order.")
            for assignment in assignments:
                question = assignment.question
                all_ids.append(question.pk)
                if str(question.skill).lower() != skill:
                    errors.append(f"{skill.title()} Part {part.order}: '{question.title}' belongs to another skill.")
                if skill == "listening":
                    audio = bool(question.prompt_audio or (question.stimulus and question.stimulus.audio_file))
                    if not audio:
                        errors.append(f"Listening Part {part.order}: '{question.title}' has no playable audio.")
                # B1_FULL_MOCK_SPEAKING_AUDIO_GATE_V38_6
                if skill == "speaking":
                    title_match = re.match(r"^Speaking S\d+ P([12]) Q\d+$", question.title or "", re.I)
                    if title_match:
                        field = getattr(question, "prompt_audio", None)
                        name = getattr(field, "name", "") if field else ""
                        audio = bool(name)
                        if audio:
                            try:
                                audio = bool(field.storage.exists(name))
                            except Exception:
                                audio = False
                        if not audio:
                            errors.append(
                                f"Speaking Part {part.order}: '{question.title}' needs uploaded physical question audio; browser voice fallback is disabled."
                            )
                # /B1_FULL_MOCK_SPEAKING_AUDIO_GATE_V38_6
                if skill in {"reading", "listening"} and not _has_key(question):
                    errors.append(f"{skill.title()} Part {part.order}: '{question.title}' has no detectable answer key.")
        rows.append({
            "section": section,
            "skill": skill,
            "label": skill.title(),
            "parts": len(parts),
            "questions": question_total,
            "minutes": MINUTES[skill],
            "order": position,
        })

    duplicates = [pk for pk, count in Counter(all_ids).items() if count > 1]
    if duplicates:
        errors.append(
            "One or more Question records are assigned more than once inside this Full Mock. "
            "Each question must appear only once in a single attempt."
        )
    return {"ready": not errors, "errors": errors, "sections": rows, "questions": len(all_ids)}


# B1_MOCK_HUB_CLEANUP_V35_7
# Only Part-1 builder-created Full Mocks belong on the continuous student hub.
# Legacy one-skill mocks are intentionally excluded so they do not reappear as
# duplicate Reading / Listening / Speaking / Writing boxes.
def _is_builder_full_mock(test):
    title = str(getattr(test, "title", "") or "").strip().lower()
    slug = str(getattr(test, "slug", "") or "").strip().lower()
    return slug.startswith("cambridge-full-mock-") or title.startswith("cambridge full mock test")


def _published_mocks():
    result = []
    for test in _candidate_queryset(True):
        if not _is_builder_full_mock(test):
            continue
        skills = tuple(str(value).lower() for value in test.sections.order_by("order").values_list("skill", flat=True))
        if skills != SKILLS:
            continue
        state = readiness(test)
        if _is_cambridge(test):
            result.append((test, state))
    return result


def _active(user):
    for attempt in (
        TestAttempt.objects.select_related("mock_test", "mock_test__program")
        .filter(user=user, status=TestAttempt.Status.IN_PROGRESS, mock_test__delivery_mode="full_mock")
        .order_by("-started_at", "-pk")
    ):
        if is_continuous_full_mock(attempt):
            return attempt
    return None


# B1_FULL_MOCK_REPEAT_READY_V40_7_2 START
def _b1_v4072_next_ready_mock(user, published):
    # Rotate only among READY Full Mocks. Never select incomplete source content.
    ready = [
        (test, state)
        for test, state in published
        if state.get("ready")
        and not str(getattr(test, "slug", "") or "").startswith(
            "cambridge-full-mock-rotation-"
        )
    ]
    ready.sort(key=lambda pair: (pair[0].pk, str(pair[0].slug)))

    if not ready:
        return None, None

    ids = [test.pk for test, _state in ready]
    latest = (
        TestAttempt.objects
        .filter(user=user, mock_test_id__in=ids)
        .select_related("mock_test")
        .order_by("-started_at", "-pk")
        .first()
    )

    if latest is None or len(ready) == 1:
        return ready[0]

    current_index = next(
        (
            index
            for index, (test, _state) in enumerate(ready)
            if test.pk == latest.mock_test_id
        ),
        -1,
    )

    return ready[(current_index + 1) % len(ready)]


@login_required
def hub(request):
    active = _active(request.user)
    published = _published_mocks()

    primary_test = None
    primary_state = None

    if active:
        primary_test = active.mock_test
        primary_state = readiness(primary_test)
    else:
        primary_test, primary_state = _b1_v4072_next_ready_mock(
            request.user,
            published,
        )

        if primary_test is None and published:
            primary_test, primary_state = published[0]

    section_map = {
        str(row.get("skill", "")).lower(): row
        for row in (primary_state or {}).get("sections", [])
    }

    skill_cards = []
    for order, skill in enumerate(SKILLS, start=1):
        row = section_map.get(skill, {})
        skill_cards.append({
            "key": skill,
            "label": skill.title(),
            "parts": row.get("parts", PARTS[skill]),
            "minutes": row.get("minutes", MINUTES[skill]),
            "questions": row.get("questions", 0),
            "order": order,
        })

    from attempts.full_mock_v35_part3 import history_rows
    history = history_rows(request.user)

    return render(request, "full_mock_v35/hub.html", {
        "active": active,
        "history": history,
        "primary_test": primary_test,
        "primary_state": primary_state,
        "skill_cards": skill_cards,
    })
# B1_FULL_MOCK_REPEAT_READY_V40_7_2 END

@login_required
def detail(request, slug, error=""):
    test = get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        delivery_mode="full_mock",
        is_published=True,
    )
    state = readiness(test)
    active = _active(request.user)
    return render(request, "full_mock_v35/detail.html", {
        "mock_test": test,
        "state": state,
        "active": active,
        "own_active": bool(active and active.mock_test_id == test.pk),
        "error": error,
        "total_minutes": sum(row["minutes"] for row in state["sections"]) if state["sections"] else 92,
    }, status=409 if error else 200)


@login_required
@require_POST
@transaction.atomic
def start(request, slug):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    test = get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        delivery_mode="full_mock",
        is_published=True,
    )
    state = readiness(test)
    if not state["ready"]:
        return detail(request, slug, "This Full Mock needs an admin content review before students can start it.")

    active = _active(request.user)
    if active and request.POST.get("restart") != "1":
        return redirect("attempts:dispatch", attempt_id=active.pk)
    if active and request.POST.get("restart") == "1":
        active.status = TestAttempt.Status.CANCELLED
        active.save(update_fields=["status"])

    attempt = create_attempt_for_test(user=request.user, mock_test=test)
    if not attempt.attempt_questions.exists():
        attempt.delete()
        return detail(request, slug, "No deliverable questions were found in this Full Mock.")

    metadata = dict(attempt.metadata or {})
    metadata.update({
        "practice_mode": "full_mock",
        "full_mock_part2_version": "35.1",
        "full_mock_exact_order": True,
        "full_mock_section_order": list(SKILLS),
    })
    attempt.metadata = metadata
    attempt.save(update_fields=["metadata"])
    return redirect("attempts:dispatch", attempt_id=attempt.pk)
