import re
from collections import Counter
from difflib import SequenceMatcher

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

FILLERS = {
    "um", "uh", "erm", "er", "hmm", "like", "youknow",
}

COMMON_FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "because", "so", "if",
    "i", "you", "he", "she", "we", "they", "it", "my", "your",
    "is", "am", "are", "was", "were", "be", "been", "to", "of",
    "in", "on", "at", "for", "from", "with", "this", "that",
}


def _feedback(response):
    value = response.ai_feedback
    return value if isinstance(value, dict) else {}


def _transcript(response):
    feedback = _feedback(response)

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


def _words(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())


def _clean_reference(text):
    if not text:
        return ""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.strip().startswith("•")
    ]

    return " ".join(lines)


def _word_error_rate(reference_words, hypothesis_words):
    n = len(reference_words)

    if n == 0:
        return 1.0

    m = len(hypothesis_words)
    previous = list(range(m + 1))

    for i, ref_word in enumerate(reference_words, start=1):
        current = [i]

        for j, hyp_word in enumerate(hypothesis_words, start=1):
            substitution = previous[j - 1] + (ref_word != hyp_word)
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            current.append(min(substitution, insertion, deletion))

        previous = current

    return min(1.0, previous[m] / float(n))


def _clamp(value, low, high):
    return max(low, min(high, value))


def _round(value):
    return round(float(value), 1)


def _cefr_estimate(score, enough_speech):
    if not enough_speech:
        return None

    # Practice-only conservative estimate, not an official Cambridge mapping.
    if score >= 84:
        return "B1"
    if score >= 68:
        return "A2"
    if score >= 50:
        return "A1"

    return "Below A1"


def _quality_gate(response, transcript, quality):
    words = _words(transcript)
    normalized = transcript.lower().strip()

    if normalized in BLANK_MARKERS:
        return False, "blank_transcript"

    if (
        quality.get("ok") is False
        and quality.get("reason")
        in {"missing_audio", "too_short", "too_quiet", "no_speech"}
    ):
        return False, quality.get("reason")

    if len(words) < 2:
        return False, "insufficient_words"

    return True, None


def _repetition_ratio(words):
    if not words:
        return 1.0

    counts = Counter(words)
    most_common = counts.most_common(1)[0][1]
    return most_common / len(words)


def _open_response_rubric(part_order, words, quality):
    word_count = len(words)
    duration = float(quality.get("duration") or 0)
    speech_ratio = float(quality.get("speech_ratio") or 0.0)

    if duration <= 0:
        duration = max(1.0, word_count / 2.0)

    wpm = word_count / duration * 60.0

    unique_words = set(words)
    lexical_diversity = len(unique_words) / max(1, word_count)

    content_words = [
        word for word in words
        if word not in COMMON_FUNCTION_WORDS
        and word not in FILLERS
    ]

    unique_content = len(set(content_words))
    filler_count = sum(1 for word in words if word in FILLERS)
    filler_ratio = filler_count / max(1, word_count)
    repeat_ratio = _repetition_ratio(words)

    if part_order == 1:
        target_words = 8
        strong_words = 14
    elif part_order == 2:
        target_words = 16
        strong_words = 28
    else:
        target_words = 40
        strong_words = 70

    task_ratio = _clamp(word_count / target_words, 0.0, 1.0)
    task_bonus = _clamp(
        (word_count - target_words)
        / max(1, strong_words - target_words),
        0.0,
        1.0,
    )

    task = 25.0 * (
        0.80 * task_ratio
        + 0.20 * task_bonus
    )

    language_base = _clamp(
        0.45
        + 0.45 * lexical_diversity
        - 0.55 * filler_ratio
        - 0.35 * max(0.0, repeat_ratio - 0.35),
        0.0,
        1.0,
    )
    language = 20.0 * language_base

    vocab_base = _clamp(
        (
            unique_content
            / max(5.0, target_words * 0.55)
        )
        * 0.65
        + lexical_diversity * 0.35,
        0.0,
        1.0,
    )
    vocabulary = 20.0 * vocab_base

    if wpm < 45:
        pace_score = wpm / 45.0 * 0.55
    elif wpm <= 170:
        pace_score = (
            0.55
            + _clamp((wpm - 45) / 125.0, 0.0, 1.0)
            * 0.45
        )
    else:
        pace_score = _clamp(
            1.0 - (wpm - 170) / 140.0,
            0.45,
            1.0,
        )

    fluency_base = _clamp(
        pace_score
        * (
            1.0
            - min(0.45, filler_ratio * 2.2)
        )
        * (
            1.0
            - min(
                0.35,
                max(0.0, repeat_ratio - 0.35),
            )
        ),
        0.0,
        1.0,
    )
    fluency = 20.0 * fluency_base

    clarity_base = _clamp(
        0.35
        + 0.65 * min(
            1.0,
            speech_ratio / 0.55,
        ),
        0.0,
        1.0,
    )
    intelligibility = 15.0 * clarity_base

    return {
        "task": _round(task),
        "language": _round(language),
        "vocabulary": _round(vocabulary),
        "fluency": _round(fluency),
        "intelligibility": _round(intelligibility),
        "diagnostics": {
            "word_count": word_count,
            "words_per_minute": round(wpm, 1),
            "lexical_diversity": round(
                lexical_diversity,
                3,
            ),
            "filler_ratio": round(
                filler_ratio,
                3,
            ),
            "repetition_ratio": round(
                repeat_ratio,
                3,
            ),
            "unique_content_words": unique_content,
        },
    }


