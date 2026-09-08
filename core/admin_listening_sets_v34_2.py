from __future__ import annotations

import re
import logging

from django.apps import apps
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse

Question = apps.get_model("question_bank", "Question")
Stimulus = apps.get_model("question_bank", "Stimulus")
QuestionOption = apps.get_model("question_bank", "QuestionOption")
AcceptableAnswer = apps.get_model("question_bank", "AcceptableAnswer")
OrderingItem = apps.get_model("question_bank", "OrderingItem")
PartQuestion = apps.get_model("question_bank", "PartQuestion")
MockTest = apps.get_model("assessments", "MockTest")
TestSection = apps.get_model("assessments", "TestSection")
TestPart = apps.get_model("assessments", "TestPart")

logger = logging.getLogger(__name__)

PART_GUIDE = {
    1: {
        "name": "Part 1",
        "help": "Part number classifies where this task belongs. It does not lock the question pattern.",
    },
    2: {
        "name": "Part 2",
        "help": "Choose the task pattern separately from the Part number.",
    },
    3: {
        "name": "Part 3",
        "help": "Use the pattern shown in the actual material/audio supplied for this Set.",
    },
    4: {
        "name": "Part 4",
        "help": "The administrator controls the pattern; the software no longer assumes one fixed type.",
    },
    5: {
        "name": "Part 5",
        "help": "Use the real task material as the source of truth for this Part.",
    },
}

TASK_PATTERNS = {
    "short_single": {
        "label": "Short recording → choose one answer / reply",
        "kind": "single",
        "help": "Use for a short recording followed by three answer choices. Exactly one choice is correct.",
    },
    "long_single": {
        "label": "One recording → several multiple-choice questions",
        "kind": "single",
        "help": "Use when several questions share the same recording. Select the same audio track for those questions.",
    },
    "completion": {
        "label": "Gap / note / sentence completion",
        "kind": "short",
        "help": "Use when the student types the missing word, number or short answer.",
    },
    "ordering": {
        "label": "Ordering / sequence",
        "kind": "ordering",
        "help": "Use when the student must put supplied items into the correct order.",
    },
}



def _names(model):
    return {f.name for f in model._meta.get_fields()}


def _set_if(model, data, name, value):
    if name in _names(model):
        data[name] = value


def _choice(model, field_name, keywords, fallback):
    if field_name not in _names(model):
        return fallback
    field = model._meta.get_field(field_name)
    choices = list(getattr(field, "choices", ()) or ())
    for value, label in choices:
        hay = f"{value} {label}".lower().replace("_", " ").replace("-", " ")
        if all(k in hay for k in keywords):
            return value
    for value, label in choices:
        hay = f"{value} {label}".lower().replace("_", " ").replace("-", " ")
        if any(k in hay for k in keywords):
            return value
    return fallback


def _listening(model):
    if "skill" not in _names(model):
        return None
    return _choice(model, "skill", ("listening",), "listening")


def _qtype(kind):
    if kind == "ordering":
        return _choice(Question, "question_type", ("order",), "ordering")
    if kind == "short":
        for keys in (("short", "answer"), ("fill", "gap"), ("text",)):
            value = _choice(Question, "question_type", keys, None)
            if value is not None:
                return value
        return "short_answer"
    for keys in (("single", "choice"), ("choice",), ("mcq",)):
        value = _choice(Question, "question_type", keys, None)
        if value is not None:
            return value
    return "single_choice"


def _audio_type():
    for keys in (("audio",), ("listening",)):
        value = _choice(Stimulus, "stimulus_type", keys, None)
        if value is not None:
            return value
    return "audio"


def _cambridge_program():
    Program = MockTest._meta.get_field("program").related_model
    ranked = []
    for obj in Program._default_manager.all():
        values = [str(obj)] + [
            str(getattr(obj, name, "") or "")
            for name in ("title", "name", "slug", "code", "short_name")
        ]
        text = " ".join(values).lower()
        score = 0
        if "cambridge" in text:
            score += 10
        if "general english" in text:
            score += 8
        if "ielts" in text or "ukvi" in text:
            score -= 20
        if score > 0:
            ranked.append((score, obj))

    if not ranked:
        raise ValidationError("Cambridge / General English program was not found.")

    ranked.sort(key=lambda item: (-item[0], item[1].pk))
    return ranked[0][1]


