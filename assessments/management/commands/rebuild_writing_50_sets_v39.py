from __future__ import annotations

import re

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.writing_bank_v39_data import load_data

Question = apps.get_model("question_bank", "Question")
Stimulus = apps.get_model("question_bank", "Stimulus")
PartQuestion = apps.get_model("question_bank", "PartQuestion")
MockTest = apps.get_model("assessments", "MockTest")
TestSection = apps.get_model("assessments", "TestSection")
TestPart = apps.get_model("assessments", "TestPart")
Program = MockTest._meta.get_field("program").related_model

CANONICAL_SLUG = "cambridge-writing-source-samples"
CANONICAL_TITLE_RE = re.compile(r"^Writing S([1-9]|[1-4]\d|50) P([12]) Q1$", re.I)
EXTRA_TITLE_RE = re.compile(r"^Writing Extra P2 Q(\d{2})$", re.I)


def _names(model):
    return {field.name for field in model._meta.get_fields()}


def _set_if(model, data, name, value):
    if name in _names(model):
        data[name] = value


def _set_attr(obj, name, value):
    if name in _names(obj.__class__):
        setattr(obj, name, value)


def _choice(model, field_name, keyword_sets, fallback=None):
    if field_name not in _names(model):
        return fallback
    field = model._meta.get_field(field_name)
    choices = list(getattr(field, "choices", ()) or ())
    if not choices:
        return fallback
    for keys in keyword_sets:
        for value, label in choices:
            hay = f"{value} {label}".lower().replace("_", " ").replace("-", " ")
            if all(key in hay for key in keys):
                return value
    return fallback


def _writing(model):
    return _choice(model, "skill", (("writing",),), "writing") if "skill" in _names(model) else "writing"


def _text_stimulus_type():
    existing = (
        Stimulus._default_manager
        .filter(questions__skill=_writing(Question))
        .exclude(stimulus_type="")
        .values_list("stimulus_type", flat=True)
        .first()
        if "stimulus_type" in _names(Stimulus)
        else None
    )
    if existing:
        return existing
    return _choice(
        Stimulus,
        "stimulus_type",
        (("text",), ("passage",), ("writing",), ("prompt",)),
        "text",
    )


def _writing_question_type(program):
    skill = _writing(Question)
    existing = (
        Question._default_manager
        .filter(program=program, skill=skill)
        .exclude(question_type="")
        .values_list("question_type", flat=True)
        .first()
    )
    if existing:
        return existing

    value = _choice(
        Question,
        "question_type",
        (
            ("writing",),
            ("written", "response"),
            ("essay",),
            ("free", "text"),
            ("long", "text"),
            ("text", "response"),
            ("short", "answer"),
        ),
        None,
    )
    if value is not None:
        return value

    field = Question._meta.get_field("question_type")
    choices = list(getattr(field, "choices", ()) or ())
    return choices[0][0] if choices else "short_answer"


def _program():
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
            ranked.append((score, obj.pk, obj))
    if not ranked:
        raise CommandError("Cambridge / General English Program was not found.")
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked[0][2]


def _archive_duplicate(question):
    original = question.title or f"Question {question.pk}"
    question.title = f"[ARCHIVED WRITING V39 DUPLICATE] {original} #{question.pk}"[:200]
    question.is_active = False
    question.save()


def _stable_question(program, title):
    rows = list(
        Question._default_manager
        .filter(program=program, skill=_writing(Question), title=title)
        .order_by("pk")
    )
    if not rows:
        return Question(program=program, title=title)

    def history_rank(obj):
        manager = getattr(obj, "attempt_questions", None)
        used = bool(manager and manager.exists())
        return (0 if used else 1, obj.pk)

    rows.sort(key=history_rank)
    keep = rows[0]
    for extra in rows[1:]:
        _archive_duplicate(extra)
    return keep


def _upsert_stimulus(program, title, content, source_note):
    obj = (
        Stimulus._default_manager
        .filter(program=program, title=title)
        .order_by("pk")
        .first()
    )
    if obj is None:
        data = {"program": program, "title": title}
        _set_if(Stimulus, data, "stimulus_type", _text_stimulus_type())
        obj = Stimulus(**data)

    _set_attr(obj, "program", program)
    _set_attr(obj, "title", title)
    _set_attr(obj, "skill", _writing(Stimulus))
    _set_attr(obj, "stimulus_type", _text_stimulus_type())
    _set_attr(obj, "content", content.strip())
    _set_attr(obj, "is_active", True)
    _set_attr(obj, "source_notes", source_note)
    obj.save()
    return obj


