"""Add standalone mock material without altering Practice or student attempts."""
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from django.db import transaction

from assessments.models import MockTest, Program, TestPart, TestSection
from assessments.skill_mock import contents
from assessments.skill_mock_data import LISTENING, MINUTES, READING, SKILLS, SLUGS, SPEAKING, WRITING
from question_bank.models import AcceptableAnswer, PartQuestion, Question, QuestionOption, Stimulus


class Command(BaseCommand):
    help = "Add four original single-skill starter mocks (26 questions); never overwrite Practice or existing mock edits."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Read-only readiness and audio-file check.")

    @transaction.atomic
    def handle(self, *args, **options):
        program = Program.objects.filter(code="cambridge-general").first()
        if not program:
            raise CommandError("Cambridge program cambridge-general is missing. No changes made.")
        if not options["check"]:
            for skill in SKILLS:
                test, created = MockTest.objects.get_or_create(slug=SLUGS[skill], defaults={
                    "program": program, "title": f"{skill.title()} Mock Test",
                    "description": "One complete skill test. Original B1-level starter material; not an official Cambridge exam.",
                    "instructions": "Answer the questions in order. Finish this test before starting another mock. Your progress is saved after each submitted answer.",
                    "delivery_mode": "full_mock", "duration_minutes": MINUTES[skill],
                    "is_published": False,
                })
                if not created:
                    # Admin edits, intentional unpublishing, placements, and all
                    # previous attempts remain exactly as the operator left them.
                    continue
                section = TestSection.objects.create(mock_test=test, title=skill.title(), skill=skill,
                                                     order=1, duration_seconds=MINUTES[skill] * 60)
                getattr(self, f"seed_{skill}")(program, section)
                test.is_published = True
                test.save(update_fields=["is_published", "updated_at"])
        self.check_ready()

    def part(self, section, order, title, **kwargs):
        return TestPart.objects.create(section=section, order=order, title=title, **kwargs)

    def question(self, program, part, order, **kwargs):
        question = Question.objects.create(program=program, skill=part.section.skill,
            title=f"Starter mock V29 — {part.section.skill} {part.order}.{order}",
            cefr_level="B1", **kwargs)
        PartQuestion.objects.create(part=part, question=question, order=order)
        return question

    def objective(self, program, part, order, spec, stimulus=None):
        is_choice = "options" in spec
        question = self.question(program, part, order, stimulus=stimulus,
            question_type="single_choice" if is_choice else "gap_fill",
            prompt_text=spec["prompt"], automatic_marking=True)
        if is_choice:
            for index, text in enumerate(spec["options"]):
                QuestionOption.objects.create(question=question, text=text, order=index + 1,
                                              is_correct=index == spec["correct"])
        else:
            AcceptableAnswer.objects.create(question=question, answer_text=spec["answer"])
        return question

    def seed_reading(self, program, section):
        for number, (title, specs) in enumerate(READING, 1):
            part = self.part(section, number, title, question_count=len(specs))
            for order, spec in enumerate(specs, 1):
                stimulus = Stimulus.objects.create(program=program,
                    title=f"Starter mock V29 reading {number}.{order}", content=spec["text"],
                    source_notes="Original unofficial B1-level starter material.")
                self.objective(program, part, order, spec, stimulus)

    def seed_listening(self, program, section):
        for number, spec in enumerate(LISTENING, 1):
            part = self.part(section, number, spec["title"], question_count=1,
                              prompt_mode="text_audio")
            stimulus = Stimulus.objects.create(program=program, title=f"Starter mock V29 listening {number}",
                stimulus_type="audio", transcript=spec["transcript"],
                source_notes="Original unofficial exercise. Bundled synthetic English speech (CMU Flite).")
            source = finders.find(f"audio/skill-mock-v29/listening-{number}.mp3")
            if not source:
                raise CommandError(f"Missing bundled listening audio {number}; transaction rolled back.")
            # Django's configured storage chooses a unique name on conflict.
            # Existing media files are never overwritten or deleted.
            stimulus.audio_file.save(f"skill-mock-v29-listening-{number}.mp3",
                                     ContentFile(Path(source).read_bytes()), save=True)
            self.objective(program, part, 1, spec, stimulus)

    def seed_speaking(self, program, section):
        for number, (title, prompts, qtype, prep, seconds) in enumerate(SPEAKING, 1):
            part = self.part(section, number, title, question_count=len(prompts), question_visible=True,
                recording_required=True, preparation_seconds=prep, response_seconds=seconds,
                minimum_response_seconds=60 if number == 5 else 0)
            for order, prompt in enumerate(prompts, 1):
                self.question(program, part, order, question_type=qtype, prompt_text=prompt,
                              ai_grading_required=True, default_points=100)

    def seed_writing(self, program, section):
        for number, (title, prompt, minimum, maximum) in enumerate(WRITING, 1):
            part = self.part(section, number, title, question_count=1, response_seconds=900,
                              min_word_count=minimum)
            self.question(program, part, 1, question_type="long_text", prompt_text=prompt,
                min_word_count=minimum, max_word_count=maximum,
                ai_grading_required=True, default_points=100)

    def check_ready(self):
        for skill in SKILLS:
            test = MockTest.objects.select_related("program").filter(slug=SLUGS[skill], is_published=True).first()
            parts = contents(test) if test else []
            if not parts:
                raise CommandError(f"{skill.title()} mock is unpublished or incomplete. Existing content is not overwritten; review it in Admin.")
            for part in parts:
                for assignment in part.question_assignments.filter(question__is_active=True).select_related("question__stimulus"):
                    question = assignment.question
                    if question.question_type == "single_choice" and question.options.filter(is_correct=True).count() != 1:
                        raise CommandError(f"Question {question.pk} needs exactly one correct option.")
                    if question.question_type in ("gap_fill", "short_answer") and not question.acceptable_answers.exists():
                        raise CommandError(f"Question {question.pk} needs an answer key.")
                    if skill == "listening":
                        audio = question.prompt_audio or question.stimulus.audio_file
                        if not audio.storage.exists(audio.name):
                            raise CommandError(f"Listening audio is missing for question {question.pk}.")
            count = sum(p.mock_question_count for p in parts)
            self.stdout.write(self.style.SUCCESS(f"{skill.title()}: {len(parts)} parts, {count} questions — ready."))
