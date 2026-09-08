from django.core.management.base import BaseCommand
from assessments.models import TestPart

class Command(BaseCommand):
    help = "Report Cambridge Speaking content readiness."

    def handle(self, *args, **options):
        parts = TestPart.objects.filter(
            section__mock_test__program__code="cambridge-general",
            section__skill="speaking",
        ).select_related("section__mock_test").order_by(
            "section__mock_test__title", "order"
        )

        for part in parts:
            count = part.question_assignments.count()
            self.stdout.write(
                f"{part.section.mock_test.title} | Part {part.order} | "
                f"{part.title} | questions={count} | active={part.is_active}"
            )
