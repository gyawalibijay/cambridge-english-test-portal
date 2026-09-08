from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from attempts.services import create_attempt_for_test

from .models import MockTest, Program


@login_required
def program_detail(request, code):
    program = get_object_or_404(Program, code=code, is_active=True)
    tests = program.mock_tests.filter(is_published=True).order_by("title")
    return render(
        request,
        "assessments/program_detail.html",
        {"program": program, "tests": tests},
    )


@login_required
def test_detail(request, slug):
    mock_test = get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        is_published=True,
    )
    sections = mock_test.sections.prefetch_related("parts").order_by("order")
    return render(
        request,
        "assessments/test_detail.html",
        {"mock_test": mock_test, "sections": sections},
    )


@login_required
@require_POST
def start_test(request, slug):
    mock_test = get_object_or_404(MockTest, slug=slug, is_published=True)
    attempt = create_attempt_for_test(user=request.user, mock_test=mock_test)

    if not attempt.attempt_questions.exists():
        attempt.delete()
        return redirect("assessments:test_detail", slug=mock_test.slug)

    return redirect("attempts:dispatch", attempt_id=attempt.pk)

@login_required
def cambridge_dashboard(request):
    from attempts.models import TestAttempt
    from assessments.models import MockTest

    program = get_object_or_404(
        Program,
        code="cambridge-general",
        is_active=True,
    )

    section_specs = [
        {
            "key": "speaking",
            "title": "Speaking",
            "parts": 5,
            "minutes": 12,
            "slug": "cambridge-speaking-practice-1",
        },
        {
            "key": "listening",
            "title": "Listening",
            "parts": 5,
            "minutes": 25,
            "slug": "cambridge-listening-practice-1",
        },
        {
            "key": "reading",
            "title": "Reading",
            "parts": 5,
            "minutes": 25,
            "slug": "cambridge-reading-source-samples",
        },
        {
            "key": "writing",
            "title": "Writing",
            "parts": 2,
            "minutes": 30,
            "slug": "cambridge-writing-source-samples",
        },
    ]

    cards = []

    for spec in section_specs:
        test = None

        if spec["slug"]:
            test = MockTest.objects.filter(
                slug=spec["slug"],
                program=program,
                is_published=True,
            ).first()

        completed = False
        in_progress = False
        latest_attempt = None

        if test:
            latest_attempt = (
                TestAttempt.objects
                .filter(user=request.user, mock_test=test)
                .order_by("-started_at")
                .first()
            )

            if latest_attempt:
                in_progress = (
                    latest_attempt.status
                    == TestAttempt.Status.IN_PROGRESS
                )

                completed = latest_attempt.status in {
                    TestAttempt.Status.SUBMITTED,
                    TestAttempt.Status.GRADING,
                    TestAttempt.Status.COMPLETED,
                }

        cards.append(
            {
                **spec,
                "test": test,
                "completed": completed,
                "in_progress": in_progress,
                "latest_attempt": latest_attempt,
            }
        )

    total_minutes = sum(item["minutes"] for item in section_specs)

    return render(
        request,
        "assessments/cambridge_dashboard.html",
        {
            "program": program,
            "cards": cards,
            "total_minutes": total_minutes,
        },
    )