def _main_listening_mock(program):
    # IMPORTANT: use the same MockTest the public/student Listening practice
    # already points to, instead of creating disconnected "Set" MockTests.
    mock = MockTest._default_manager.filter(
        program=program,
        slug="cambridge-listening-practice-1",
    ).first()

    if mock is None:
        candidates = MockTest._default_manager.filter(program=program)
        if "delivery_mode" in _names(MockTest):
            candidates = candidates.filter(delivery_mode="practice")
        if "is_published" in _names(MockTest):
            candidates = candidates.filter(is_published=True)

        for candidate in candidates:
            if TestSection._default_manager.filter(
                mock_test=candidate,
                skill=_listening(TestSection),
            ).exists():
                mock = candidate
                break

    if mock is None:
        data = {
            "program": program,
            "title": "Cambridge Listening Practice",
            "slug": "cambridge-listening-practice-1",
        }
        _set_if(MockTest, data, "description", "Cambridge Listening practice sets.")
        _set_if(MockTest, data, "instructions", "")
        _set_if(MockTest, data, "delivery_mode", "practice")
        _set_if(MockTest, data, "is_published", True)
        _set_if(MockTest, data, "duration_minutes", 25)
        mock = MockTest._default_manager.create(**data)

    return mock


def _structure(set_no, part_no, published):
    program = _cambridge_program()
    mock = _main_listening_mock(program)

    # Never unpublish the current Listening practice here.
    if (
        published
        and "is_published" in _names(MockTest)
        and not getattr(mock, "is_published", False)
    ):
        mock.is_published = True
        mock.save(update_fields=["is_published"])

    section = TestSection._default_manager.filter(
        mock_test=mock,
        skill=_listening(TestSection),
    ).order_by("order", "pk").first()

    if section is None:
        data = {
            "mock_test": mock,
            "title": "Listening",
            "skill": _listening(TestSection),
        }
        if "order" in _names(TestSection):
            last = (
                TestSection._default_manager
                .filter(mock_test=mock)
                .aggregate(value=Max("order"))["value"]
                or 0
            )
            data["order"] = last + 1
        _set_if(TestSection, data, "instructions", "")
        _set_if(TestSection, data, "duration_seconds", 25 * 60)
        _set_if(TestSection, data, "can_pause", False)
        _set_if(TestSection, data, "is_required", True)
        section = TestSection._default_manager.create(**data)

    part = TestPart._default_manager.filter(
        section=section,
        order=int(part_no),
    ).first()

    if part is None:
        data = {
            "section": section,
            "title": f"Listening Part {part_no}",
            "order": int(part_no),
        }
        _set_if(TestPart, data, "instructions", "")
        _set_if(TestPart, data, "prompt_mode", "audio")
        _set_if(TestPart, data, "question_visible", True)
        _set_if(TestPart, data, "preparation_seconds", 0)
        _set_if(TestPart, data, "is_active", True)
        part = TestPart._default_manager.create(**data)

    return program, mock, part


def _prefix(set_no, part_no):
    return f"Listening S{set_no} P{part_no} Q"


def _archive_replaced_question(question, set_no, part_no):
    """Retain historical content without exposing it as current Practice content."""
    changed = []

    if "is_active" in _names(Question) and getattr(question, "is_active", True):
        question.is_active = False
        changed.append("is_active")

    if "evaluator_notes" in _names(Question):
        notes = (getattr(question, "evaluator_notes", "") or "").strip()
        marker = (
            f"Archived by Listening Builder V34.6.5 after Set {set_no} "
            f"Part {part_no} was replaced. Historical attempts are preserved."
        )
        if marker not in notes:
            question.evaluator_notes = (notes + "\n" + marker).strip()
            changed.append("evaluator_notes")

    if changed:
        question.save(update_fields=list(dict.fromkeys(changed)))


