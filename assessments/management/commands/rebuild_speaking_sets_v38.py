from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.models import MockTest, Program, TestPart, TestSection
from question_bank.models import PartQuestion, Question
from core.speaking_audio_gate_v38_6 import sync_speaking_practice_publication

SOURCE_JSON = Path(__file__).resolve().parents[2] / "speaking_bank_v38_5.json"
PRACTICE_SLUG = "cambridge-speaking-practice-1"
TITLE_RE = re.compile(r"^Speaking S(\d+) P(\d+) Q(\d+)$", re.I)

PART_SPECS = {
    1: dict(title="Part 1 · Listen and answer", instructions="Listen to the question and answer in English.", prompt_mode="audio", question_visible=False, preparation_seconds=5, response_seconds=10, minimum_response_seconds=None, question_count=4, max_audio_plays=1),
    2: dict(title="Part 2 · Longer answers", instructions="Listen to the question and give a longer answer in English.", prompt_mode="audio", question_visible=False, preparation_seconds=5, response_seconds=20, minimum_response_seconds=None, question_count=4, max_audio_plays=1),
    3: dict(title="Part 3 · Read aloud", instructions="Read each sentence aloud clearly.", prompt_mode="text", question_visible=True, preparation_seconds=5, response_seconds=10, minimum_response_seconds=None, question_count=4, max_audio_plays=None),
    4: dict(title="Part 4 · Extended read aloud", instructions="Read each longer sentence aloud clearly.", prompt_mode="text", question_visible=True, preparation_seconds=5, response_seconds=10, minimum_response_seconds=None, question_count=4, max_audio_plays=None),
    5: dict(title="Part 5 · Leave a message", instructions="Prepare for 40 seconds, then leave the requested message.", prompt_mode="text", question_visible=True, preparation_seconds=40, response_seconds=60, minimum_response_seconds=60, question_count=1, max_audio_plays=None),
}


def program():
    qs = Program.objects.filter(code="cambridge-general")
    if not qs.exists():
        qs = Program.objects.filter(name__icontains="Cambridge")
    if not qs.exists():
        qs = Program.objects.filter(name__icontains="General English")
    obj = qs.order_by("pk").first()
    if not obj:
        raise CommandError("Cambridge / General English Program was not found.")
    return obj


def source_data():
    if not SOURCE_JSON.exists():
        raise CommandError(f"Speaking source JSON missing: {SOURCE_JSON}")
    return json.loads(SOURCE_JSON.read_text(encoding="utf-8"))


def source_audio_rel(part_no: int, filename: str) -> str:
    return f"question_bank/question_audio/imported/speaking/source_library/part_{part_no}/{filename}"


def p5_prompt(row):
    bullets = row.get("bullets") or []
    lines = [f"Task: {row.get('task','').strip()}", "", "You should:"]
    lines.extend(f"• {item.strip()}" for item in bullets if item.strip())
    return "\\n".join(lines).strip()


def expected_prompt(set_row, part_no, q_no):
    if part_no == 5:
        return p5_prompt(set_row["5"])
    return set_row[str(part_no)][q_no - 1].strip()


def safe_audio_filename(data, part_no, prompt):
    return (data.get("audio_match", {}).get(str(part_no), {}) or {}).get(prompt)


def archive_duplicate(q):
    old = q.title
    q.title = f"[ARCHIVED DUPLICATE SPEAKING V38.5.1] {old} #{q.pk}"[:200]
    q.is_active = False
    q.save(update_fields=["title", "is_active", "updated_at"])


def upsert_question(prog, data, set_no, part_no, q_no):
    title = f"Speaking S{set_no} P{part_no} Q{q_no}"
    matches = list(Question.objects.filter(program=prog, skill="speaking", title=title).order_by("pk"))
    if matches:
        # Prefer a record already used by attempt history, otherwise the oldest stable row.
        matches.sort(key=lambda q: (0 if q.attempt_questions.exists() else 1, q.pk))
        q = matches[0]
        for extra in matches[1:]:
            if extra.attempt_questions.exists():
                archive_duplicate(extra)
            else:
                extra.delete()
    else:
        q = Question(program=prog, skill="speaking", title=title)

    set_row = data["sets"][str(set_no)]
    prompt = expected_prompt(set_row, part_no, q_no)
    q.title = title
    q.skill = "speaking"
    q.question_type = "read_aloud" if part_no in (3, 4) else "recorded_response"
    q.prompt_text = prompt
    q.show_prompt_text = part_no >= 3
    q.difficulty = "medium"
    q.cefr_level = ""
    q.default_points = 1
    q.automatic_marking = False
    q.ai_grading_required = True
    q.manual_review_allowed = True
    q.preparation_seconds = 40 if part_no == 5 else 5
    q.response_seconds = 60 if part_no == 5 else (20 if part_no == 2 else 10)
    q.evaluator_notes = (
        f"Speaking Set {set_no}, Part {part_no}, Question {q_no}. "
        "Source: Cambridge_Upskill_Speaking_Mock_Sets_2_to_31 supplied by the client. "
        "Independent practice material; not an official Cambridge publication."
    )
    q.is_active = True

    # Preserve an admin replacement audio on reruns. Only fill a blank field from a safe
    # filename-to-question match. Parts 3-5 intentionally have no prompt audio requirement.
    if part_no in (1, 2) and not q.prompt_audio:
        filename = safe_audio_filename(data, part_no, prompt)
        if filename:
            rel = source_audio_rel(part_no, filename)
            full = Path(settings.MEDIA_ROOT) / rel
            if full.exists():
                q.prompt_audio.name = rel

    q.save()
    return q