# === CAMBRIDGE DESIGN PACK SECTION HUB OVERRIDE ===
@login_required
def cambridge_dashboard(request):
    from attempts.models import TestAttempt
    from assessments.models import MockTest, Program

    program = get_object_or_404(Program, code="cambridge-general", is_active=True)

    specs = [
        ("speaking", "Speaking", 5, 12, ["cambridge-speaking-practice-1"]),
        ("listening", "Listening", 5, 25, ["cambridge-listening-practice-1"]),
        ("reading", "Reading", 5, 25, ["cambridge-reading-practice-1", "cambridge-reading-source-samples"]),
        ("writing", "Writing", 2, 30, ["cambridge-writing-practice-1", "cambridge-writing-source-samples"]),
    ]

    cards = []

    for key, title, expected_parts, minutes, candidates in specs:
        test = None
        for slug in candidates:
            test = MockTest.objects.filter(program=program, slug=slug, is_published=True).first()
            if test:
                break

        latest = None
        completed = False
        in_progress = False
        parts = []

        if test:
            latest = TestAttempt.objects.filter(
                user=request.user,
                mock_test=test,
            ).order_by("-started_at").first()

            if latest:
                in_progress = latest.status == TestAttempt.Status.IN_PROGRESS
                completed = latest.status in {
                    TestAttempt.Status.SUBMITTED,
                    TestAttempt.Status.GRADING,
                    TestAttempt.Status.COMPLETED,
                }

            section = test.sections.prefetch_related("parts").order_by("order").first()
            if section:
                parts = list(section.parts.filter(is_active=True).order_by("order"))

        cards.append({
            "key": key,
            "title": title,
            "expected_parts": expected_parts,
            "minutes": minutes,
            "test": test,
            "latest": latest,
            "completed": completed,
            "in_progress": in_progress,
            "parts": parts,
        })

    return render(
        request,
        "assessments/cambridge_dashboard.html",
        {
            "program": program,
            "cards": cards,
            "total_minutes": 92,
        },
    )

# === CAMBRIDGE DESIGN PACK TEST DETAIL OVERRIDE ===
@login_required
def test_detail(request, slug):
    from attempts.models import TestAttempt
    from question_bank.models import PartQuestion

    mock_test = get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        is_published=True,
    )

    sections = list(
        mock_test.sections.prefetch_related("parts").order_by("order")
    )
    section = sections[0] if sections else None
    skill = section.skill if section else ""

    in_progress = TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    ).order_by("-started_at").first()

    completed_attempt = TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
    ).exclude(status=TestAttempt.Status.IN_PROGRESS).order_by("-started_at").first()

    sample_audio_url = ""

    first_assignment = (
        PartQuestion.objects
        .filter(part__section__mock_test=mock_test)
        .select_related("question__stimulus")
        .order_by("part__order", "order")
        .first()
    )

    if first_assignment:
        question = first_assignment.question
        if question.prompt_audio:
            sample_audio_url = question.prompt_audio.url
        elif question.stimulus and question.stimulus.audio_file:
            sample_audio_url = question.stimulus.audio_file.url

    return render(
        request,
        "assessments/test_detail.html",
        {
            "mock_test": mock_test,
            "sections": sections,
            "section": section,
            "skill": skill,
            "in_progress": in_progress,
            "completed_attempt": completed_attempt,
            "sample_audio_url": sample_audio_url,
        },
    )

# === PRACTICE RESUME + PART INSTRUCTION FLOW V3 START ===
from django.contrib.auth.decorators import login_required as _pf_login_required
from django.shortcuts import get_object_or_404 as _pf_get_object_or_404
from django.shortcuts import redirect as _pf_redirect
from django.shortcuts import render as _pf_render
from django.urls import reverse as _pf_reverse
from django.views.decorators.http import require_POST as _pf_require_POST


