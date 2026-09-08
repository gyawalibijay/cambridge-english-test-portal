"""
B1 Ready Cambridge Full Mock Builder — Part 1 / 3.

This module is deliberately admin-only and schema-preserving.
It reuses existing Question objects and only manages PartQuestion placements
inside MockTest records whose delivery_mode is Full Mock.

No Practice question is deleted or duplicated.
"""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from assessments.models import MockTest, TestSection, TestPart
from question_bank.models import PartQuestion, Question

try:
    from question_bank.models import QuestionOption
except Exception:  # pragma: no cover - compatibility with older schema
    QuestionOption = None

try:
    from question_bank.models import AcceptableAnswer
except Exception:  # pragma: no cover
    AcceptableAnswer = None

try:
    from question_bank.models import OrderingItem
except Exception:  # pragma: no cover
    OrderingItem = None


# The order here is intentional and is the order the Full Mock must keep.
BLUEPRINT = OrderedDict(
    [
        (
            "reading",
            {
                "label": "Reading",
                "parts": 5,
                "minutes": 25,
                "icon": "R",
                "description": "Five Reading parts in exact admin-defined order.",
            },
        ),
        (
            "listening",
            {
                "label": "Listening",
                "parts": 5,
                "minutes": 25,
                "icon": "L",
                "description": "Five Listening parts with the uploaded audio and answer keys.",
            },
        ),
        (
            "speaking",
            {
                "label": "Speaking",
                "parts": 5,
                "minutes": 12,
                "icon": "S",
                "description": "Five Speaking parts using the existing recording runner.",
            },
        ),
        (
            "writing",
            {
                "label": "Writing",
                "parts": 2,
                "minutes": 30,
                "icon": "W",
                "description": "Two Writing parts using the existing writing runner.",
            },
        ),
    ]
)

FULL_DURATION_MINUTES = 92

SET_TITLE_RE = re.compile(
    r"^(Reading|Listening|Speaking|Writing)\s+S(\d+)\s+P(\d+)\s+Q(\d+)$",
    re.I,
)


def _names(model):
    return {field.name for field in model._meta.get_fields()}


def _field(model, name):
    try:
        return model._meta.get_field(name)
    except Exception:
        return None


def _choice(model, field_name, needles, fallback):
    field = _field(model, field_name)
    if field is None:
        return fallback

    choices = list(getattr(field, "choices", ()) or ())
    if not choices:
        return fallback

    wanted = tuple(str(x).lower() for x in needles)
    for value, label in choices:
        hay = f"{value} {label}".lower()
        if all(token in hay for token in wanted):
            return value

    for value, label in choices:
        hay = f"{value} {label}".lower()
        if any(token in hay for token in wanted):
            return value

    return fallback


def _skill_value(model, skill):
    return _choice(model, "skill", (skill,), skill)


def _full_mock_value():
    return _choice(MockTest, "delivery_mode", ("full", "mock"), "full_mock")


def _set_if(model, data, field_name, value):
    if field_name in _names(model):
        data[field_name] = value


def _set_attr_if(obj, field_name, value, changed):
    if field_name not in _names(obj.__class__):
        return
    if getattr(obj, field_name, None) != value:
        setattr(obj, field_name, value)
        changed.append(field_name)


def _cambridge_program():
    Program = MockTest._meta.get_field("program").related_model
    ranked = []

    for obj in Program._default_manager.all():
        values = [str(obj)]
        for name in ("title", "name", "slug", "code", "short_name"):
            values.append(str(getattr(obj, name, "") or ""))
        text = " ".join(values).lower()

        score = 0
        if "cambridge" in text:
            score += 10
        if "general english" in text:
            score += 8
        if "upskill" in text:
            score += 4
        if "ielts" in text or "ukvi" in text or "interview" in text:
            score -= 30

        if score > 0:
            ranked.append((score, obj))

    if not ranked:
        raise ValidationError(
            "Cambridge / General English program was not found. "
            "No mock-test data was changed."
        )

    ranked.sort(key=lambda item: (-item[0], item[1].pk))
    return ranked[0][1]