def normalize_practice_structure(prog):
    test, _ = MockTest.objects.get_or_create(
        slug=PRACTICE_SLUG,
        defaults={"program": prog, "title": "Cambridge Speaking Practice"},
    )
    test.program = prog
    test.title = "Cambridge Speaking Practice"
    test.description = "Speaking Sets 2–31 · five-part Cambridge Upskill-style practice."
    test.instructions = "Complete all five Speaking parts. Each new practice attempt advances to the next Set."
    test.duration_minutes = 12
    test.delivery_mode = "practice"
    test.is_published = False
    test.save()

    speaking_sections = list(test.sections.filter(skill="speaking").order_by("pk"))
    if speaking_sections:
        section = speaking_sections[0]
    else:
        # Find a free section order safely.
        used = set(test.sections.values_list("order", flat=True))
        order = 1
        while order in used:
            order += 1
        section = TestSection.objects.create(mock_test=test, title="Speaking", skill="speaking", order=order)

    # Park any non-speaking sections out of the attempt by disabling their parts.
    for other in test.sections.exclude(pk=section.pk):
        other.parts.update(is_active=False)

    section.title = "Speaking"
    section.skill = "speaking"
    section.duration_seconds = 720
    section.can_pause = False
    section.is_required = True
    section.save(update_fields=["title", "skill", "duration_seconds", "can_pause", "is_required"])

    # Keep existing part IDs wherever possible.
    parts = {}
    for part_no, spec in PART_SPECS.items():
        part = section.parts.filter(order=part_no).order_by("pk").first()
        if part is None:
            part = TestPart.objects.create(section=section, order=part_no, title=spec["title"])
        for field, value in spec.items():
            setattr(part, field, value)
        part.recording_required = True
        part.is_active = True
        part.save()
        parts[part_no] = part

    # Any extra Speaking parts are old structure; keep records for history but disable them.
    section.parts.exclude(pk__in=[p.pk for p in parts.values()]).update(is_active=False)
    return test, section, parts


class Command(BaseCommand):
    help = "Import/rebuild Speaking Sets 2–31 and connect them to the existing Speaking practice structure."

    def handle(self, *args, **options):
        data = source_data()
        prog = program()
        with transaction.atomic():
            questions = {}
            for set_no in range(2, 32):
                if str(set_no) not in data["sets"]:
                    raise CommandError(f"Source data is missing Set {set_no}")
                for part_no in range(1, 6):
                    count = 1 if part_no == 5 else 4
                    for q_no in range(1, count + 1):
                        questions[(set_no, part_no, q_no)] = upsert_question(
                            prog, data, set_no, part_no, q_no
                        )

            test, section, parts = normalize_practice_structure(prog)
            for part_no, part in parts.items():
                PartQuestion.objects.filter(part=part).delete()
                order = 1
                for set_no in range(2, 32):
                    count = 1 if part_no == 5 else 4
                    for q_no in range(1, count + 1):
                        PartQuestion.objects.create(
                            part=part,
                            question=questions[(set_no, part_no, q_no)],
                            order=order,
                            is_required=True,
                        )
                        order += 1

        active = Question.objects.filter(
            program=prog, skill="speaking", is_active=True,
            title__regex=r"^Speaking S([2-9]|[12][0-9]|3[01]) P[1-5] Q[1-4]$",
        )
        counts = {}
        for p in range(1, 6):
            counts[p] = active.filter(title__regex=rf"^Speaking S\d+ P{p} Q\d+$").count()

        attached = {
            1: active.filter(title__regex=r"^Speaking S\d+ P1 Q\d+$").exclude(prompt_audio="").exclude(prompt_audio__isnull=True).count(),
            2: active.filter(title__regex=r"^Speaking S\d+ P2 Q\d+$").exclude(prompt_audio="").exclude(prompt_audio__isnull=True).count(),
        }
        assignments = {p: PartQuestion.objects.filter(part=parts[p]).count() for p in range(1, 6)}
        public_sets = sync_speaking_practice_publication(prog.pk)

        self.stdout.write("")
        self.stdout.write("SPEAKING SETS 2–31 IMPORT V38.5.1 COMPLETE")
        self.stdout.write(f"Standardized active questions: {active.count()} / 510")
        for p in range(1, 6):
            self.stdout.write(f"Part {p}: questions={counts[p]} practice_assignments={assignments[p]}")
        self.stdout.write(f"Part 1 physical audio attached: {attached[1]} / 120 placements")
        self.stdout.write(f"Part 2 physical audio attached: {attached[2]} / 120 placements")
        self.stdout.write(f"Student-public Speaking Sets with complete physical Part 1/2 audio: {len(public_sets)} / 30")
        self.stdout.write("Browser voice fallback is disabled. Incomplete Sets remain private until all 8 required audio files are uploaded.")

        if active.count() != 510:
            raise CommandError(f"Expected 510 active standardized Speaking questions; found {active.count()}")
        expected = {1:120, 2:120, 3:120, 4:120, 5:30}
        if counts != expected or assignments != expected:
            raise CommandError(f"Speaking validation mismatch: counts={counts}, assignments={assignments}")

