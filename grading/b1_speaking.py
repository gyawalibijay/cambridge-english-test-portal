import math
import re
from collections import Counter
from difflib import SequenceMatcher


SPEC_ID = "cefr_b1_speaking_v1.0"
DISCLAIMER = "CEFR B1-aligned practice estimate; not an official Cambridge result."

CRITERION_WEIGHTS = {
    "task_achievement": 0.20,
    "pronunciation_intelligibility": 0.20,
    "fluency": 0.15,
    "grammar": 0.15,
    "vocabulary": 0.15,
    "coherence": 0.15,
}

PART_WEIGHTS = {
    "task_achievement": {1: 0.10, 2: 0.25, 3: 0.15, 4: 0.20, 5: 0.30},
    "pronunciation_intelligibility": {1: 0.05, 2: 0.25, 3: 0.20, 4: 0.25, 5: 0.25},
    "fluency": {1: 0.05, 2: 0.30, 3: 0.15, 4: 0.20, 5: 0.30},
    "grammar": {1: 0.10, 2: 0.40, 3: 0.0, 4: 0.0, 5: 0.50},
    "vocabulary": {1: 0.05, 2: 0.40, 3: 0.0, 4: 0.0, 5: 0.55},
    "coherence": {1: 0.05, 2: 0.40, 3: 0.0, 4: 0.0, 5: 0.55},
}

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
FILLERS = {"um", "uh", "erm", "hmm", "umm", "uhh"}
FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "because", "so", "if", "i",
    "you", "he", "she", "we", "they", "it", "my", "your", "our", "is",
    "am", "are", "was", "were", "be", "been", "to", "of", "in", "on",
    "at", "for", "from", "with", "this", "that", "do", "does", "did",
}
COMMON_VERBS = {
    "am", "is", "are", "was", "were", "be", "been", "have", "has", "had",
    "do", "does", "did", "work", "worked", "study", "studied", "live", "lived",
    "go", "went", "want", "wanted", "plan", "planned", "think", "thought",
    "choose", "chose", "prefer", "preferred", "need", "needed", "will", "would",
    "can", "could", "should", "like", "liked", "enjoy", "enjoyed", "learn",
}
LINKERS = {
    "and", "but", "because", "so", "then", "when", "after", "before", "also",
    "however", "therefore", "first", "finally", "although", "while", "if",
}
REQUEST_WORDS = {
    "please", "could", "would", "call", "contact", "reply", "send", "let", "need",
}


def clamp(value, low, high):
    return max(low, min(high, value))


def rounded(value, digits=2):
    return round(float(value), digits)


def words(text):
    return WORD_RE.findall(str(text or "").lower())


def _content_words(tokens):
    return [word for word in tokens if word not in FUNCTION_WORDS and word not in FILLERS]


def _repeat_ratio(tokens):
    if not tokens:
        return 1.0
    return Counter(tokens).most_common(1)[0][1] / len(tokens)


def _word_error_rate(reference, hypothesis):
    if not reference:
        return 1.0
    previous = list(range(len(hypothesis) + 1))
    for i, ref_word in enumerate(reference, start=1):
        current = [i]
        for j, hyp_word in enumerate(hypothesis, start=1):
            current.append(min(
                previous[j - 1] + (ref_word != hyp_word),
                current[j - 1] + 1,
                previous[j] + 1,
            ))
        previous = current
    return min(1.0, previous[-1] / len(reference))


def _read_aloud_accuracy(prompt, transcript):
    reference = words(prompt)
    hypothesis = words(transcript)
    sequence = SequenceMatcher(None, reference, hypothesis).ratio()
    wer = _word_error_rate(reference, hypothesis)
    return clamp(0.55 * sequence + 0.45 * (1.0 - wer), 0.0, 1.0), wer