def _upsert_question(program, title, stimulus, prompt, source_note, qtype):
    q = _stable_question(program, title)
    _set_attr(q, "program", program)
    _set_attr(q, "title", title)
    _set_attr(q, "skill", _writing(Question))
    _set_attr(q, "question_type", qtype)
    _set_attr(q, "stimulus", stimulus)
    _set_attr(q, "prompt_text", prompt.strip())
    _set_attr(q, "show_prompt_text", True)
    _set_attr(q, "difficulty", "medium")
    _set_attr(q, "cefr_level", "")
    _set_attr(q, "default_points", 1)
    _set_attr(q, "automatic_marking", False)
    _set_attr(q, "ai_grading_required", True)
    _set_attr(q, "manual_review_allowed", True)
    _set_attr(q, "preparation_seconds", 0)
    _set_attr(q, "response_seconds", 900)
    _set_attr(q, "min_word_count", 50)
    _set_attr(q, "max_word_count", 0)
    _set_attr(q, "explanation", "")
    _set_attr(q, "evaluator_notes", source_note)
    _set_attr(q, "is_active", True)
    q.save()
    return q


def _find_existing_practice(program):
    direct = (
        MockTest._default_manager
        .filter(program=program, slug=CANONICAL_SLUG)
        .order_by("pk")
        .first()
    )
    if direct:
        return direct

    candidates = MockTest._default_manager.filter(program=program).order_by("pk")
    if "delivery_mode" in _names(MockTest):
        candidates = candidates.filter(delivery_mode="practice")
    for mock in candidates:
        if TestSection._default_manager.filter(
            mock_test=mock,
            skill=_writing(TestSection),
        ).exists():
            return mock
    return None


def _ensure_practice(program):
    mock = _find_existing_practice(program)
    if mock is None:
        data = {
            "program": program,
            "title": "Cambridge Writing Practice",
            "slug": CANONICAL_SLUG,
        }
        _set_if(MockTest, data, "description", "Cambridge Writing Practice · 50 complete two-part sets.")
        _set_if(MockTest, data, "instructions", "")
        _set_if(MockTest, data, "delivery_mode", "practice")
        _set_if(MockTest, data, "is_published", True)
        _set_if(MockTest, data, "duration_minutes", 30)
        mock = MockTest._default_manager.create(**data)
    else:
        _set_attr(mock, "program", program)
        _set_attr(mock, "title", "Cambridge Writing Practice")
        _set_attr(mock, "description", "Cambridge Writing Practice · 50 complete two-part sets.")
        _set_attr(mock, "delivery_mode", "practice")
        _set_attr(mock, "is_published", True)
        _set_attr(mock, "duration_minutes", 30)
        mock.save()

    writing_sections = list(
        TestSection._default_manager
        .filter(mock_test=mock, skill=_writing(TestSection))
        .order_by("order", "pk")
    )
    if writing_sections:
        section = writing_sections[0]
        for extra in writing_sections[1:]:
            extra.parts.update(is_active=False)
    else:
        data = {
            "mock_test": mock,
            "title": "Writing",
            "skill": _writing(TestSection),
        }
        _set_if(TestSection, data, "order", 1)
        section = TestSection._default_manager.create(**data)

    _set_attr(section, "title", "Writing")
    _set_attr(section, "skill", _writing(TestSection))
    _set_attr(section, "duration_seconds", 30 * 60)
    _set_attr(section, "can_pause", False)
    _set_attr(section, "is_required", True)
    section.save()

    # This object is the dedicated Writing Practice test. Keep any accidental
    # non-Writing sections out of new attempts without deleting their rows.
    for other in TestSection._default_manager.filter(mock_test=mock).exclude(pk=section.pk):
        other.parts.update(is_active=False)

    parts = {}
    for part_no in (1, 2):
        part = (
            TestPart._default_manager
            .filter(section=section, order=part_no)
            .order_by("pk")
            .first()
        )
        if part is None:
            part = TestPart(section=section, order=part_no, title=f"Writing Part {part_no}")
        _set_attr(part, "title", f"Writing Part {part_no}")
        _set_attr(part, "order", part_no)
        _set_attr(part, "instructions", "")
        _set_attr(part, "prompt_mode", "text")
        _set_attr(part, "question_visible", True)
        _set_attr(part, "preparation_seconds", 0)
        _set_attr(part, "response_seconds", 15 * 60)
        _set_attr(part, "question_count", 1)
        _set_attr(part, "recording_required", False)
        _set_attr(part, "is_active", True)
        part.save()
        parts[part_no] = part

    section.parts.exclude(pk__in=[part.pk for part in parts.values()]).update(is_active=False)
    return mock, section, parts


