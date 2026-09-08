from decimal import Decimal

from celery import shared_task
from django.db import transaction

from attempts.models import StudentResponse
from .local_speaking import evaluate


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=20,
    soft_time_limit=300,
    time_limit=330,
)
def grade_speaking_response(self, response_id):
    try:
        response = (
            StudentResponse.objects
            .select_related(
                "attempt_question__question",
                "attempt_question__part",
            )
            .get(pk=response_id)
        )
    except StudentResponse.DoesNotExist:
        return {"status": "missing"}

    if not response.audio_response:
        response.review_status = StudentResponse.ReviewStatus.PENDING
        response.ai_feedback = {
            "status": "error",
            "error": "No audio file is attached.",
            "paid_api_used": False,
        }
        response.save()
        return {"status": "no_audio"}

    response.review_status = StudentResponse.ReviewStatus.AI_QUEUED
    response.ai_feedback = {
        "status": "processing",
        "engine": "local whisper.cpp",
        "paid_api_used": False,
    }
    response.save()

    try:
        item = response.attempt_question

        result = evaluate(
            response.audio_response.path,
            item.question.prompt_text,
            item.part.order,
        )

        with transaction.atomic():
            locked = StudentResponse.objects.select_for_update().get(
                pk=response.pk
            )

            locked.text_response = result.get("transcript", "")
            locked.ai_feedback = result

            if result.get("status") == "graded":
                max_points = Decimal(str(item.points))
                scaled = (
                    max_points
                    * Decimal(str(result["score_total"]))
                    / Decimal("100")
                ).quantize(Decimal("0.01"))

                locked.ai_score = scaled
                locked.final_score = scaled
                locked.review_status = StudentResponse.ReviewStatus.AI_GRADED

            elif result.get("status") == "no_speech":
                # The recording was processed successfully but is intentionally unscored.
                locked.ai_score = None
                locked.final_score = None
                locked.review_status = StudentResponse.ReviewStatus.AI_GRADED

            else:
                locked.review_status = StudentResponse.ReviewStatus.PENDING

            locked.save()

        return {
            "status": result.get("status"),
            "response_id": response.pk,
            "score_total": result.get("score_total"),
        }

    except Exception as exc:
        response.review_status = StudentResponse.ReviewStatus.PENDING
        response.ai_feedback = {
            "status": "error",
            "engine": "local whisper.cpp",
            "paid_api_used": False,
            "error": str(exc)[:1000],
        }
        response.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            "status": "error",
            "error": str(exc)[:500],
        }

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=15,
    soft_time_limit=90,
    time_limit=120,
)
def grade_writing_response(self, response_id):
    from decimal import Decimal
    from attempts.models import StudentResponse
    from grading.local_writing import analyze

    try:
        response = (
            StudentResponse.objects
            .select_related(
                "attempt_question__question",
                "attempt_question__part",
            )
            .get(pk=response_id)
        )
    except StudentResponse.DoesNotExist:
        return {"status": "missing"}

    item = response.attempt_question

    if not response.text_response.strip():
        response.review_status = StudentResponse.ReviewStatus.PENDING
        response.ai_feedback = {
            "status": "error",
            "error": "No Writing response text was found.",
            "paid_api_used": False,
        }
        response.save()
        return {"status": "empty"}

    response.review_status = StudentResponse.ReviewStatus.AI_QUEUED
    response.ai_feedback = {
        "status": "processing",
        "engine": "local writing practice analyzer",
        "paid_api_used": False,
    }
    response.save()

    try:
        result = analyze(
            item.question.prompt_text,
            response.text_response,
            item.part.title,
        )

        max_points = Decimal(str(item.points))
        scaled = (
            max_points
            * Decimal(str(result["score_total"]))
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        response.ai_score = scaled
        response.final_score = scaled
        response.ai_feedback = result
        response.review_status = StudentResponse.ReviewStatus.AI_GRADED
        response.save()

        return {
            "status": "graded",
            "response_id": response.pk,
            "score_total": result["score_total"],
        }

    except Exception as exc:
        response.review_status = StudentResponse.ReviewStatus.PENDING
        response.ai_feedback = {
            "status": "error",
            "engine": "local writing practice analyzer",
            "paid_api_used": False,
            "error": str(exc)[:1000],
        }
        response.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {"status": "error", "error": str(exc)[:500]}