def _intent_signal(question, tokens):
    prompt = str(question or "").lower().strip()
    answer = set(tokens)
    joined = " ".join(tokens)
    if not tokens:
        return 0.0
    if "why" in prompt:
        return 1.0 if {"because", "since", "so"} & answer else 0.62
    if "how often" in prompt:
        return 1.0 if {"always", "usually", "often", "sometimes", "daily", "weekly", "never"} & answer else 0.62
    if "what time" in prompt or prompt.startswith("when"):
        return 1.0 if re.search(r"\b\d{1,2}(?::\d{2})?\b", joined) or {"morning", "afternoon", "evening", "night"} & answer else 0.62
    if prompt.startswith(("do ", "are ", "is ", "have ", "can ")):
        return 1.0 if {"yes", "no", "yeah", "not"} & answer or len(tokens) >= 3 else 0.68
    return 1.0 if tokens else 0.0


def _relevance_signal(question, tokens):
    prompt_words = set(_content_words(words(question)))
    answer_words = set(_content_words(tokens))
    if not answer_words:
        return 0.0
    if not prompt_words:
        return 0.7
    overlap = len(prompt_words & answer_words) / len(prompt_words)
    # Lexical overlap is deliberately only a weak signal: valid personal answers
    # often use different names and details from the question.
    return clamp(0.62 + 0.38 * overlap, 0.0, 1.0)


def _criterion(score, confidence, evidence, limitations=None):
    return {
        "score": rounded(clamp(score, 1.0, 4.0), 2),
        "confidence": rounded(clamp(confidence, 0.0, 1.0), 3),
        "evidence": [str(value) for value in evidence if value],
        "limitations": [str(value) for value in (limitations or []) if value],
    }


def _not_scored(reason):
    return {
        "score": None,
        "confidence": None,
        "evidence": [],
        "limitations": [reason],
    }


def _quality_confidence(asr_confidence, silence_ratio, mean_db):
    asr = 0.62 if asr_confidence is None else clamp(asr_confidence, 0.0, 1.0)
    activity = clamp(1.0 - silence_ratio, 0.0, 1.0)
    volume = 0.65 if mean_db is None else clamp((mean_db + 52.0) / 32.0, 0.0, 1.0)
    return clamp(0.58 * asr + 0.27 * activity + 0.15 * volume, 0.25, 0.98)


def _task_score(question, tokens, part_order):
    count = len(tokens)
    intent = _intent_signal(question, tokens)
    relevance = _relevance_signal(question, tokens)
    linker_count = sum(1 for token in tokens if token in LINKERS)

    if part_order == 1:
        # A direct phrase such as "By bus" may fully satisfy a short question.
        score = 2.15 + 0.65 * intent + 0.35 * relevance + 0.25 * min(1.0, count / 4)
        evidence = [f"Direct response contained {count} recognised word(s)."]
    elif part_order == 2:
        detail = min(1.0, max(0, count - 4) / 12)
        connection = min(1.0, linker_count / 2)
        score = 1.65 + 0.65 * intent + 0.35 * relevance + 0.6 * detail + 0.35 * connection
        evidence = [
            f"Response contained {count} recognised words.",
            f"Detected {linker_count} basic connection signal(s).",
        ]
    else:
        request_signal = 1.0 if set(tokens) & REQUEST_WORDS else 0.45
        detail = min(1.0, count / 55)
        connection = min(1.0, linker_count / 4)
        score = 1.25 + 0.55 * intent + 0.3 * relevance + 0.7 * detail + 0.55 * connection + 0.4 * request_signal
        evidence = [
            f"Voicemail contained {count} recognised words.",
            "Requested-action language was detected." if request_signal == 1.0 else "Requested-action language was not clear in the transcript.",
        ]
    return clamp(score, 1.0, 4.0), evidence


def _grammar_score(tokens):
    if not tokens:
        return 1.0
    has_verb = bool(set(tokens) & COMMON_VERBS)
    linker_count = sum(1 for token in tokens if token in LINKERS)
    length_signal = min(1.0, len(tokens) / 20)
    repeats = sum(1 for left, right in zip(tokens, tokens[1:]) if left == right)
    repeat_penalty = min(0.45, repeats * 0.12)
    return clamp(1.45 + (0.75 if has_verb else 0.2) + 0.55 * length_signal + min(0.65, linker_count * 0.18) - repeat_penalty, 1.0, 4.0)