def _full_mocks():
    program = _cambridge_program()
    qs = MockTest._default_manager.filter(program=program)

    if "delivery_mode" in _names(MockTest):
        qs = qs.filter(delivery_mode=_full_mock_value())

    return qs.order_by("pk")


def _next_mock_number():
    number = 0
    for mock in _full_mocks():
        text = f"{getattr(mock, 'title', '')} {getattr(mock, 'slug', '')}"
        hits = [int(value) for value in re.findall(r"(?:mock(?:-test)?[-\s]*)(\d+)", text, re.I)]
        if hits:
            number = max(number, *hits)
    return number + 1


def _fill_required_scalar_fields(model, data):
    """
    Fill only harmless required scalar fields if an older portal schema has one.
    Foreign keys / relations are never guessed.
    """
    for field in model._meta.local_fields:
        if (
            field.primary_key
            or field.auto_created
            or field.name in data
            or field.null
            or field.has_default()
        ):
            continue

        internal = field.get_internal_type()

        if internal in {"CharField", "TextField"}:
            data[field.name] = ""
        elif internal == "BooleanField":
            data[field.name] = False
        elif internal in {
            "IntegerField",
            "PositiveIntegerField",
            "PositiveSmallIntegerField",
            "SmallIntegerField",
            "BigIntegerField",
        }:
            data[field.name] = 0
        # Date/time auto fields and relations are intentionally not guessed.

    return data


def _create_mock():
    program = _cambridge_program()
    number = _next_mock_number()

    data = {
        "program": program,
        "title": f"Cambridge Full Mock Test {number}",
        "delivery_mode": _full_mock_value(),
    }

    _set_if(MockTest, data, "slug", f"cambridge-full-mock-{number}")
    _set_if(
        MockTest,
        data,
        "description",
        "Complete Cambridge Upskill preparation mock: Reading, Listening, Speaking and Writing.",
    )
    _set_if(
        MockTest,
        data,
        "instructions",
        "Complete each skill and Part in the order presented.",
    )
    _set_if(MockTest, data, "duration_minutes", FULL_DURATION_MINUTES)
    _set_if(MockTest, data, "is_published", False)
    _set_if(MockTest, data, "is_active", True)

    _fill_required_scalar_fields(MockTest, data)

    mock = MockTest(**data)
    mock.full_clean()
    mock.save()

    _ensure_structure(mock)
    return mock


def _section_for(mock, skill):
    expected = _skill_value(TestSection, skill)

    if "skill" in _names(TestSection):
        found = (
            TestSection._default_manager.filter(mock_test=mock, skill=expected)
            .order_by("order", "pk")
            .first()
        )
        if found:
            return found

    label = BLUEPRINT[skill]["label"]
    return (
        TestSection._default_manager.filter(mock_test=mock, title__iexact=label)
        .order_by("order", "pk")
        .first()
    )


