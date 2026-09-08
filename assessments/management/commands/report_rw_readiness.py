from django.core.management.base import BaseCommand
from assessments.models import TestPart

class Command(BaseCommand):
    help = "Report Cambridge Reading and Writing readiness."

    def handle(self, *args, **options):
        for skill in ("reading", "writing"):
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(skill.upper()))

            parts = TestPart.objects.filter(
                section__mock_test__program__code="cambridge-general",
                section__skill=skill,
            ).select_related("section__mock_test").order_by(
                "section__mock_test__title", "order"
            )

            for part in parts:
                self.stdout.write(
                    f"{part.section.mock_test.title} | "
                    f"Part {part.order} | {part.title} | "
                    f"questions={part.question_assignments.count()} | "
                    f"min_words={part.min_word_count or '-'} | "
                    f"published={part.section.mock_test.is_published}"
                )