def _pf_int(value, default=1):
    try:
        value = int(value)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _pf_instruction(skill, part_number):
    skill = str(skill or "").lower()

    speaking = {
        1: {
            "title": "Speaking Part 1",
            "bullets": [
                "You will hear 4 questions. Listen and answer each question.",
                "For each question, you will have 10 seconds to speak.",
            ],
        },
        2: {
            "title": "Speaking Part 2",
            "bullets": [
                "You will hear 4 questions. Listen and give a longer answer to each question.",
                "For each question, you will have 20 seconds to speak.",
            ],
        },
        3: {
            "title": "Speaking Part 3",
            "bullets": [
                "You will read 4 sentences aloud.",
                "For each sentence, you will have 10 seconds to speak.",
            ],
        },
        4: {
            "title": "Speaking Part 4",
            "bullets": [
                "You will read 4 extended sentences aloud.",
                "For each sentence, you will have 10 seconds to speak.",
            ],
        },
        5: {
            "title": "Speaking Part 5",
            "bullets": [
                "You will leave a spoken message based on the situation provided.",
                "You will have 40 seconds to prepare and at least 1 minute to speak.",
            ],
        },
    }

    if skill == "speaking":
        return speaking.get(part_number, speaking[1])

    if skill == "listening":
        return {
            "title": f"Listening Part {part_number}",
            "bullets": [
                "Listen carefully to the audio and answer the questions in this part.",
                "Follow the instructions shown for each question before submitting your answer.",
            ],
        }

    if skill == "reading":
        return {
            "title": f"Reading Part {part_number}",
            "bullets": [
                "Read the text carefully and answer the questions in this part.",
                "Work through the questions under the displayed time limit.",
            ],
        }

    return {
        "title": f"Writing Part {part_number}",
        "bullets": [
            "Read the writing task carefully before you begin.",
            "Complete the task using the word-count requirement shown in the test.",
        ],
    }


def _pf_attempt_matches(attempt, skill, part_number, set_number):
    metadata = getattr(attempt, "metadata", None) or {}
    if not isinstance(metadata, dict):
        return True

    # Older in-progress attempts may not yet carry practice metadata.
    if not any(k in metadata for k in ("practice_skill", "practice_part", "practice_set")):
        return True

    return (
        str(metadata.get("practice_skill", "")).lower() == str(skill).lower()
        and int(metadata.get("practice_part", part_number) or part_number) == part_number
        and int(metadata.get("practice_set", set_number) or set_number) == set_number
    )


@_pf_login_required
def test_detail(request, slug):
    from attempts.models import TestAttempt
    from .models import MockTest

    mock_test = _pf_get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        is_published=True,
    )

    sections = list(
        mock_test.sections.prefetch_related("parts").order_by("order")
    )
    section = sections[0] if sections else None
    skill = str(getattr(section, "skill", "speaking") or "speaking").lower()
    skill_label = skill.capitalize()

    selected_part_number = _pf_int(request.GET.get("part"), 1)
    selected_set_number = _pf_int(request.GET.get("set"), 1)

    in_progress_qs = TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    ).order_by("-started_at")

    matching_attempts = [
        a for a in in_progress_qs
        if _pf_attempt_matches(
            a,
            skill,
            selected_part_number,
            selected_set_number,
        )
    ]

    if request.GET.get("restart") == "1":
        for attempt in matching_attempts:
            attempt.status = TestAttempt.Status.CANCELLED
            attempt.save(update_fields=["status"])
        matching_attempts = []

    in_progress = matching_attempts[0] if matching_attempts else None

    return _pf_render(
        request,
        "assessments/test_detail.html",
        {
            "mock_test": mock_test,
            "skill": skill,
            "skill_label": skill_label,
            "selected_part_number": selected_part_number,
            "selected_set_number": selected_set_number,
            "instruction": _pf_instruction(skill, selected_part_number),
            "resume_mode": bool(in_progress),
            "resume_url": (
                _pf_reverse("attempts:dispatch", args=[in_progress.pk])
                if in_progress
                else ""
            ),
        },
    )


