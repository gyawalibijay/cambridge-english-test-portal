from django.core.management.base import BaseCommand
from assessments.models import TestPart

class Command(BaseCommand):
    help = "Report Cambridge Listening content readiness."

    def handle(self, *args, **options):
        parts = TestPart.objects.filter(
            section__mock_test__program__code="cambridge-general",
            section__skill="listening",
        ).select_related("section__mock_test").order_by(
            "section__mock_test__title", "order"
        )

        for part in parts:
            assignments = part.question_assignments.select_related("question__stimulus")
            with_audio = 0

            for assignment in assignments:
                q = assignment.question
                if q.prompt_audio or (q.stimulus and q.stimulus.audio_file):
                    with_audio += 1

            self.stdout.write(
                f"{part.section.mock_test.title} | Part {part.order} | "
                f"questions={assignments.count()} | audio={with_audio} | "
                f"play_limit={part.max_audio_plays or 'not configured'}"
            )
