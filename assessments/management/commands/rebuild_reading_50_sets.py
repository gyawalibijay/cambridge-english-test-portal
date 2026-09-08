from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from assessments.models import MockTest, Program, TestPart, TestSection
from assessments.reading_bank_v36_data import SOURCE_NOTE, TOTAL_SETS, load_sets
from attempts.models import AttemptQuestion, TestAttempt
from question_bank.models import AcceptableAnswer, PartQuestion, Question, QuestionOption, Stimulus

CANONICAL_SLUG = "cambridge-reading-reference-practice"
CANONICAL_MARKER = "UPSKILL_READING_50SETS_20260908"
LEGACY_STARTER_SLUGS = {
    "cambridge-reading-skill-mock",
    "cambridge-listening-skill-mock",
    "cambridge-speaking-skill-mock",
    "cambridge-writing-skill-mock",
}
LEGACY_READING_SLUGS = {
    CANONICAL_SLUG,
    "cambridge-reading-source-samples",
    "cambridge-reading-practice-1",
    "cambridge-reading-skill-mock",
}
PART_INSTRUCTIONS = {
    1: "Read and choose the correct answer.",
    2: "Read and choose the correct word.",
    3: "Read each sentence and write the missing word.",
    4: "Read the message and complete the form.",
    5: "Read the text and choose the correct answer for each question.",
}


