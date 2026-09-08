from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from accounts.models import User
from assessments.models import MockTest, TestPart
from attempts.models import StudentResponse, TestAttempt
from question_bank.models import Question, Stimulus


@staff_member_required
def content_studio(request):
    cambridge_parts = (
        TestPart.objects
        .filter(section__mock_test__program__code="cambridge-general")
        .select_related("section", "section__mock_test")
        .order_by("section__order", "order")
    )

    readiness = []

    for part in cambridge_parts:
        assignments = part.question_assignments.select_related(
            "question__stimulus"
        )

        audio_count = 0

        for assignment in assignments:
            question = assignment.question

            if question.prompt_audio:
                audio_count += 1
            elif question.stimulus and question.stimulus.audio_file:
                audio_count += 1

        readiness.append(
            {
                "part": part,
                "question_count": assignments.count(),
                "audio_count": audio_count,
            }
        )

    context = {
        "student_count": User.objects.filter(role=User.Role.STUDENT).count(),
        "test_count": MockTest.objects.count(),
        "question_count": Question.objects.count(),
        "stimulus_count": Stimulus.objects.count(),
        "attempt_count": TestAttempt.objects.count(),
        "response_count": StudentResponse.objects.count(),
        "readiness": readiness,
    }

    return render(
        request,
        "core/staff_content_studio.html",
        context,
    )