class Command(BaseCommand):
    help = "Import the user-supplied 50-set Cambridge Writing bank and 10 supplementary Part 2 tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the import. Without this flag, print a source/database audit only.",
        )

    def handle(self, *args, **options):
        data = load_data()
        canonical = data["canonical_sets"]
        extras = data["extra_part2"]
        program = _program()
        skill = _writing(Question)

        if not options["apply"]:
            self.stdout.write(f"Source: {len(canonical)} complete Sets / {len(canonical) * 2} canonical tasks")
            self.stdout.write(f"Supplementary Part 2 source tasks: {len(extras)}")
            self.stdout.write(
                f"Current standardized Writing questions: "
                f"{Question._default_manager.filter(program=program, skill=skill, title__regex=r'^Writing S\\d+ P[12] Q1$').count()}"
            )
            return

        qtype = _writing_question_type(program)

        with transaction.atomic():
            mock, section, parts = _ensure_practice(program)
            canonical_questions = {}

            for row in canonical:
                set_no = int(row["set_no"])
                for part_no in (1, 2):
                    task = row["parts"][str(part_no)]
                    title = f"Writing S{set_no} P{part_no} Q1"
                    source_note = (
                        f"Writing V39 canonical source · Set {set_no} · Part {part_no} · "
                        f"{task['type']} · {task['source_file']}. "
                        "Imported from the client-supplied Writing DOCX bank."
                    )
                    stimulus = _upsert_stimulus(
                        program,
                        f"{title} Source",
                        task["context"],
                        source_note,
                    )
                    question = _upsert_question(
                        program,
                        title,
                        stimulus,
                        task["prompt"],
                        source_note,
                        qtype,
                    )
                    canonical_questions[(set_no, part_no)] = question

            # Canonical Practice placements only: replace legacy/dummy placements in
            # these two Writing Parts, but do not delete Question records or attempts.
            for part_no, part in parts.items():
                PartQuestion._default_manager.filter(part=part).delete()
                rows = []
                for set_no in range(1, 51):
                    values = {
                        "part": part,
                        "question": canonical_questions[(set_no, part_no)],
                        "order": set_no,
                    }
                    _set_if(PartQuestion, values, "is_required", True)
                    rows.append(PartQuestion(**values))
                PartQuestion._default_manager.bulk_create(rows)

            # The separate PART 2 WRITING.docx overlaps conceptually with Sets 1-10.
            # Preserve all ten tasks without silently replacing the canonical P2 tasks.
            for extra in extras:
                number = int(extra["number"])
                title = f"Writing Extra P2 Q{number:02d}"
                source_note = (
                    f"Writing V39 supplementary Part 2 · {extra['title']} · "
                    f"{extra['source_file']}. Not auto-placed into Practice/Mock."
                )
                stimulus = _upsert_stimulus(
                    program,
                    f"{title} Source",
                    extra["context"],
                    source_note,
                )
                _upsert_question(
                    program,
                    title,
                    stimulus,
                    extra["prompt"],
                    source_note,
                    qtype,
                )

        canonical_qs = Question._default_manager.filter(
            program=program,
            skill=skill,
            is_active=True,
            title__regex=r"^Writing S([1-9]|[1-4]\d|50) P[12] Q1$",
        )
        extra_qs = Question._default_manager.filter(
            program=program,
            skill=skill,
            is_active=True,
            title__regex=r"^Writing Extra P2 Q\d{2}$",
        )
        placement_counts = {
            part_no: PartQuestion._default_manager.filter(part=part).count()
            for part_no, part in parts.items()
        }

        if canonical_qs.count() != 100:
            raise CommandError(f"Expected 100 active canonical Writing questions; found {canonical_qs.count()}.")
        if extra_qs.count() != 10:
            raise CommandError(f"Expected 10 supplementary Writing questions; found {extra_qs.count()}.")
        if placement_counts != {1: 50, 2: 50}:
            raise CommandError(f"Writing Practice placement mismatch: {placement_counts}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("WRITING V39 IMPORT COMPLETE"))
        self.stdout.write(f"Program: {program}")
        self.stdout.write(f"Practice: {mock.title} ({mock.slug})")
        self.stdout.write("Canonical Writing: 50 Sets × 2 Parts = 100 tasks")
        self.stdout.write("Supplementary Part 2: 10 tasks preserved, not auto-placed")
        self.stdout.write("Practice placements: Part 1 = 50, Part 2 = 50")
        self.stdout.write(f"Question type used: {qtype}")