def _read_aloud_rubric(prompt_text, transcript, quality):
    reference_words = _words(
        _clean_reference(prompt_text)
    )
    hypothesis_words = _words(transcript)

    sequence_similarity = SequenceMatcher(
        None,
        reference_words,
        hypothesis_words,
    ).ratio()

    wer = _word_error_rate(
        reference_words,
        hypothesis_words,
    )

    accuracy = _clamp(
        0.55 * sequence_similarity
        + 0.45 * (1.0 - wer),
        0.0,
        1.0,
    )

    speech_ratio = float(
        quality.get("speech_ratio") or 0.0
    )

    clarity = _clamp(
        0.40
        + 0.60 * min(
            1.0,
            speech_ratio / 0.55,
        ),
        0.0,
        1.0,
    )

    task = 25.0 * accuracy
    language = 20.0 * accuracy
    vocabulary = 20.0 * accuracy
    fluency = 20.0 * _clamp(
        0.75 * accuracy
        + 0.25 * clarity,
        0.0,
        1.0,
    )
    intelligibility = 15.0 * _clamp(
        0.70 * accuracy
        + 0.30 * clarity,
        0.0,
        1.0,
    )

    return {
        "task": _round(task),
        "language": _round(language),
        "vocabulary": _round(vocabulary),
        "fluency": _round(fluency),
        "intelligibility": _round(
            intelligibility
        ),
        "diagnostics": {
            "reference_word_count": len(
                reference_words
            ),
            "transcript_word_count": len(
                hypothesis_words
            ),
            "sequence_similarity": round(
                sequence_similarity,
                3,
            ),
            "word_error_rate": round(
                wer,
                3,
            ),
            "read_aloud_accuracy": round(
                accuracy,
                3,
            ),
        },
    }