def _clear(set_no, part_no, part):
    """
    Remove only CURRENT Practice placements.

    V34.6.5 intentionally performs NO Question.delete() and NO Stimulus.delete()
    while an administrator is replacing a Listening Part. This makes the save
    path safe for AttemptQuestion(PROTECT), Full Mock reuse, review/history and
    any future protected relation.
    """
    prefix = _prefix(set_no, part_no)
    rows = list(
        PartQuestion._default_manager
        .filter(part=part, question__title__startswith=prefix)
        .select_related("question")
    )

    questions = []
    seen = set()
    for row in rows:
        if row.question_id in seen:
            continue
        seen.add(row.question_id)
        questions.append(row.question)

    # Delete ONLY the link between the current Practice Part and its old
    # questions. The Question records themselves are retained safely.
    if questions:
        PartQuestion._default_manager.filter(
            part=part,
            question__in=questions,
        ).delete()

    for question in questions:
        # If the same question is reused by any other Part (especially Full
        # Mock), it must remain active and untouched.
        if PartQuestion._default_manager.filter(question=question).exists():
            continue

        # No current placement remains. Archive instead of deleting so any
        # AttemptQuestion / result / evaluator history can always resolve it.
        _archive_replaced_question(question, set_no, part_no)

def _stimuli(request, program, set_no, part_no):
    result = {}
    for number in range(1, 9):
        upload = request.FILES.get(f"audio_{number}")
        if not upload:
            continue

        data = {
            "program": program,
            "title": f"Listening S{set_no} P{part_no} Track {number}",
            "audio_file": upload,
        }
        _set_if(Stimulus, data, "stimulus_type", _audio_type())
        _set_if(Stimulus, data, "is_active", True)
        _set_if(
            Stimulus,
            data,
            "source_notes",
            f"Listening Builder V34.4 · Set {set_no} · Part {part_no} · Track {number}",
        )

        stimulus = Stimulus(**data)
        stimulus.full_clean(exclude=["audio_file"])
        stimulus.save()
        result[number] = stimulus

    return result


def _posted_choice(request, q_no, index):
    # Current unnumbered UI.
    value = (request.POST.get(f"q{q_no}_option_{index}") or "").strip()
    if value:
        return value

    # Backwards compatibility with the previous A/B/C form names.
    if index <= 3:
        letter = ("a", "b", "c")[index - 1]
        return (request.POST.get(f"q{q_no}_option_{letter}") or "").strip()
    return ""


def _correct_choice(request, q_no):
    value = (request.POST.get(f"q{q_no}_correct") or "").strip().upper()
    return {"A": "1", "B": "2", "C": "3"}.get(value, value)


def _question(
    request,
    program,
    part,
    set_no,
    part_no,
    q_no,
    q_type,
    task_pattern,
    prompt,
    stimulus,
):
    # Listening is audio-first. The audio can contain the complete question,
    # so prompt/instruction text is optional and NO transcript is required.
    prompt = (prompt or "").strip()

    data = {
        "program": program,
        "title": f"Listening S{set_no} P{part_no} Q{q_no}",
        "question_type": _qtype(q_type),
        "stimulus": stimulus,
        "prompt_text": prompt,
    }
    _set_if(Question, data, "skill", _listening(Question))
    _set_if(Question, data, "is_active", True)
    _set_if(Question, data, "show_prompt_text", bool(prompt))
    _set_if(Question, data, "default_points", 1)
    _set_if(Question, data, "automatic_marking", True)
    _set_if(Question, data, "ai_grading_required", False)
    _set_if(Question, data, "manual_review_allowed", False)
    _set_if(Question, data, "explanation", "")
    _set_if(
        Question,
        data,
        "evaluator_notes",
        f"Listening Flexible Builder V34.6 · Set {set_no} · Part {part_no} · Pattern {task_pattern}",
    )

    question = Question(**data)
    question.full_clean(exclude=["stimulus"])
    question.save()

    if q_type == "single":
        correct = _correct_choice(request, q_no)
        option_texts = [
            _posted_choice(request, q_no, index)
            for index in range(1, 4)
        ]

        if any(not text for text in option_texts):
            raise ValidationError(
                f"Question {q_no}: enter all 3 answer choices. "
                f"The student will choose only one answer."
            )

        if correct not in {"1", "2", "3"}:
            raise ValidationError(
                f"Question {q_no}: mark exactly 1 of the 3 choices as the correct answer."
            )

        rows = [
            QuestionOption(
                question=question,
                order=index,
                text=text,
                is_correct=(str(index) == correct),
            )
            for index, text in enumerate(option_texts, 1)
        ]

        QuestionOption._default_manager.bulk_create(rows)

    elif q_type == "short":
        raw = (request.POST.get(f"q{q_no}_short_answer") or "").strip()
        answers = [
            value.strip()
            for value in re.split(r"[\n;]+", raw)
            if value.strip()
        ]
        if not answers:
            raise ValidationError(
                f"Question {q_no}: enter the correct accepted answer."
            )

        answer_rows = []
        for answer in answers:
            answer_data = {
                "question": question,
                "answer_text": answer,
            }
            _set_if(AcceptableAnswer, answer_data, "case_sensitive", False)
            answer_rows.append(AcceptableAnswer(**answer_data))
        AcceptableAnswer._default_manager.bulk_create(answer_rows)

    elif q_type == "ordering":
        raw_items = (
            request.POST.get(f"q{q_no}_ordering_items") or ""
        ).strip()
        raw_order = (
            request.POST.get(f"q{q_no}_correct_order") or ""
        ).strip()

        items = {}
        for line in raw_items.splitlines():
            line = line.strip()
            if not line:
                continue

            match = re.match(
                r"^\s*([A-Za-z0-9]+)\s*[\.\|\):\-]\s*(.+)$",
                line,
            )
            if match:
                label = match.group(1).upper()
                text = match.group(2).strip()
            else:
                label = str(len(items) + 1)
                text = line
            items[label] = text

        order = [
            value.strip().upper()
            for value in re.split(r"[\s,>→]+", raw_order)
            if value.strip()
        ]

        if len(items) < 2:
            raise ValidationError(
                f"Question {q_no}: add at least two ordering items."
            )
        if not order or set(order) != set(items):
            raise ValidationError(
                f"Question {q_no}: correct order must include every item exactly once."
            )

        OrderingItem._default_manager.bulk_create([
            OrderingItem(
                question=question,
                correct_position=index,
                text=items[label],
            )
            for index, label in enumerate(order, 1)
        ])

    # Keep different Sets inside the same live TestPart without unique-order
    # collisions. Set 1 => 1001..., Set 2 => 2001..., etc.
    placement = {
        "part": part,
        "question": question,
        "order": (int(set_no) * 1000) + int(q_no),
    }
    _set_if(PartQuestion, placement, "is_required", True)
    if "points_override" in _names(PartQuestion):
        placement["points_override"] = None

    PartQuestion._default_manager.create(**placement)
    return question