def _vocabulary_score(tokens):
    content = _content_words(tokens)
    if not content:
        return 1.0
    unique = len(set(content))
    length_adjusted_range = min(1.0, unique / max(3.0, math.sqrt(len(tokens)) * 2.25))
    repetition = _repeat_ratio(tokens)
    return clamp(1.65 + 1.65 * length_adjusted_range + 0.5 * (1.0 - repetition), 1.0, 4.0)


def _coherence_score(tokens, part_order):
    if not tokens:
        return 1.0
    linkers = sum(1 for token in tokens if token in LINKERS)
    continuity = min(1.0, len(tokens) / (5 if part_order == 1 else 24))
    connection = min(1.0, linkers / (1 if part_order == 1 else 4))
    return clamp(1.75 + 0.9 * continuity + 0.75 * connection, 1.0, 4.0)


def _fluency_score(tokens, duration, silence_ratio):
    filler_ratio = sum(1 for token in tokens if token in FILLERS) / max(1, len(tokens))
    repetition = _repeat_ratio(tokens)
    continuity = clamp(1.0 - silence_ratio / 0.72, 0.0, 1.0)
    repair_control = clamp(1.0 - max(0.0, repetition - 0.34) * 1.8, 0.0, 1.0)
    filler_control = clamp(1.0 - filler_ratio * 4.0, 0.0, 1.0)
    score = 1.0 + 3.0 * (0.58 * continuity + 0.27 * repair_control + 0.15 * filler_control)
    active_seconds = max(0.5, duration * (1.0 - silence_ratio))
    wpm = len(tokens) / active_seconds * 60.0 if tokens else 0.0
    return clamp(score, 1.0, 4.0), rounded(wpm, 1), rounded(filler_ratio, 3)


def _pronunciation_score(asr_confidence, silence_ratio, mean_db):
    # This is an uncertainty-aware intelligibility proxy, never an accent score.
    asr = 0.58 if asr_confidence is None else clamp(asr_confidence, 0.0, 1.0)
    activity = clamp(1.0 - silence_ratio / 0.88, 0.0, 1.0)
    volume = 0.65 if mean_db is None else clamp((mean_db + 52.0) / 31.0, 0.0, 1.0)
    return clamp(1.0 + 3.0 * (0.6 * asr + 0.25 * activity + 0.15 * volume), 1.0, 4.0)


def _evidence_index(criteria):
    active = {
        name: data["score"]
        for name, data in criteria.items()
        if data.get("score") is not None
    }
    total_weight = sum(CRITERION_WEIGHTS[name] for name in active)
    if not total_weight:
        return None
    value = sum(
        CRITERION_WEIGHTS[name] * (score / 4.0)
        for name, score in active.items()
    ) / total_weight
    return rounded(100.0 * value, 1)


