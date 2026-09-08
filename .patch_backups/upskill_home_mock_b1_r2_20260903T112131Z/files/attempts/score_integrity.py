from django.db.models.signals import post_save
from django.dispatch import receiver

from .audio_quality import analyze_response_audio
from .models import StudentResponse


BLANK_MARKERS = {
    "[blank_audio]",
    "blank_audio",
    "[blank audio]",
    "[no_speech]",
    "[no speech]",
    "no_speech",
    "[silence]",
    "silence",
}


def feedback_dict(response):
    value = response.ai_feedback
    return value if isinstance(value, dict) else {}


def transcript_text(response):
    feedback = feedback_dict(response)

    for value in (
        feedback.get("transcript"),
        feedback.get("text"),
        feedback.get("transcription"),
        feedback.get("recognized_text"),
        response.text_response,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def explicit_blank(response):
    feedback = feedback_dict(response)
    transcript = transcript_text(response).lower().strip()
    status = str(feedback.get("status", "")).lower().strip()
    error_code = str(feedback.get("error_code", "")).lower().strip()

    return (
        transcript in BLANK_MARKERS
        or status in {"blank_audio", "no_speech", "silence"}
        or error_code in {"blank_audio", "no_speech", "silence"}
    )


def zero_feedback(response, quality, reason):
    feedback = feedback_dict(response).copy()

    feedback.update({
        "status": "no_speech",
        "engine": feedback.get("engine", "local whisper.cpp"),
        "paid_api_used": False,
        "transcript": "[BLANK_AUDIO]",
        "score": 0.0,
        "overall_score": 0.0,
        "practice_cefr": None,
        "cefr_estimate": None,
        "audio_quality": quality,
        "quality_gate_reason": reason,
        "rubric": {
            "task": 0.0,
            "task_max": 25.0,
            "language": 0.0,
            "language_max": 20.0,
            "vocabulary": 0.0,
            "vocabulary_max": 20.0,
            "fluency": 0.0,
            "fluency_max": 20.0,
            "intelligibility": 0.0,
            "intelligibility_max": 15.0,
        },
        "strengths": [],
        "improvements": [
            "No usable speech was detected in this recording.",
            "Check the microphone, reduce background noise and record the answer again.",
        ],
        "summary": (
            "This recording did not pass the audio-quality gate. "
            "It is treated as not scorable and receives a practice score of 0."
        ),
    })

    return feedback


@receiver(post_save, sender=StudentResponse)
def enforce_speaking_audio_integrity(sender, instance, **kwargs):
    try:
        question = instance.attempt_question.question
    except Exception:
        return

    if getattr(question, "skill", "") != "speaking":
        return

    quality = analyze_response_audio(instance)

    failed_quality = (
        quality.get("ok") is False
        and quality.get("reason")
        in {"missing_audio", "too_short", "too_quiet", "no_speech"}
    )

    if not failed_quality and not explicit_blank(instance):
        return

    reason = (
        quality.get("reason")
        if failed_quality
        else "transcript_marked_blank"
    )

    final_score = (
        instance.evaluator_score
        if instance.evaluator_score is not None
        else 0
    )

    StudentResponse.objects.filter(pk=instance.pk).update(
        ai_score=0,
        final_score=final_score,
        ai_feedback=zero_feedback(
            instance,
            quality,
            reason,
        ),
    )