def _ensure_structure(mock):
    """
    Create/normalize the exact four-skill Full Mock skeleton.

    Existing questions are never deleted here.
    Extra historical Parts are left in the database but deactivated when possible.
    """
    with transaction.atomic():
        mock_changed = []
        _set_attr_if(mock, "delivery_mode", _full_mock_value(), mock_changed)
        _set_attr_if(mock, "duration_minutes", FULL_DURATION_MINUTES, mock_changed)
        if mock_changed:
            mock.save(update_fields=mock_changed)

        # B1_MOCK_BUILDER_ORDER_COLLISION_HOTFIX_V35_0_1
        # Existing Full Mock rows may already use section orders 1..4 in a
        # different skill sequence. Updating one row directly to an occupied
        # order violates unique_section_order_per_test. Detect that situation
        # first and temporarily move the mock's existing sections to a safe
        # high range. The four real Cambridge sections are then normalized
        # below to 1=Reading, 2=Listening, 3=Speaking, 4=Writing.
        existing_sections = list(
            TestSection._default_manager.filter(mock_test=mock)
            .only("pk", "order")
            .order_by("order", "pk")
        )
        occupied_orders = {int(row.order): row.pk for row in existing_sections}
        needs_order_staging = False

        for expected_order, (expected_skill, _spec) in enumerate(BLUEPRINT.items(), start=1):
            selected = _section_for(mock, expected_skill)
            occupant_pk = occupied_orders.get(expected_order)

            if selected is None:
                if occupant_pk is not None:
                    needs_order_staging = True
                    break
            elif int(getattr(selected, "order", 0) or 0) != expected_order:
                if occupant_pk is not None and occupant_pk != selected.pk:
                    needs_order_staging = True
                    break

        if needs_order_staging and existing_sections:
            from django.db.models import F

            max_order = max(int(row.order or 0) for row in existing_sections)
            offset = max_order + len(existing_sections) + 10
            TestSection._default_manager.filter(mock_test=mock).update(
                order=F("order") + offset
            )

        result = {}

        for section_order, (skill, spec) in enumerate(BLUEPRINT.items(), start=1):
            section = _section_for(mock, skill)

            if section is None:
                data = {
                    "mock_test": mock,
                    "title": spec["label"],
                }
                _set_if(TestSection, data, "skill", _skill_value(TestSection, skill))
                _set_if(TestSection, data, "order", section_order)
                _set_if(TestSection, data, "duration_seconds", spec["minutes"] * 60)
                _set_if(TestSection, data, "duration_minutes", spec["minutes"])
                _set_if(TestSection, data, "instructions", "")
                _set_if(TestSection, data, "can_pause", False)
                _set_if(TestSection, data, "is_required", True)
                _set_if(TestSection, data, "is_active", True)
                _fill_required_scalar_fields(TestSection, data)

                section = TestSection(**data)
                section.full_clean()
                section.save()
            else:
                changed = []
                _set_attr_if(section, "title", spec["label"], changed)
                _set_attr_if(section, "skill", _skill_value(TestSection, skill), changed)
                _set_attr_if(section, "order", section_order, changed)
                _set_attr_if(section, "duration_seconds", spec["minutes"] * 60, changed)
                _set_attr_if(section, "duration_minutes", spec["minutes"], changed)
                _set_attr_if(section, "can_pause", False, changed)
                _set_attr_if(section, "is_required", True, changed)
                _set_attr_if(section, "is_active", True, changed)
                if changed:
                    section.save(update_fields=list(dict.fromkeys(changed)))

            parts = []
            for part_no in range(1, spec["parts"] + 1):
                part = (
                    TestPart._default_manager.filter(section=section, order=part_no)
                    .order_by("pk")
                    .first()
                )

                if part is None:
                    data = {
                        "section": section,
                        "title": f"{spec['label']} Part {part_no}",
                        "order": part_no,
                    }
                    _set_if(TestPart, data, "instructions", "")
                    _set_if(
                        TestPart,
                        data,
                        "prompt_mode",
                        "audio" if skill == "listening" else "text",
                    )
                    _set_if(TestPart, data, "question_visible", True)
                    _set_if(TestPart, data, "preparation_seconds", 0)
                    _set_if(TestPart, data, "prep_seconds", 0)
                    _set_if(TestPart, data, "response_seconds", 0)
                    _set_if(TestPart, data, "is_active", True)
                    _fill_required_scalar_fields(TestPart, data)

                    part = TestPart(**data)
                    part.full_clean()
                    part.save()
                else:
                    changed = []
                    _set_attr_if(part, "title", f"{spec['label']} Part {part_no}", changed)
                    _set_attr_if(part, "order", part_no, changed)
                    _set_attr_if(part, "is_active", True, changed)
                    if changed:
                        part.save(update_fields=list(dict.fromkeys(changed)))

                parts.append(part)

            # Never delete historical data automatically.
            # If the schema supports is_active, hide Parts beyond the real structure.
            extras = TestPart._default_manager.filter(section=section).exclude(
                pk__in=[p.pk for p in parts]
            )
            if "is_active" in _names(TestPart):
                extras.update(is_active=False)

            result[skill] = {"section": section, "parts": parts}

        return result