def build_item_assessment(
    *, question, transcript, part_order, duration, silence_seconds,
    asr_confidence, mean_db,
):
    tokens = words(transcript)
    silence_ratio = clamp(silence_seconds / duration, 0.0, 1.0) if duration else 1.0
    quality_confidence = _quality_confidence(asr_confidence, silence_ratio, mean_db)
    review_flags = []
    if asr_confidence is None:
        review_flags.append("asr_confidence_unavailable")
    elif asr_confidence < 0.55:
        review_flags.append("low_asr_confidence")
    if silence_ratio > 0.68:
        review_flags.append("high_silence_ratio")
    if mean_db is not None and mean_db < -46:
        review_flags.append("low_recording_level")

    fluency, wpm, filler_ratio = _fluency_score(tokens, duration, silence_ratio)
    pronunciation = _pronunciation_score(asr_confidence, silence_ratio, mean_db)
    limitations = [
        "Automatic transcript and acoustic proxies require human confirmation near a decision boundary."
    ]

    if part_order in {3, 4}:
        accuracy, wer = _read_aloud_accuracy(question, transcript)
        task = clamp(1.0 + 3.0 * accuracy, 1.0, 4.0)
        pronunciation = clamp(0.68 * pronunciation + 0.32 * task, 1.0, 4.0)
        criteria = {
            "task_achievement": _criterion(task, quality_confidence, [
                f"Read-aloud text coverage estimate: {rounded(accuracy * 100, 1)}%.",
            ], limitations),
            "pronunciation_intelligibility": _criterion(pronunciation, quality_confidence, [
                "Words were compared with the supplied sentence and acoustic confidence.",
            ], ["Accent strength is not scored; this is an intelligibility proxy."]),
            "fluency": _criterion(fluency, quality_confidence, [
                f"Connected-speech activity estimate: {rounded((1-silence_ratio)*100, 1)}%.",
            ], limitations),
            "grammar": _not_scored("Not scored for read-aloud: the grammar was supplied."),
            "vocabulary": _not_scored("Not scored for read-aloud: the vocabulary was supplied."),
            "coherence": _not_scored("Not scored for read-aloud: the text organisation was supplied."),
        }
        diagnostics = {
            "read_aloud_accuracy": rounded(accuracy, 3),
            "word_error_rate": rounded(wer, 3),
        }
    else:
        task, task_evidence = _task_score(question, tokens, part_order)
        grammar = _grammar_score(tokens)
        vocabulary = _vocabulary_score(tokens)
        coherence = _coherence_score(tokens, part_order)
        language_confidence = clamp(quality_confidence - 0.04, 0.0, 1.0)
        criteria = {
            "task_achievement": _criterion(task, language_confidence, task_evidence, [
                "Semantic relevance is estimated from the transcript and should not be reduced to keyword matching."
            ]),
            "pronunciation_intelligibility": _criterion(pronunciation, quality_confidence, [
                "Intelligibility combines acoustic activity, recording level and ASR confidence."
            ], ["Accent strength is not scored; this is an intelligibility proxy."]),
            "fluency": _criterion(fluency, quality_confidence, [
                f"Speech contained {len(tokens)} recognised words with {rounded(silence_ratio*100,1)}% estimated silence.",
                f"Observed articulation proxy: {wpm} words/minute; no universal speed target was applied.",
            ], limitations),
            "grammar": _criterion(grammar, language_confidence, [
                "Common verb and clause-connection signals were evaluated in the uncertainty-aware transcript."
            ], ["Transcript-only grammar analysis cannot reliably identify every spoken-language error."]),
            "vocabulary": _criterion(vocabulary, language_confidence, [
                f"Length-adjusted range used {len(set(_content_words(tokens)))} unique content words."
            ], ["Rare words are not rewarded merely for being rare."]),
            "coherence": _criterion(coherence, language_confidence, [
                f"Detected {sum(1 for token in tokens if token in LINKERS)} basic connection signal(s)."
            ], ["Linker counts are supporting evidence, not the coherence score by themselves."]),
        }
        diagnostics = {}

    evidence_index = _evidence_index(criteria)
    scored_values = [data["score"] for data in criteria.values() if data["score"] is not None]
    lowest_name = min(
        (name for name in criteria if criteria[name]["score"] is not None),
        key=lambda name: criteria[name]["score"],
    )
    strengths = []
    if criteria["task_achievement"]["score"] >= 3.0:
        strengths.append("The response addressed the communicative task clearly enough for this item.")
    if criteria["pronunciation_intelligibility"]["score"] >= 3.0:
        strengths.append("The response was generally understandable despite normal accent variation.")
    if criteria["fluency"]["score"] >= 3.0:
        strengths.append("Planning and repair did not prevent the response from continuing.")
    improvement_map = {
        "task_achievement": "Answer the exact question first, then add the requested detail or action.",
        "pronunciation_intelligibility": "Record in a quieter place and focus on clear word endings and phrase stress.",
        "fluency": "Plan the first sentence, then speak in short connected chunks with fewer long stops.",
        "grammar": "Use clear subject-verb sentences and connect time, reason and sequence accurately.",
        "vocabulary": "Add precise familiar-topic words and paraphrase instead of repeating one expression.",
        "coherence": "Order the message clearly and connect each point with a simple logical link.",
    }
    improvements = [improvement_map[lowest_name]]

    status = "HUMAN_REVIEW" if review_flags else "SCORABLE"
    score_total = evidence_index
    criteria_scores = {name: value.get("score") for name, value in criteria.items()}
    return {
        "status": "graded",
        "scoring_spec": SPEC_ID,
        "scoring_version": 3,
        "assessment_status": status,
        "target_level": "B1",
        "part_order": int(part_order),
        "criteria": criteria,
        "b1_evidence_index": evidence_index,
        "score_total": score_total,
        "decision": "ITEM_EVIDENCE_ONLY",
        "decision_confidence": rounded(sum(data["confidence"] for data in criteria.values() if data["confidence"] is not None) / max(1, len(scored_values)), 3),
        "review_flags": review_flags,
        "transcript": transcript,
        "word_count": len(tokens),
        "words_per_minute": wpm,
        "audio_duration_seconds": rounded(duration, 2),
        "silence_ratio": rounded(silence_ratio, 3),
        "mean_volume_db": mean_db,
        "whisper_confidence": rounded(asr_confidence, 3) if asr_confidence is not None else None,
        "diagnostics": {**diagnostics, "filler_ratio": filler_ratio},
        "strengths": strengths[:2],
        "improvements": improvements,
        "feedback": {
            "demonstrated": strengths[:2],
            "next_priority": improvements[0],
            "practice_action": "Record the same task once more, keeping the meaning but improving the priority above.",
        },
        "cefr_estimate": None,
        "official_score": False,
        "paid_api_used": False,
        "disclaimer": DISCLAIMER,
        # Compatibility keys used by the existing report while it transitions.
        "task_response": rounded(criteria_scores["task_achievement"] / 4 * 25, 1),
        "language_control": rounded(criteria_scores["grammar"] / 4 * 20, 1) if criteria_scores["grammar"] is not None else None,
        "vocabulary": rounded(criteria_scores["vocabulary"] / 4 * 20, 1) if criteria_scores["vocabulary"] is not None else None,
        "fluency": rounded(criteria_scores["fluency"] / 4 * 20, 1),
        "intelligibility_proxy": rounded(criteria_scores["pronunciation_intelligibility"] / 4 * 15, 1),
    }