def _rows():
    # Show only records produced by this builder.
    program = _cambridge_program()
    mock = MockTest._default_manager.filter(
        program=program,
        slug="cambridge-listening-practice-1",
    ).first()
    if mock is None:
        return []

    grouped = {}
    placements = (
        PartQuestion._default_manager
        .filter(
            part__section__mock_test=mock,
            question__title__startswith="Listening S",
        )
        .select_related("part", "question", "question__stimulus")
        .order_by("part__order", "order", "pk")
    )

    for row in placements:
        match = re.match(
            r"^Listening\s+S(\d+)\s+P(\d+)\s+Q(\d+)",
            row.question.title or "",
            re.I,
        )
        if not match:
            continue

        set_no = int(match.group(1))
        part_no = int(match.group(2))
        key = (set_no, part_no)

        bucket = grouped.setdefault(
            key,
            {
                "set_no": set_no,
                "part_no": part_no,
                "part_name": PART_GUIDE.get(part_no, {}).get(
                    "name",
                    row.part.title,
                ),
                "questions": 0,
                "audio_ids": set(),
                "published": bool(
                    getattr(mock, "is_published", False)
                ),
                "mock": mock,
            },
        )

        bucket["questions"] += 1

        if (
            row.question.stimulus_id
            and row.question.stimulus
            and getattr(row.question.stimulus, "audio_file", None)
        ):
            bucket["audio_ids"].add(row.question.stimulus_id)

    result = []
    for bucket in grouped.values():
        bucket["audio_tracks"] = len(bucket.pop("audio_ids"))
        result.append(bucket)

    result.sort(key=lambda item: (item["set_no"], item["part_no"]))
    return result


def listening_sets(request):
    wanted = (request.GET.get("part") or "").strip()
    rows = _rows()

    if wanted.isdigit():
        rows = [
            row
            for row in rows
            if row["part_no"] == int(wanted)
        ]

    context = {
        **admin.site.each_context(request),
        "title": "Listening Sets",
        "rows": rows,
        "part_guide": PART_GUIDE,
        "wanted_part": wanted,
        "opts": None,
        "has_permission": True,
    }

    return TemplateResponse(
        request,
        "admin/listening_sets_v34_2.html",
        context,
    )