def _question_queryset(skill):
    program = _cambridge_program()
    qs = Question._default_manager.filter(program=program)

    if "skill" in _names(Question):
        qs = qs.filter(skill=_skill_value(Question, skill))

    if "is_active" in _names(Question):
        qs = qs.filter(is_active=True)

    return qs.order_by("title", "pk")


def _parse_standard_title(title):
    match = SET_TITLE_RE.fullmatch((title or "").strip())
    if not match:
        return None
    label, set_no, part_no, q_no = match.groups()
    return label.lower(), int(set_no), int(part_no), int(q_no)


def _set_inventory(skill):
    inventory = defaultdict(lambda: defaultdict(list))

    for question in _question_queryset(skill):
        parsed = _parse_standard_title(question.title)
        if not parsed:
            continue

        title_skill, set_no, part_no, q_no = parsed
        if title_skill != skill:
            continue

        inventory[set_no][part_no].append((q_no, question))

    result = []
    for set_no in sorted(inventory):
        parts = {}
        total = 0
        for part_no in sorted(inventory[set_no]):
            rows = sorted(inventory[set_no][part_no], key=lambda row: (row[0], row[1].pk))
            parts[part_no] = rows
            total += len(rows)
        result.append({"set_no": set_no, "parts": parts, "total": total})

    return result


def _part_rows(part):
    return list(
        PartQuestion._default_manager.filter(part=part)
        .select_related("question")
        .order_by("order", "pk")
    )


def _part_summary(part, skill, part_no):
    rows = _part_rows(part)
    current_set = None

    parsed = []
    for row in rows:
        p = _parse_standard_title(getattr(row.question, "title", ""))
        if p and p[0] == skill and p[2] == part_no:
            parsed.append(p[1])
        else:
            parsed.append(None)

    if rows and all(value is not None for value in parsed) and len(set(parsed)) == 1:
        current_set = parsed[0]

    return {
        "part": part,
        "part_no": part_no,
        "question_count": len(rows),
        "current_set": current_set,
        "questions": [row.question for row in rows],
    }


def _placement_data(part, question, order):
    data = {
        "part": part,
        "question": question,
        "order": int(order),
    }

    if "is_required" in _names(PartQuestion):
        data["is_required"] = True

    if "points_override" in _names(PartQuestion):
        field = _field(PartQuestion, "points_override")
        if getattr(field, "null", False):
            data["points_override"] = None
        elif field.has_default():
            data["points_override"] = field.get_default()
        else:
            data["points_override"] = 0

    return data


def _sync_question_count(part):
    if "question_count" not in _names(TestPart):
        return

    count = PartQuestion._default_manager.filter(part=part).count()
    if getattr(part, "question_count", None) != count:
        part.question_count = count
        part.save(update_fields=["question_count"])


def _assign_questions(part, questions):
    """
    Replace only placements in this Full Mock Part.
    Source Question records and Practice placements remain untouched.
    """
    with transaction.atomic():
        PartQuestion._default_manager.filter(part=part).delete()

        rows = []
        for order, question in enumerate(questions, start=1):
            rows.append(PartQuestion(**_placement_data(part, question, order)))

        if rows:
            PartQuestion._default_manager.bulk_create(rows)

        _sync_question_count(part)


def _questions_for_set(skill, set_no, part_no):
    found = []
    for question in _question_queryset(skill):
        parsed = _parse_standard_title(question.title)
        if not parsed:
            continue
        q_skill, q_set, q_part, q_no = parsed
        if q_skill == skill and q_set == set_no and q_part == part_no:
            found.append((q_no, question))

    found.sort(key=lambda row: (row[0], row[1].pk))
    return [question for _, question in found]