def evaluate_response(response):
    feedback = _feedback(response).copy()
    transcript = _transcript(response)
    quality = analyze_response_audio(response)

    passed, reason = _quality_gate(
        response,
        transcript,
        quality,
    )

    if not passed:
        rubric = {
            "task": 0.0,
            "language": 0.0,
            "vocabulary": 0.0,
            "fluency": 0.0,
            "intelligibility": 0.0,
            "diagnostics": {
                "quality_gate_reason": reason,
            },
        }
        score = 0.0
        cefr = None
        strengths = []
        improvements = [
            "No scorable spoken response was detected.",
            "Check your microphone and record a complete answer.",
        ]

    else:
        question = response.attempt_question.question
        part = response.attempt_question.part
        part_order = int(
            getattr(part, "order", 0) or 0
        )

        if (
            question.question_type == "read_aloud"
            or part_order in {3, 4}
        ):
            rubric = _read_aloud_rubric(
                question.prompt_text,
                transcript,
                quality,
            )
        else:
            rubric = _open_response_rubric(
                part_order,
                _words(transcript),
                quality,
            )

        score = _round(
            rubric["task"]
            + rubric["language"]
            + rubric["vocabulary"]
            + rubric["fluency"]
            + rubric["intelligibility"]
        )

        word_count = len(_words(transcript))
        duration = float(
            quality.get("duration") or 0
        )

        if (
            part_order == 1
            and word_count < 3
        ):
            score = min(score, 25.0)
        elif (
            part_order == 2
            and word_count < 6
        ):
            score = min(score, 30.0)
        elif (
            part_order == 5
            and (
                word_count < 20
                or duration < 15
            )
        ):
            score = min(score, 38.0)

        if (
            _repetition_ratio(
                _words(transcript)
            )
            > 0.60
        ):
            score = min(score, 30.0)

        enough_speech = (
            word_count >= 4
            and duration >= 2.0
        )

        cefr = _cefr_estimate(
            score,
            enough_speech,
        )

        strengths = []

        if rubric["fluency"] >= 14:
            strengths.append(
                "The response shows reasonably steady spoken delivery."
            )

        if rubric["vocabulary"] >= 14:
            strengths.append(
                "The response uses a useful range of vocabulary for practice."
            )

        if rubric["task"] >= 18:
            strengths.append(
                "The response is sufficiently developed for this practice task."
            )

        improvements = []

        if rubric["task"] < 15:
            improvements.append(
                "Develop the answer further and include more relevant detail."
            )

        if rubric["fluency"] < 12:
            improvements.append(
                "Aim for a steadier pace with fewer long pauses or fillers."
            )

        if rubric["vocabulary"] < 12:
            improvements.append(
                "Use a wider range of specific words rather than repeating the same vocabulary."
            )

        if rubric["intelligibility"] < 10:
            improvements.append(
                "Speak clearly and close enough to the microphone for the words to be recognised reliably."
            )

    feedback.update({
        "status": (
            "ai_graded_v2"
            if score > 0
            else "no_speech"
        ),
        "scoring_engine": "speaking_practice_v2",
        "scoring_version": 2,
        "score": score,
        "overall_score": score,
        "practice_cefr": cefr,
        "cefr_estimate": cefr,
        "audio_quality": quality,
        "rubric": {
            "task": rubric["task"],
            "task_max": 25.0,
            "language": rubric["language"],
            "language_max": 20.0,
            "vocabulary": rubric["vocabulary"],
            "vocabulary_max": 20.0,
            "fluency": rubric["fluency"],
            "fluency_max": 20.0,
            "intelligibility": rubric["intelligibility"],
            "intelligibility_max": 15.0,
        },
        "diagnostics": rubric.get(
            "diagnostics",
            {},
        ),
        "strengths": strengths,
        "improvements": improvements,
        "grading_notice": (
            "Practice estimate generated locally. "
            "This is not an official Cambridge/Upskill score "
            "or proprietary Cambridge scoring model."
        ),
    })

    return {
        "score": score,
        "cefr": cefr,
        "feedback": feedback,
    }


def apply_score(response):
    result = evaluate_response(response)

    final_score = (
        response.evaluator_score
        if response.evaluator_score is not None
        else result["score"]
    )

    StudentResponse.objects.filter(
        pk=response.pk
    ).update(
        ai_score=result["score"],
        final_score=final_score,
        ai_feedback=result["feedback"],
    )

    return result


@receiver(post_save, sender=StudentResponse)
def apply_v2_after_local_grading(
    sender,
    instance,
    **kwargs,
):
    try:
        question = (
            instance
            .attempt_question
            .question
        )
    except Exception:
        return

    if getattr(question, "skill", "") != "speaking":
        return

    transcript = _transcript(instance)

    # Initial browser upload can happen before local STT
    # has produced a transcript.
    if not transcript:
        return

    feedback = _feedback(instance)

    # The CEFR B1 specification grader is authoritative for newly processed
    # recordings. Do not overwrite its six-criterion evidence with legacy v2.
    if (
        feedback.get("scoring_spec") == "cefr_b1_speaking_v1.0"
        or str(feedback.get("scoring_version") or "") in {"3", "3.0"}
    ):
        return

    if (
        feedback.get("scoring_engine")
        == "speaking_practice_v2"
        and feedback.get("scoring_version") == 2
    ):
        return

    apply_score(instance)