class Command(BaseCommand):
    help = (
        "Replace all old Cambridge Reading questions with the supplied 50-set bank, "
        "remove known starter/dummy questions, and keep current Listening content untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply the cleanup/import. Without this flag only an audit is printed.")

    def _program(self):
        program = Program.objects.filter(code="cambridge-general").first()
        if program:
            return program
        ranked = []
        for obj in Program.objects.all():
            text = " ".join(str(getattr(obj, n, "") or "") for n in ("name", "short_name", "code")).lower()
            score = (10 if "cambridge" in text else 0) + (8 if "general english" in text else 0) - (20 if "ielts" in text else 0)
            if score > 0:
                ranked.append((score, obj.pk, obj))
        if not ranked:
            raise CommandError("Cambridge / General English program was not found.")
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return ranked[0][2]

    def _legacy_question_ids(self, program):
        # User explicitly requested a clean Reading reset. Every existing Cambridge
        # Reading question is replaced by the new supplied 50-set bank.
        reading_ids = set(Question.objects.filter(program=program, skill="reading").values_list("pk", flat=True))
        starter_ids = set(Question.objects.filter(program=program, title__startswith="Starter mock V29 —").values_list("pk", flat=True))
        return reading_ids | starter_ids

    def _audit(self, program):
        legacy_ids = self._legacy_question_ids(program)
        attempt_ids = set(AttemptQuestion.objects.filter(question_id__in=legacy_ids).values_list("attempt_id", flat=True)) if legacy_ids else set()
        starter_tests = MockTest.objects.filter(program=program, slug__in=LEGACY_STARTER_SLUGS).count()
        old_reading_tests = MockTest.objects.filter(program=program, slug__in=LEGACY_READING_SLUGS).count()
        new_listening = Question.objects.filter(program=program, skill="listening", title__startswith="Listening S").count()
        self.stdout.write(f"Cambridge program: {program}")
        self.stdout.write(f"Existing Cambridge Reading questions to replace: {len(legacy_ids - set(Question.objects.filter(program=program, title__startswith='Starter mock V29 —').exclude(skill='reading').values_list('pk', flat=True)))}")
        self.stdout.write(f"Known Starter mock V29 questions included in cleanup: {Question.objects.filter(pk__in=legacy_ids, title__startswith='Starter mock V29 —').count()}")
        self.stdout.write(f"Attempts tied to replaced/dummy questions: {len(attempt_ids)}")
        self.stdout.write(f"Legacy starter tests: {starter_tests}")
        self.stdout.write(f"Known old Reading test containers: {old_reading_tests}")
        self.stdout.write(f"Current standardized Listening questions preserved: {new_listening}")
        self.stdout.write("Target Reading import: 50 sets × 5 parts × 4 questions = 1,000 questions")
        return legacy_ids, attempt_ids

    @transaction.atomic
    def handle(self, *args, **options):
        program = self._program()
        legacy_ids, attempt_ids = self._audit(program)
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("AUDIT ONLY. Re-run with --apply to make changes."))
            return

        data = load_sets()
        if len(data) != TOTAL_SETS:
            raise CommandError("Embedded Reading source did not pass its integrity check.")

        # Capture stimuli before deleting questions so only known now-orphaned
        # sources can be removed later.
        legacy_stimulus_ids = set(
            Question.objects.filter(pk__in=legacy_ids, stimulus_id__isnull=False).values_list("stimulus_id", flat=True)
        )

        # Attempts snapshot questions. Old Reading/starter attempts must go first
        # because AttemptQuestion protects Question rows from deletion.
        if attempt_ids:
            deleted_attempts = TestAttempt.objects.filter(pk__in=attempt_ids).count()
            TestAttempt.objects.filter(pk__in=attempt_ids).delete()
        else:
            deleted_attempts = 0

        # Delete known legacy starter test containers. Also delete old Reading-only
        # practice containers so the admin/student UI has one Reading source of truth.
        starter_qs = MockTest.objects.filter(program=program, slug__in=LEGACY_STARTER_SLUGS)
        starter_count = starter_qs.count()
        starter_qs.delete()

        reading_test_qs = MockTest.objects.filter(program=program, slug__in=LEGACY_READING_SLUGS)
        old_reading_test_count = reading_test_qs.count()
        reading_test_qs.delete()

        # Any remaining old Reading containers are now empty; remove only practice
        # tests whose active sections are Reading-only. Full mocks are never deleted.
        removed_empty_reading_tests = 0
        for test in list(MockTest.objects.filter(program=program, delivery_mode="practice")):
            skills = set(test.sections.values_list("skill", flat=True))
            if skills and skills <= {"reading"}:
                qcount = PartQuestion.objects.filter(part__section__mock_test=test).count()
                if qcount == 0:
                    test.delete()
                    removed_empty_reading_tests += 1

        # Delete all previous Cambridge Reading questions and known V29 starter
        # questions from every skill. Current Listening Sx Px Qx items are untouched.
        legacy_questions = Question.objects.filter(pk__in=legacy_ids)
        deleted_questions = legacy_questions.count()
        legacy_questions.delete()

        # Remove only captured stimuli that became truly orphaned.
        orphan_stimuli = Stimulus.objects.filter(pk__in=legacy_stimulus_ids).annotate(q_count=Count("questions")).filter(q_count=0)
        deleted_stimuli = orphan_stimuli.count()
        orphan_stimuli.delete()

        # Create the one canonical Reading Practice bank.
        test = MockTest.objects.create(
            program=program,
            title="Cambridge Reading Practice — 50 Sets",
            slug=CANONICAL_SLUG,
            description=(
                f"{CANONICAL_MARKER}\n{SOURCE_NOTE}\n"
                "50 sets; 5 parts per set; 20 answers per set; 25 minutes per complete set."
            ),
            instructions="Choose Reading from Practice, then complete Parts 1–5. Sets advance automatically.",
            duration_minutes=25,
            delivery_mode="practice",
            is_published=True,
        )
        section = TestSection.objects.create(
            mock_test=test,
            title="Reading",
            skill="reading",
            order=1,
            instructions="Complete the five Reading parts in order.",
            duration_seconds=25 * 60,
            can_pause=False,
            is_required=True,
        )
        parts = {}
        for part_no in range(1, 6):
            parts[part_no] = TestPart.objects.create(
                section=section,
                title=f"Reading Part {part_no}",
                order=part_no,
                instructions=PART_INSTRUCTIONS[part_no],
                prompt_mode="text",
                question_visible=True,
                preparation_seconds=0,
                response_seconds=300,
                question_count=4,
                recording_required=False,
                is_active=True,
            )

        created_questions = 0
        created_stimuli = 0
        created_options = 0
        created_answers = 0

        for set_row in data:
            set_no = int(set_row["set"])
            for part_key, part_spec in set_row["parts"].items():
                part_no = int(part_key)
                part = parts[part_no]
                shared_stimulus = None

                if part_no in (4, 5):
                    shared_stimulus = Stimulus.objects.create(
                        program=program,
                        title=f"Reading S{set_no} P{part_no} Source",
                        stimulus_type="text",
                        content=part_spec.get("stimulus", ""),
                        source_notes=SOURCE_NOTE,
                        is_active=True,
                    )
                    created_stimuli += 1

                for q_spec in part_spec["questions"]:
                    local_q = int(q_spec["q"])
                    source_no = int(q_spec["source_no"])
                    stimulus = shared_stimulus
                    if part_no == 1:
                        stimulus = Stimulus.objects.create(
                            program=program,
                            title=f"Reading S{set_no} P1 Source {local_q}",
                            stimulus_type="text",
                            content=q_spec.get("stimulus", ""),
                            source_notes=SOURCE_NOTE,
                            is_active=True,
                        )
                        created_stimuli += 1

                    is_choice = part_no in (1, 2, 5)
                    question = Question.objects.create(
                        program=program,
                        stimulus=stimulus,
                        title=f"Reading S{set_no} P{part_no} Q{local_q}",
                        skill="reading",
                        question_type="single_choice" if is_choice else "gap_fill",
                        prompt_text=q_spec["prompt"],
                        show_prompt_text=True,
                        cefr_level="",
                        default_points=Decimal("1"),
                        automatic_marking=True,
                        ai_grading_required=False,
                        manual_review_allowed=False,
                        evaluator_notes=(
                            f"Source question {source_no}. {SOURCE_NOTE} "
                            "Answer key supplied in the source workbook."
                        ),
                        is_active=True,
                    )
                    created_questions += 1

                    if is_choice:
                        for index, text in enumerate(q_spec["options"], start=1):
                            QuestionOption.objects.create(
                                question=question,
                                text=text,
                                order=index,
                                is_correct=(index - 1) == int(q_spec["correct"]),
                            )
                            created_options += 1
                    else:
                        for answer in q_spec.get("answers", []):
                            AcceptableAnswer.objects.create(
                                question=question,
                                answer_text=answer,
                                case_sensitive=False,
                            )
                            created_answers += 1

                    PartQuestion.objects.create(
                        part=part,
                        question=question,
                        order=(set_no - 1) * 4 + local_q,
                        points_override=None,
                        is_required=True,
                    )

        # Full mocks that used deleted Reading content must return to Draft until
        # an admin chooses one of the new Reading Sets in Mock Builder.
        unpublished_full_mocks = 0
        for mock in MockTest.objects.filter(program=program, delivery_mode="full_mock", is_published=True):
            reading_sections = mock.sections.filter(skill="reading")
            if not reading_sections.exists():
                continue
            ready = True
            for pno in range(1, 6):
                part = TestPart.objects.filter(section__in=reading_sections, order=pno, is_active=True).first()
                if part is None or not PartQuestion.objects.filter(part=part, question__skill="reading", question__is_active=True).exists():
                    ready = False
                    break
            if not ready:
                mock.is_published = False
                mock.save(update_fields=["is_published", "updated_at"])
                unpublished_full_mocks += 1

        # Final integrity checks.
        standard = Question.objects.filter(program=program, skill="reading", title__startswith="Reading S")
        if standard.count() != 1000:
            raise CommandError(f"Import integrity failed: expected 1000 standardized Reading questions, got {standard.count()}.")
        for part_no, part in parts.items():
            count = PartQuestion.objects.filter(part=part).count()
            if count != 200:
                raise CommandError(f"Reading Part {part_no} integrity failed: expected 200 placements, got {count}.")
        if Question.objects.filter(program=program, title__startswith="Starter mock V29 —").exists():
            raise CommandError("Legacy Starter mock V29 questions remain after cleanup.")

        self.stdout.write(self.style.SUCCESS("READING 50-SET REBUILD COMPLETE"))
        self.stdout.write(f"Deleted old/dummy attempts: {deleted_attempts}")
        self.stdout.write(f"Deleted old/dummy questions: {deleted_questions}")
        self.stdout.write(f"Deleted orphan old stimuli: {deleted_stimuli}")
        self.stdout.write(f"Deleted starter test containers: {starter_count}")
        self.stdout.write(f"Deleted known old Reading test containers: {old_reading_test_count}")
        self.stdout.write(f"Deleted other empty Reading-only practice containers: {removed_empty_reading_tests}")
        self.stdout.write(f"Created Reading questions: {created_questions}")
        self.stdout.write(f"Created choices: {created_options}")
        self.stdout.write(f"Created acceptable answers: {created_answers}")
        self.stdout.write(f"Created Reading stimuli: {created_stimuli}")
        self.stdout.write(f"Full mocks returned to Draft for new Reading selection: {unpublished_full_mocks}")
        self.stdout.write("Preserved current Listening S<set> P<part> Q<question> content.")