def _natural_question_key(question):
    parsed = _parse_standard_title(getattr(question, "title", ""))
    if parsed:
        return (0, parsed[3], question.pk)

    numbers = re.findall(r"\d+", getattr(question, "title", "") or "")
    if numbers:
        return (1, int(numbers[-1]), question.pk)

    return (2, question.pk, question.pk)


def _has_audio(question):
    prompt_audio = getattr(question, "prompt_audio", None)
    if prompt_audio and getattr(prompt_audio, "name", ""):
        return True

    stimulus = getattr(question, "stimulus", None)
    if stimulus:
        audio = getattr(stimulus, "audio_file", None)
        if audio and getattr(audio, "name", ""):
            return True

    return False


def _has_student_content(question):
    if (getattr(question, "prompt_text", "") or "").strip():
        return True
    if _has_audio(question):
        return True

    stimulus = getattr(question, "stimulus", None)
    if stimulus:
        for name in ("content", "text", "transcript"):
            if (getattr(stimulus, name, "") or "").strip():
                return True

    return False


def _has_objective_key(question):
    checks = []

    if QuestionOption is not None:
        options = QuestionOption._default_manager.filter(question=question)
        if options.exists():
            checks.append(
                options.count() >= 2
                and options.filter(is_correct=True).exists()
            )

    if AcceptableAnswer is not None:
        answers = AcceptableAnswer._default_manager.filter(question=question)
        if answers.exists():
            checks.append(True)

    if OrderingItem is not None:
        items = OrderingItem._default_manager.filter(question=question)
        if items.exists():
            checks.append(items.count() >= 2)

    return any(checks)


def _readiness(mock):
    structure = _ensure_structure(mock)
    issues = []
    skill_rows = []

    for skill, spec in BLUEPRINT.items():
        section = structure[skill]["section"]
        parts = structure[skill]["parts"]
        ready_parts = 0
        question_total = 0

        for part_no, part in enumerate(parts, start=1):
            rows = _part_rows(part)
            question_total += len(rows)

            if not rows:
                issues.append(f"{spec['label']} Part {part_no}: no questions assigned.")
                continue

            orders = [row.order for row in rows]
            if len(orders) != len(set(orders)):
                issues.append(
                    f"{spec['label']} Part {part_no}: duplicate question order values."
                )

            part_ok = True
            for row in rows:
                question = row.question

                if "is_active" in _names(Question) and not getattr(question, "is_active", True):
                    issues.append(
                        f"{spec['label']} Part {part_no}: '{question.title}' is inactive."
                    )
                    part_ok = False

                if skill == "listening" and not _has_audio(question):
                    issues.append(
                        f"Listening Part {part_no}: '{question.title}' has no playable audio source."
                    )
                    part_ok = False

                if skill in {"reading", "listening"} and not _has_objective_key(question):
                    issues.append(
                        f"{spec['label']} Part {part_no}: '{question.title}' has no detectable answer key."
                    )
                    part_ok = False

                if skill in {"speaking", "writing"} and not _has_student_content(question):
                    issues.append(
                        f"{spec['label']} Part {part_no}: '{question.title}' has no student prompt/media."
                    )
                    part_ok = False

            if part_ok:
                ready_parts += 1

        skill_rows.append(
            {
                "key": skill,
                "label": spec["label"],
                "icon": spec["icon"],
                "parts": spec["parts"],
                "ready_parts": ready_parts,
                "minutes": spec["minutes"],
                "questions": question_total,
                "ready": ready_parts == spec["parts"],
                "description": spec["description"],
                "section": section,
            }
        )

    return {
        "ready": not issues,
        "issues": issues,
        "skills": skill_rows,
        "total_questions": sum(row["questions"] for row in skill_rows),
    }