def _parse_ordering_submission(request, q_no):
    raw_items = (
        request.POST.get(f"q{q_no}_ordering_items") or ""
    ).strip()
    raw_order = (
        request.POST.get(f"q{q_no}_correct_order") or ""
    ).strip()

    items = {}
    for line in raw_items.splitlines():
        line = line.strip()
        if not line:
            continue

        match = re.match(
            r"^\s*([A-Za-z0-9]+)\s*[\.\|\):\-]\s*(.+)$",
            line,
        )
        if match:
            label = match.group(1).upper()
            text = match.group(2).strip()
        else:
            label = str(len(items) + 1)
            text = line
        items[label] = text

    order = [
        value.strip().upper()
        for value in re.split(r"[\s,>→]+", raw_order)
        if value.strip()
    ]

    return items, order


def _validate_submission(request):
    try:
        set_no = int(request.POST.get("set_no") or 0)
        part_no = int(request.POST.get("part_no") or 0)
        question_count = int(
            request.POST.get("question_count") or 0
        )
    except (TypeError, ValueError):
        raise ValidationError(
            "Set, Part and question count must be valid numbers."
        )

    task_pattern = (
        request.POST.get("task_pattern")
        or ""
    ).strip()

    if not 1 <= set_no <= 99:
        raise ValidationError(
            "Set number must be between 1 and 99."
        )

    if part_no not in PART_GUIDE:
        raise ValidationError(
            "Choose Listening Part 1, 2, 3, 4 or 5."
        )

    if task_pattern not in TASK_PATTERNS:
        raise ValidationError(
            "Choose a valid Listening task pattern."
        )

    if not 1 <= question_count <= 10:
        raise ValidationError(
            "Add between 1 and 10 questions."
        )

    kind = TASK_PATTERNS[task_pattern]["kind"]

    for q_no in range(1, question_count + 1):
        try:
            track = int(
                request.POST.get(f"q{q_no}_track")
                or 0
            )
        except (TypeError, ValueError):
            track = 0

        if not 1 <= track <= 8:
            raise ValidationError(
                f"Question {q_no}: choose the audio track used by this question."
            )

        if not request.FILES.get(f"audio_{track}"):
            raise ValidationError(
                f"Question {q_no}: Track {track} is selected, "
                f"but no audio file is attached to Track {track}."
            )

        if kind == "single":
            options = [
                _posted_choice(request, q_no, index)
                for index in range(1, 4)
            ]
            correct = _correct_choice(request, q_no)

            if any(not value for value in options):
                raise ValidationError(
                    f"Question {q_no}: enter all 3 answer choices. "
                    f"Only 1 of them will be selected by the student."
                )

            if correct not in {"1", "2", "3"}:
                raise ValidationError(
                    f"Question {q_no}: mark exactly 1 correct answer."
                )

        elif kind == "short":
            raw = (
                request.POST.get(f"q{q_no}_short_answer")
                or ""
            ).strip()

            if not raw:
                raise ValidationError(
                    f"Question {q_no}: enter the accepted answer."
                )

        elif kind == "ordering":
            items, order = _parse_ordering_submission(
                request,
                q_no,
            )

            if len(items) < 2:
                raise ValidationError(
                    f"Question {q_no}: add at least two ordering items."
                )

            if not order or set(order) != set(items):
                raise ValidationError(
                    f"Question {q_no}: the correct order must contain "
                    f"every item exactly once."
                )

    return (
        set_no,
        part_no,
        question_count,
        task_pattern,
        kind,
    )


