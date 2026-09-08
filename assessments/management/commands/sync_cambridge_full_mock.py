from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.models import MockTest, Program, TestPart, TestSection
from question_bank.models import PartQuestion


class Command(BaseCommand):
    help = (
        "Safely fill the Cambridge full mock from the currently published "
        "Cambridge practice tests. Questions are reused, not duplicated."
    )

    SOURCE_SLUGS = {
        "speaking": ("cambridge-speaking-practice-1",),
        "listening": ("cambridge-listening-practice-1",),
        "reading": (
            "cambridge-reading-source-samples",
            "cambridge-reading-reference-practice",
        ),
        "writing": ("cambridge-writing-source-samples",),
    }

    @transaction.atomic
    def handle(self, *args, **options):
        program = Program.objects.filter(code="cambridge-general").first()
        if program is None:
            raise CommandError("Cambridge program (cambridge-general) was not found.")

        full_mock, _ = MockTest.objects.get_or_create(
            slug="cambridge-upskill-full-mock-1",
            defaults={
                "program": program,
                "title": "Cambridge / General English Full Mock 1",
                "description": (
                    "Complete Speaking, Listening, Reading and Writing in one "
                    "realistic Cambridge-style practice journey."
                ),
                "instructions": (
                    "Complete each skill in order. Your answers are saved as one "
                    "full mock-test attempt and one practice report."
                ),
                "duration_minutes": 92,
                "delivery_mode": MockTest.DeliveryMode.FULL_MOCK,
                "is_published": False,
            },
        )

        changed_fields = []
        if full_mock.program_id != program.id:
            full_mock.program = program
            changed_fields.append("program")
        if full_mock.delivery_mode != MockTest.DeliveryMode.FULL_MOCK:
            full_mock.delivery_mode = MockTest.DeliveryMode.FULL_MOCK
            changed_fields.append("delivery_mode")
        if not full_mock.duration_minutes:
            full_mock.duration_minutes = 92
            changed_fields.append("duration_minutes")
        if changed_fields:
            full_mock.save(update_fields=changed_fields + ["updated_at"])

        copied = 0
        required_skills = ("speaking", "listening", "reading", "writing")

        for section_order, skill in enumerate(required_skills, start=1):
            source_test = self._source_test(program, skill)
            if source_test is None:
                self.stdout.write(self.style.WARNING(f"No published {skill} practice source found."))
                continue

            source_section = (
                source_test.sections.filter(skill=skill)
                .prefetch_related("parts__question_assignments")
                .order_by("order")
                .first()
            )
            if source_section is None:
                self.stdout.write(self.style.WARNING(f"No {skill} section found in {source_test.slug}."))
                continue

            target_section, _ = TestSection.objects.get_or_create(
                mock_test=full_mock,
                skill=skill,
                defaults={
                    "title": source_section.title or skill.title(),
                    "order": section_order,
                    "instructions": source_section.instructions,
                    "duration_seconds": source_section.duration_seconds,
                    "can_pause": False,
                    "is_required": True,
                },
            )

            # Keep the established section row if one already exists, but align
            # harmless display/timing fields with the current practice source.
            section_updates = []
            for field, value in (
                ("title", source_section.title or skill.title()),
                ("order", section_order),
                ("instructions", source_section.instructions),
                ("duration_seconds", source_section.duration_seconds),
                ("is_required", True),
            ):
                if getattr(target_section, field) != value:
                    setattr(target_section, field, value)
                    section_updates.append(field)
            if section_updates:
                target_section.save(update_fields=section_updates)

            source_parts = list(source_section.parts.filter(is_active=True).order_by("order"))
            source_orders = {part.order for part in source_parts}

            # Old full-mock scaffolding sometimes contains placeholder parts
            # with no questions. Deactivate only those empty placeholders when
            # the current practice source no longer has that part number.
            for stale_part in target_section.parts.filter(is_active=True).exclude(order__in=source_orders):
                if not stale_part.question_assignments.exists():
                    stale_part.is_active = False
                    stale_part.save(update_fields=["is_active"])

            for source_part in source_parts:
                target_part = target_section.parts.filter(order=source_part.order).first()
                if target_part is None:
                    target_part = TestPart.objects.create(
                        section=target_section,
                        title=source_part.title,
                        order=source_part.order,
                    )

                part_fields = (
                    "title",
                    "instructions",
                    "prompt_mode",
                    "question_visible",
                    "preparation_seconds",
                    "response_seconds",
                    "minimum_response_seconds",
                    "question_count",
                    "max_audio_plays",
                    "recording_required",
                    "min_word_count",
                    "is_active",
                )
                part_updates = []
                for field in part_fields:
                    value = getattr(source_part, field)
                    if getattr(target_part, field) != value:
                        setattr(target_part, field, value)
                        part_updates.append(field)
                if part_updates:
                    target_part.save(update_fields=part_updates)

                # Only fill missing placements. Existing admin-edited placements
                # are preserved. Reusing the same Question object means later
                # text/audio edits automatically affect Practice and Mock Test.
                existing_question_ids = set(
                    target_part.question_assignments.values_list("question_id", flat=True)
                )
                existing_orders = set(
                    target_part.question_assignments.values_list("order", flat=True)
                )
                next_order = max(existing_orders or {0}) + 1

                for source_assignment in source_part.question_assignments.select_related("question").order_by("order"):
                    if source_assignment.question_id in existing_question_ids:
                        continue
                    preferred_order = source_assignment.order
                    order = preferred_order if preferred_order not in existing_orders else next_order
                    while order in existing_orders:
                        order += 1
                    PartQuestion.objects.create(
                        part=target_part,
                        question=source_assignment.question,
                        order=order,
                        points_override=source_assignment.points_override,
                        is_required=source_assignment.is_required,
                    )
                    existing_question_ids.add(source_assignment.question_id)
                    existing_orders.add(order)
                    next_order = max(next_order, order + 1)
                    copied += 1

        ready = self._is_ready(full_mock)
        if ready and not full_mock.is_published:
            full_mock.is_published = True
            full_mock.save(update_fields=["is_published", "updated_at"])
        elif not ready and full_mock.is_published:
            # Never publish an incomplete full mock after a partial sync.
            full_mock.is_published = False
            full_mock.save(update_fields=["is_published", "updated_at"])

        if ready:
            self.stdout.write(self.style.SUCCESS(
                f"Cambridge full mock is ready and published. {copied} missing question placement(s) added."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Cambridge full mock is still incomplete. {copied} placement(s) added; it remains unpublished."
            ))

    def _source_test(self, program, skill):
        for slug in self.SOURCE_SLUGS.get(skill, ()):
            test = MockTest.objects.filter(
                program=program,
                slug=slug,
                delivery_mode=MockTest.DeliveryMode.PRACTICE,
                is_published=True,
            ).first()
            if test and test.sections.filter(skill=skill).exists():
                return test

        return (
            MockTest.objects.filter(
                program=program,
                delivery_mode=MockTest.DeliveryMode.PRACTICE,
                is_published=True,
                sections__skill=skill,
            )
            .distinct()
            .order_by("title")
            .first()
        )

    def _is_ready(self, mock_test):
        required = {"speaking", "listening", "reading", "writing"}
        sections = list(mock_test.sections.prefetch_related("parts__question_assignments"))
        skills = {section.skill for section in sections}
        if not required.issubset(skills):
            return False
        for skill in required:
            section = next((item for item in sections if item.skill == skill), None)
            if section is None:
                return False
            parts = [part for part in section.parts.all() if part.is_active]
            if not parts:
                return False
            if any(not part.question_assignments.exists() for part in parts):
                return False
        return True