@_pf_login_required
@_pf_require_POST
def start_test(request, slug):
    from decimal import Decimal

    from attempts.models import TestAttempt
    from attempts.services import create_attempt_for_test
    from .models import MockTest

    mock_test = _pf_get_object_or_404(
        MockTest,
        slug=slug,
        is_published=True,
    )

    skill = str(request.POST.get("skill") or "speaking").lower()
    part_number = _pf_int(request.POST.get("part"), 1)
    set_number = _pf_int(request.POST.get("set"), 1)

    # Do not leave duplicate in-progress attempts for the same practice selection.
    for old in TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    ).order_by("-started_at"):
        if _pf_attempt_matches(old, skill, part_number, set_number):
            old.status = TestAttempt.Status.CANCELLED
            old.save(update_fields=["status"])

    attempt = create_attempt_for_test(
        user=request.user,
        mock_test=mock_test,
    )

    selected = attempt.attempt_questions.filter(
        part__section__skill=skill,
        part__order=part_number,
    )

    if not selected.exists():
        attempt.delete()
        return _pf_redirect(
            f"/practice/test/{mock_test.slug}/?part={part_number}&set={set_number}"
        )

    attempt.attempt_questions.exclude(
        pk__in=selected.values_list("pk", flat=True)
    ).delete()

    max_score = Decimal("0")
    for item in attempt.attempt_questions.all():
        try:
            max_score += Decimal(str(item.points or 0))
        except Exception:
            pass

    attempt.max_score = max_score
    metadata = attempt.metadata if isinstance(attempt.metadata, dict) else {}
    metadata.update({
        "practice_skill": skill,
        "practice_part": part_number,
        "practice_set": set_number,
        "practice_mode": "part_set",
    })
    attempt.metadata = metadata
    attempt.save(update_fields=["max_score", "metadata"])

    return _pf_redirect(
        "attempts:dispatch",
        attempt_id=attempt.pk,
    )
# === PRACTICE RESUME + PART INSTRUCTION FLOW V3 END ===

# === PRACTICE RESUME + PART INSTRUCTION FLOW V3 START ===
from django.contrib.auth.decorators import login_required as _pf_login_required
from django.shortcuts import get_object_or_404 as _pf_get_object_or_404
from django.shortcuts import redirect as _pf_redirect
from django.shortcuts import render as _pf_render
from django.urls import reverse as _pf_reverse
from django.views.decorators.http import require_POST as _pf_require_POST


def _pf_int(value, default=1):
    try:
        value = int(value)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _pf_instruction(skill, part_number):
    skill = str(skill or "").lower()

    speaking = {
        1: {
            "title": "Speaking Part 1",
            "bullets": [
                "You will hear 4 questions. Listen and answer each question.",
                "For each question, you will have 10 seconds to speak.",
            ],
        },
        2: {
            "title": "Speaking Part 2",
            "bullets": [
                "You will hear 4 questions. Listen and give a longer answer to each question.",
                "For each question, you will have 20 seconds to speak.",
            ],
        },
        3: {
            "title": "Speaking Part 3",
            "bullets": [
                "You will read 4 sentences aloud.",
                "For each sentence, you will have 10 seconds to speak.",
            ],
        },
        4: {
            "title": "Speaking Part 4",
            "bullets": [
                "You will read 4 extended sentences aloud.",
                "For each sentence, you will have 10 seconds to speak.",
            ],
        },
        5: {
            "title": "Speaking Part 5",
            "bullets": [
                "You will leave a spoken message based on the situation provided.",
                "You will have 40 seconds to prepare and at least 1 minute to speak.",
            ],
        },
    }

    if skill == "speaking":
        return speaking.get(part_number, speaking[1])

    if skill == "listening":
        return {
            "title": f"Listening Part {part_number}",
            "bullets": [
                "Listen carefully to the audio and answer the questions in this part.",
                "Follow the instructions shown for each question before submitting your answer.",
            ],
        }

    if skill == "reading":
        return {
            "title": f"Reading Part {part_number}",
            "bullets": [
                "Read the text carefully and answer the questions in this part.",
                "Work through the questions under the displayed time limit.",
            ],
        }

    return {
        "title": f"Writing Part {part_number}",
        "bullets": [
            "Read the writing task carefully before you begin.",
            "Complete the task using the word-count requirement shown in the test.",
        ],
    }


def _pf_attempt_matches(attempt, skill, part_number, set_number):
    metadata = getattr(attempt, "metadata", None) or {}
    if not isinstance(metadata, dict):
        return True

    # Older in-progress attempts may not yet carry practice metadata.
    if not any(k in metadata for k in ("practice_skill", "practice_part", "practice_set")):
        return True

    return (
        str(metadata.get("practice_skill", "")).lower() == str(skill).lower()
        and int(metadata.get("practice_part", part_number) or part_number) == part_number
        and int(metadata.get("practice_set", set_number) or set_number) == set_number
    )