@transaction.atomic
def _save(request):
    (
        set_no,
        part_no,
        question_count,
        task_pattern,
        q_type,
    ) = _validate_submission(request)

    program, mock, part = _structure(
        set_no,
        part_no,
        request.POST.get("published") == "on",
    )

    existing = PartQuestion._default_manager.filter(
        part=part,
        question__title__startswith=_prefix(set_no, part_no),
    ).count()

    if (
        existing
        and request.POST.get("replace_existing") != "on"
    ):
        raise ValidationError(
            f"Set {set_no} Part {part_no} already has "
            f"{existing} question(s). Tick Replace existing "
            f"questions only when rebuilding this exact Set + Part."
        )

    if existing:
        _clear(set_no, part_no, part)

    # All user-input validation has already passed before this point.
    # This avoids writing audio/question records and then rejecting the form.
    stimuli = _stimuli(
        request,
        program,
        set_no,
        part_no,
    )

    created = []

    for q_no in range(1, question_count + 1):
        prompt = (
            request.POST.get(f"q{q_no}_text")
            or request.POST.get(f"q{q_no}_instruction")
            or ""
        ).strip()

        track = int(
            request.POST.get(f"q{q_no}_track")
        )

        created.append(
            _question(
                request,
                program,
                part,
                set_no,
                part_no,
                q_no,
                q_type,
                task_pattern,
                prompt,
                stimuli[track],
            )
        )

    return (
        mock,
        part,
        created,
        set_no,
        part_no,
        task_pattern,
    )


def listening_set_builder(request):
    def _safe_int(value, default, minimum, maximum):
        try:
            return max(
                minimum,
                min(maximum, int(value)),
            )
        except Exception:
            return default

    source = (
        request.POST
        if request.method == "POST"
        else request.GET
    )

    initial_set = _safe_int(
        source.get("set") or source.get("set_no") or 1,
        1,
        1,
        99,
    )

    initial_part = _safe_int(
        source.get("part") or source.get("part_no") or 1,
        1,
        1,
        5,
    )

    if initial_part not in PART_GUIDE:
        initial_part = 1

    initial_pattern = (
        source.get("task_pattern")
        or "short_single"
    )

    if initial_pattern not in TASK_PATTERNS:
        initial_pattern = "short_single"

    is_ajax = (
        request.headers.get("X-Requested-With")
        == "XMLHttpRequest"
    )

    if request.method == "POST":
        try:
            (
                mock,
                part,
                created,
                saved_set,
                saved_part,
                saved_pattern,
            ) = _save(request)

        except ValidationError as exc:
            error = " ".join(exc.messages)

            if is_ajax:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": error,
                    },
                    status=400,
                )

            messages.error(request, error)

        except Exception as exc:
            logger.exception("Listening Set Builder save failed")
            error = (
                "Could not save this Listening Part "
                f"({exc.__class__.__name__}): {exc}"
            )

            if is_ajax:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": error,
                    },
                    status=500,
                )

            messages.error(request, error)

        else:
            messages.success(
                request,
                f"Saved Listening Set {saved_set} · "
                f"Part {saved_part} with "
                f"{len(created)} question(s).",
            )

            if request.POST.get("save_another") == "1":
                next_part = (
                    saved_part + 1
                    if saved_part < 5
                    else 1
                )
                redirect_url = (
                    reverse(
                        "admin:b1_listening_set_builder"
                    )
                    + f"?set={saved_set}"
                    + f"&part={next_part}"
                    + f"&saved=1"
                )
            else:
                redirect_url = (
                    reverse(
                        "admin:b1_listening_sets"
                    )
                    + "?saved=1"
                )

            if is_ajax:
                return JsonResponse(
                    {
                        "ok": True,
                        "redirect": redirect_url,
                    }
                )

            return HttpResponseRedirect(
                redirect_url
            )

    server_draft = (
        request.POST.dict()
        if request.method == "POST"
        else {}
    )

    context = {
        **admin.site.each_context(request),
        "title": "Add Listening Questions",
        "part_guide": PART_GUIDE,
        "task_patterns": TASK_PATTERNS,
        "initial_set": initial_set,
        "initial_part": initial_part,
        "initial_pattern": initial_pattern,
        "server_draft": server_draft,
        "had_server_error": bool(
            request.method == "POST"
            and server_draft
        ),
        "opts": None,
        "has_permission": True,
    }

    return TemplateResponse(
        request,
        "admin/listening_set_builder_v34_2.html",
        context,
    )


if not getattr(
    admin.site,
    "_b1_listening_sets_v342_hooked",
    False,
):
    previous = admin.site.get_urls

    def get_urls():
        return [
            path(
                "listening-sets/",
                admin.site.admin_view(
                    listening_sets
                ),
                name="b1_listening_sets",
            ),
            path(
                "listening-set-builder/",
                admin.site.admin_view(
                    listening_set_builder
                ),
                name="b1_listening_set_builder",
            ),
        ] + previous()

    admin.site.get_urls = get_urls
    admin.site._b1_listening_sets_v342_hooked = True