def _mock_from_id(mock_id):
    try:
        mock = _full_mocks().get(pk=mock_id)
    except MockTest.DoesNotExist as exc:
        raise Http404("Cambridge Full Mock Test not found.") from exc
    return mock


def _mock_status(mock):
    if "is_published" in _names(MockTest):
        return bool(getattr(mock, "is_published", False))
    return False


def _builder_context(request, title):
    context = admin.site.each_context(request)
    context.update(
        {
            "title": title,
            "opts": None,
            "has_permission": True,
            "mock_builder_part": "1 / 3",
        }
    )
    return context


def mock_builder_index(request):
    if request.method == "POST":
        action = request.POST.get("action", "")

        try:
            if action == "create":
                mock = _create_mock()
                messages.success(
                    request,
                    f"{mock.title} created with Reading → Listening → Speaking → Writing structure.",
                )
                return HttpResponseRedirect(
                    reverse("admin:b1_mock_builder_detail", args=[mock.pk])
                )
            raise ValidationError("Unknown Mock Builder action.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except Exception as exc:
            messages.error(request, f"Could not create the mock safely: {exc}")

    mocks = []
    for mock in _full_mocks():
        status = _readiness(mock)
        mocks.append(
            {
                "mock": mock,
                "published": _mock_status(mock),
                "ready": status["ready"],
                "questions": status["total_questions"],
                "ready_skills": sum(1 for row in status["skills"] if row["ready"]),
            }
        )

    context = _builder_context(request, "Cambridge Mock Tests")
    context.update({"mocks": mocks})
    return TemplateResponse(request, "admin/mock_builder_v35/index.html", context)


def mock_builder_detail(request, mock_id):
    mock = _mock_from_id(mock_id)

    if request.method == "POST":
        action = request.POST.get("action", "")

        try:
            if action == "repair":
                _ensure_structure(mock)
                messages.success(
                    request,
                    "The four-skill structure was checked and normalized without deleting questions.",
                )

            elif action == "publish":
                state = _readiness(mock)
                if not state["ready"]:
                    raise ValidationError(
                        "This mock is not ready to publish. Fix the readiness items first."
                    )
                if "is_published" not in _names(MockTest):
                    raise ValidationError(
                        "The current MockTest model has no is_published field."
                    )
                mock.is_published = True
                mock.save(update_fields=["is_published"])
                messages.success(
                    request,
                    "Mock published. The current student Mock Test hub can now discover it.",
                )

            elif action == "unpublish":
                if "is_published" in _names(MockTest):
                    mock.is_published = False
                    mock.save(update_fields=["is_published"])
                messages.success(request, "Mock unpublished. Its questions were kept.")

            else:
                raise ValidationError("Unknown Mock Builder action.")

        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except Exception as exc:
            messages.error(request, f"Mock Builder could not complete that action: {exc}")

        return HttpResponseRedirect(
            reverse("admin:b1_mock_builder_detail", args=[mock.pk])
        )

    state = _readiness(mock)
    context = _builder_context(request, mock.title)
    context.update(
        {
            "mock": mock,
            "published": _mock_status(mock),
            "state": state,
        }
    )
    return TemplateResponse(request, "admin/mock_builder_v35/detail.html", context)


def mock_builder_skill(request, mock_id, skill):
    skill = (skill or "").lower()
    if skill not in BLUEPRINT:
        raise Http404("Unknown skill.")

    mock = _mock_from_id(mock_id)
    structure = _ensure_structure(mock)
    parts = structure[skill]["parts"]
    spec = BLUEPRINT[skill]

    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            part_no = int(request.POST.get("part_no", "0"))
            if part_no < 1 or part_no > len(parts):
                raise ValidationError("Choose a valid Part.")

            part = parts[part_no - 1]

            if action == "use_set":
                set_no = int(request.POST.get("set_no", "0"))
                questions = _questions_for_set(skill, set_no, part_no)
                if not questions:
                    raise ValidationError(
                        f"No {spec['label']} Set {set_no} / Part {part_no} questions were found."
                    )
                _assign_questions(part, questions)
                messages.success(
                    request,
                    f"{spec['label']} Part {part_no} now uses Set {set_no} "
                    f"({len(questions)} questions) in exact Q-number order.",
                )

            elif action == "manual_assign":
                raw_ids = request.POST.getlist("question_ids")
                if not raw_ids:
                    raise ValidationError("Select at least one existing question.")

                ids = []
                for raw in raw_ids:
                    try:
                        ids.append(int(raw))
                    except (TypeError, ValueError):
                        continue

                allowed = {
                    q.pk: q
                    for q in _question_queryset(skill).filter(pk__in=ids)
                }

                if len(allowed) != len(set(ids)):
                    raise ValidationError(
                        "One or more selected questions do not belong to this Cambridge skill."
                    )

                questions = [allowed[pk] for pk in ids if pk in allowed]
                questions.sort(key=_natural_question_key)
                _assign_questions(part, questions)

                messages.success(
                    request,
                    f"{spec['label']} Part {part_no} updated with "
                    f"{len(questions)} existing questions in deterministic order.",
                )

            elif action == "clear":
                _assign_questions(part, [])
                messages.success(
                    request,
                    f"{spec['label']} Part {part_no} placement cleared. "
                    "No Question record was deleted.",
                )

            else:
                raise ValidationError("Unknown Part action.")

        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except Exception as exc:
            messages.error(
                request,
                f"{spec['label']} Part could not be updated safely: {exc}",
            )

        return HttpResponseRedirect(
            reverse("admin:b1_mock_builder_skill", args=[mock.pk, skill])
        )

    inventory = _set_inventory(skill)
    part_summaries = [
        _part_summary(part, skill, index)
        for index, part in enumerate(parts, start=1)
    ]

    # Existing questions are available as a fallback picker.
    all_questions = list(_question_queryset(skill)[:500])

    # Build a convenient set lookup for the template.
    set_cards = []
    for entry in inventory:
        set_cards.append(
            {
                "set_no": entry["set_no"],
                "parts": {
                    part_no: len(rows)
                    for part_no, rows in entry["parts"].items()
                },
                "total": entry["total"],
            }
        )

    context = _builder_context(
        request,
        f"{mock.title} — {spec['label']}",
    )
    context.update(
        {
            "mock": mock,
            "skill": skill,
            "spec": spec,
            "parts": part_summaries,
            "sets": set_cards,
            "all_questions": all_questions,
            "question_bank_url": f"/admin/question_bank/question/?skill={skill}",
            "question_add_url": f"/admin/question_bank/question/add/?skill={skill}",
            "special_builder_url": (
                "/admin/listening-sets/"
                if skill == "listening"
                else "/admin/reading-sets/"
                if skill == "reading"
                else f"/admin/question_bank/question/?skill={skill}"
            ),
        }
    )
    return TemplateResponse(request, "admin/mock_builder_v35/skill.html", context)


if not getattr(admin.site, "_b1_mock_builder_v35_part1_hooked", False):
    _previous_get_urls = admin.site.get_urls

    def _get_urls():
        custom = [
            path(
                "mock-builder/",
                admin.site.admin_view(mock_builder_index),
                name="b1_mock_builder",
            ),
            path(
                "mock-builder/<int:mock_id>/",
                admin.site.admin_view(mock_builder_detail),
                name="b1_mock_builder_detail",
            ),
            path(
                "mock-builder/<int:mock_id>/<slug:skill>/",
                admin.site.admin_view(mock_builder_skill),
                name="b1_mock_builder_skill",
            ),
        ]
        return custom + _previous_get_urls()

    admin.site.get_urls = _get_urls
    admin.site._b1_mock_builder_v35_part1_hooked = True
