from decimal import Decimal

from celery import shared_task
from django.db import transaction

from attempts.models import StudentResponse
from .b1_attempt import update_attempt_assessment
from .b1_speaking import SPEC_ID, build_insufficient_item_assessment
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
        item = response.attempt_question
        result = build_insufficient_item_assessment(
            transcript="",
            part_order=item.part.order,
            duration=0,
            silence_ratio=1,
            asr_confidence=None,
            mean_db=None,
            reasons=["No audio file was attached."],
        )
        result["engine"] = "CEFR B1 aligned practice specification"
        response.ai_score = None
        response.final_score = None
        response.review_status = StudentResponse.ReviewStatus.AI_GRADED
        response.ai_feedback = result
        response.save()
        update_attempt_assessment(response.attempt_question.attempt)
        return {"status": "no_audio", "assessment_status": "INSUFFICIENT_EVIDENCE"}

    response.review_status = StudentResponse.ReviewStatus.AI_QUEUED
    response.ai_feedback = {
        "status": "processing",
        "engine": "local whisper.cpp",
        "scoring_spec": SPEC_ID,
        "scoring_version": 3,
        "assessment_status": "PROCESSING",
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
                # Speaking practice scores are stored on the existing 0-100
                # report scale. Point-equivalent data remains in the JSON result.
                score_percent = Decimal(str(result["score_total"])).quantize(
                    Decimal("0.01")
                )
                result["points_equivalent"] = str(
                    (
                        Decimal(str(item.points))
                        * score_percent
                        / Decimal("100")
                    ).quantize(Decimal("0.01"))
                )
                locked.ai_feedback = result
                locked.ai_score = score_percent
                locked.final_score = score_percent
                locked.review_status = StudentResponse.ReviewStatus.AI_GRADED

            elif result.get("status") == "no_speech":
                # The recording was processed successfully but is intentionally unscored.
                locked.ai_score = None
                locked.final_score = None
                locked.review_status = StudentResponse.ReviewStatus.AI_GRADED

            else:
                locked.review_status = StudentResponse.ReviewStatus.PENDING

            locked.save()

        update_attempt_assessment(response.attempt_question.attempt)

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
            "scoring_spec": SPEC_ID,
            "scoring_version": 3,
            "assessment_status": "PROCESSING",
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