def build_insufficient_item_assessment(
    *, transcript, part_order, duration, silence_ratio, asr_confidence,
    mean_db, reasons,
):
    return {
        "status": "no_speech",
        "scoring_spec": SPEC_ID,
        "scoring_version": 3,
        "assessment_status": "INSUFFICIENT_EVIDENCE",
        "target_level": "B1",
        "part_order": int(part_order),
        "criteria": {
            name: _not_scored("Insufficient usable audio evidence.")
            for name in CRITERION_WEIGHTS
        },
        "b1_evidence_index": None,
        "score_total": None,
        "decision": "INSUFFICIENT_EVIDENCE",
        "decision_confidence": 0.0,
        "review_flags": list(reasons),
        "transcript": transcript,
        "word_count": len(words(transcript)),
        "audio_duration_seconds": rounded(duration, 2),
        "silence_ratio": rounded(silence_ratio, 3),
        "mean_volume_db": mean_db,
        "whisper_confidence": rounded(asr_confidence, 3) if asr_confidence is not None else None,
        "no_speech_reasons": list(reasons),
        "strengths": [],
        "improvements": ["Check the microphone and record a complete response in a quieter place."],
        "feedback": {
            "demonstrated": [],
            "next_priority": "Provide enough clear recorded English for the task to be evaluated.",
            "practice_action": "Check the microphone, replay a short test recording and try the item again.",
        },
        "cefr_estimate": None,
        "official_score": False,
        "paid_api_used": False,
        "disclaimer": DISCLAIMER,
    }
