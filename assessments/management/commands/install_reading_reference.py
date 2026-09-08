"""Add a separate, non-destructive Reading bank. Never overwrite existing items."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from assessments.models import MockTest, Program, TestPart, TestSection
from assessments.reading_reference_data import CONTENT, MARKER, PART_SECONDS, SLUG, SOURCE
from question_bank.models import AcceptableAnswer, PartQuestion, Question, QuestionOption, Stimulus


class Command(BaseCommand):
    help = "Add the supplied Reading reference exercises, without changing any existing bank."

    def add_arguments(self, parser):
        parser.add_argument("--publish", action="store_true", help="Publish the validated import.")

    @transaction.atomic
    def handle(self, *args, **options):
        # Lock a stable row: concurrent installers cannot duplicate this import.
        program = Program.objects.filter(code="cambridge-general").first()
        if program is None:
            raise CommandError("Cambridge program not found. No data was imported.")
        Program.objects.filter(pk=program.pk).update(is_active=F("is_active"))
        test = MockTest.objects.filter(slug=SLUG).first()
        if test is not None:
            if MARKER not in test.description or test.program_id != program.pk:
                raise CommandError("Reading slug belongs to different content; refusing to overwrite.")
            # Preserve admin edits and extra questions on repeat runs.
            if not test.sections.filter(skill="reading").exists():
                raise CommandError("Existing Reading import has no section; inspect it before continuing.")
            self.stdout.write("Reading bank already present; question content unchanged.")
        else:
            test = MockTest.objects.create(
                program=program, title="Cambridge Reading Reference Practice", slug=SLUG,
                description=f"{MARKER}\n{SOURCE}\nParts 1 and 3 complete. Part 2 Q1 and Parts 4–5 not supplied.",
                instructions="Practise the supplied Reading parts.", is_published=False,
            )
            section = TestSection.objects.create(
                mock_test=test, title="Reading", skill="reading", order=1,
                duration_seconds=PART_SECONDS, can_pause=False,
            )
            for number in range(1, 6):
                rows = CONTENT.get(number, [])
                part = TestPart.objects.create(
                    section=section, title=f"Reading Part {number}", order=number,
                    question_count=len(rows) or None, question_visible=True,
                    recording_required=False, is_active=bool(rows),
                )
                for position, row in enumerate(rows, 1):
                    key = f"{MARKER} P{number} Q{row['source_number']}"
                    stimulus = Stimulus.objects.create(
                        program=program, title=key, content=row["text"], source_notes=SOURCE,
                    )
                    question = Question.objects.create(
                        program=program, stimulus=stimulus, title=key, skill="reading",
                        question_type="single_choice" if "options" in row else "gap_fill",
                        prompt_text=row.get("prompt", "Write the missing word"),
                        default_points=1, automatic_marking=True, ai_grading_required=False,
                        evaluator_notes=f"{SOURCE}\nAnswer key inferred from the text; not an official supplied key.",
                    )
                    for index, text in enumerate(row.get("options", [])):
                        QuestionOption.objects.create(
                            question=question, text=text, order=index + 1,
                            is_correct=index == row["correct"],
                        )
                    if "answer" in row:
                        AcceptableAnswer.objects.create(question=question, answer_text=row["answer"])
                    PartQuestion.objects.create(part=part, question=question, order=position)
            self.stdout.write("Imported 11 supplied exercises as a separate draft. No existing bank changed.")
        if options["publish"] and not test.is_published:
            test.is_published = True
            test.save(update_fields=["is_published"])
            self.stdout.write("Reading reference practice is now published.")