@_pf_login_required
def test_detail(request, slug):
    from attempts.models import TestAttempt
    from .models import MockTest

    mock_test = _pf_get_object_or_404(
        MockTest.objects.select_related("program"),
        slug=slug,
        is_published=True,
    )

    sections = list(
        mock_test.sections.prefetch_related("parts").order_by("order")
    )
    section = sections[0] if sections else None
    skill = str(getattr(section, "skill", "speaking") or "speaking").lower()
    skill_label = skill.capitalize()

    selected_part_number = _pf_int(request.GET.get("part"), 1)
    selected_set_number = _pf_int(request.GET.get("set"), 1)

    in_progress_qs = TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    ).order_by("-started_at")

    matching_attempts = [
        a for a in in_progress_qs
        if _pf_attempt_matches(
            a,
            skill,
            selected_part_number,
            selected_set_number,
        )
    ]

    if request.GET.get("restart") == "1":
        for attempt in matching_attempts:
            attempt.status = TestAttempt.Status.CANCELLED
            attempt.save(update_fields=["status"])
        matching_attempts = []

    in_progress = matching_attempts[0] if matching_attempts else None

    return _pf_render(
        request,
        "assessments/test_detail.html",
        {
            "mock_test": mock_test,
            "skill": skill,
            "skill_label": skill_label,
            "selected_part_number": selected_part_number,
            "selected_set_number": selected_set_number,
            "instruction": _pf_instruction(skill, selected_part_number),
            "resume_mode": bool(in_progress),
            "resume_url": (
                _pf_reverse("attempts:dispatch", args=[in_progress.pk])
                if in_progress
                else ""
            ),
        },
    )


@_pf_login_required
@_pf_require_POST
def start_test(request, slug):
    from decimal import Decimal

    from attempts.models import TestAttempt
    from attempts.services import create_attempt_for_test
    from .models import MockTest

    mock_test = _pf_get_object_or_404(
        MockTest,
        slug=slug,
        is_published=True,
    )

    skill = str(request.POST.get("skill") or "speaking").lower()
    part_number = _pf_int(request.POST.get("part"), 1)
    set_number = _pf_int(request.POST.get("set"), 1)

    # Do not leave duplicate in-progress attempts for the same practice selection.
    for old in TestAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    ).order_by("-started_at"):
        if _pf_attempt_matches(old, skill, part_number, set_number):
            old.status = TestAttempt.Status.CANCELLED
            old.save(update_fields=["status"])

    attempt = create_attempt_for_test(
        user=request.user,
        mock_test=mock_test,
    )

    selected = attempt.attempt_questions.filter(
        part__section__skill=skill,
        part__order=part_number,
    )

    if not selected.exists():
        attempt.delete()
        return _pf_redirect(
            f"/practice/test/{mock_test.slug}/?part={part_number}&set={set_number}"
        )

    attempt.attempt_questions.exclude(
        pk__in=selected.values_list("pk", flat=True)
    ).delete()

    max_score = Decimal("0")
    for item in attempt.attempt_questions.all():
        try:
            max_score += Decimal(str(item.points or 0))
        except Exception:
            pass

    attempt.max_score = max_score
    metadata = attempt.metadata if isinstance(attempt.metadata, dict) else {}
    metadata.update({
        "practice_skill": skill,
        "practice_part": part_number,
        "practice_set": set_number,
        "practice_mode": "part_set",
    })
    attempt.metadata = metadata
    attempt.save(update_fields=["max_score", "metadata"])

    return _pf_redirect(
        "attempts:dispatch",
        attempt_id=attempt.pk,
    )
# === PRACTICE RESUME + PART INSTRUCTION FLOW V3 END ===
