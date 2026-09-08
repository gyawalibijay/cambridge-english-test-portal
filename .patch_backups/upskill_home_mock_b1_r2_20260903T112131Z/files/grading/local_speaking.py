import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from statistics import mean

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

STOPWORDS = {
    "a","an","the","and","or","but","to","of","in","on","at","for","from",
    "with","about","is","am","are","was","were","be","been","being","do",
    "does","did","have","has","had","will","would","can","could","should",
    "i","you","he","she","it","we","they","my","your","our","their","me",
    "him","her","them","what","where","when","why","how","who","which",
    "this","that","these","those"
}

FILLERS = {"um","uh","erm","hmm","umm","uhh"}

COMMON_VERBS = {
    "am","is","are","was","were","be","been","being","have","has","had",
    "do","does","did","work","works","worked","study","studies","studied",
    "live","lives","lived","like","likes","liked","love","loves","loved",
    "go","goes","went","eat","eats","ate","want","wants","wanted","enjoy",
    "enjoys","enjoyed","play","plays","played","watch","watches","watched",
    "read","reads","travel","travels","travelled","exercise","exercises",
    "wake","wakes","prefer","prefers","use","uses","used","learn","learns",
    "learned","meet","meets","met","think","thinks","thought","feel","feels",
    "felt","make","makes","made","plan","plans","planned","hope","hopes"
}

FREQUENCY_WORDS = {
    "always","usually","often","sometimes","occasionally","rarely","never",
    "daily","weekly","monthly","every","once","twice"
}

TIME_WORDS = {
    "morning","afternoon","evening","night","today","yesterday","tomorrow",
    "week","weekend","month","year","monday","tuesday","wednesday",
    "thursday","friday","saturday","sunday"
}

YES_NO_WORDS = {"yes", "no", "yeah", "yep", "nope"}


def clamp(value, low, high):
    return max(low, min(high, value))


def tokenize(text):
    return [w.lower() for w in WORD_RE.findall(text or "")]


def content_words(items):
    return [w for w in items if w not in STOPWORDS and len(w) > 1]


def run(command, timeout=220):
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def convert_to_wav(source_path):
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.close()
    wav_path = Path(handle.name)

    subprocess.run(
        [
            "/usr/bin/ffmpeg", "-y",
            "-i", str(source_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(wav_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
    )
    return wav_path


def audio_duration(wav_path):
    result = run([
        "/usr/bin/ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(wav_path),
    ], timeout=20)

    try:
        return max(0.0, float(result.stdout.strip()))
    except ValueError:
        return 0.0


def silence_duration(wav_path, total_duration):
    process = subprocess.run(
        [
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", str(wav_path),
            "-af", "silencedetect=noise=-35dB:d=0.22",
            "-f", "null", "-"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=45,
    )

    values = [
        float(v)
        for v in re.findall(
            r"silence_duration:\s*([0-9]+(?:\.[0-9]+)?)",
            process.stderr or ""
        )
    ]

    return clamp(sum(values), 0.0, total_duration)


def mean_volume_db(wav_path):
    process = subprocess.run(
        [
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", str(wav_path),
            "-af", "volumedetect",
            "-f", "null", "-"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=45,
    )

    match = re.search(
        r"mean_volume:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*dB",
        process.stderr or ""
    )

    return float(match.group(1)) if match else None


def transcribe(wav_path):
    cli = os.environ["LOCAL_WHISPER_CLI"]
    model = os.environ["LOCAL_WHISPER_MODEL"]
    threads = os.environ.get("LOCAL_WHISPER_THREADS", "1")

    with tempfile.TemporaryDirectory() as tmp:
        output_base = Path(tmp) / "result"

        run([
            cli,
            "-m", model,
            "-f", str(wav_path),
            "-l", "en",
            "-t", str(threads),
            "-ojf",
            "-of", str(output_base),
            "-np",
        ])

        json_path = Path(str(output_base) + ".json")
        data = json.loads(json_path.read_text(encoding="utf-8"))

    segments = data.get("transcription") or []

    transcript = " ".join(
        str(segment.get("text", "")).strip()
        for segment in segments
        if str(segment.get("text", "")).strip()
    ).strip()

    probabilities = []

    for segment in segments:
        for token in segment.get("tokens") or []:
            probability = token.get("p")
            token_text = str(token.get("text", "")).strip()

            if token_text and isinstance(probability, (int, float)):
                probabilities.append(float(probability))

    confidence = mean(probabilities) if probabilities else None

    return {
        "transcript": transcript,
        "confidence": confidence,
        "segments": len(segments),
    }


def detect_no_speech(
    transcript,
    answer_words,
    duration,
    silence_ratio,
    confidence,
    mean_db,
):
    reasons = []

    if not transcript.strip():
        reasons.append("No usable English speech was transcribed.")

    if len(answer_words) == 0:
        reasons.append("No spoken words were detected.")

    if duration > 1 and silence_ratio >= 0.92:
        reasons.append("Almost the entire recording was silence.")

    if mean_db is not None and mean_db <= -52:
        reasons.append("The recording level was too low.")

    if (
        confidence is not None
        and confidence < 0.10
        and len(answer_words) <= 2
    ):
        reasons.append("Speech-recognition confidence was too low.")

    # A single hallucinated word over a mostly silent clip should not be graded.
    if (
        len(answer_words) <= 1
        and duration >= 4
        and silence_ratio >= 0.72
    ):
        reasons.append("Not enough clear speech was present to grade.")

    return reasons


def intent_score(question, answer_words):
    q = question.lower().strip()
    aset = set(answer_words)
    joined = " ".join(answer_words)

    if not answer_words:
        return 0.0

    if "why" in q:
        return 1.0 if {"because", "since"} & aset else 0.55

    if "how often" in q:
        return 1.0 if FREQUENCY_WORDS & aset else 0.55

    if "what time" in q or q.startswith("when"):
        has_number = bool(re.search(r"\b\d{1,2}(?::\d{2})?\b", joined))
        return 1.0 if has_number or TIME_WORDS & aset else 0.55

    if q.startswith("where") or "hometown" in q or "place" in q:
        return 1.0 if len(answer_words) >= 4 else 0.6

    if q.startswith(("do ", "are ", "is ", "have ")):
        yes_no = bool(YES_NO_WORDS & aset)
        return 1.0 if yes_no or len(answer_words) >= 4 else 0.6

    if "describe" in q or "tell me about" in q:
        return clamp(len(answer_words) / 16.0, 0.35, 1.0)

    if "future" in q or "plan" in q:
        future_signal = {"will","going","want","plan","hope"} & aset
        return 1.0 if future_signal else 0.6

    return clamp(len(answer_words) / 8.0, 0.45, 1.0)


def relevance_score(question, answer_words):
    q_content = set(content_words(tokenize(question)))
    a_content = set(content_words(answer_words))

    if not q_content or not a_content:
        return 0.0

    overlap = len(q_content & a_content) / len(q_content)

    # Direct lexical overlap is only one signal; short personal answers
    # should not be punished merely because names/places differ.
    return clamp(overlap, 0.0, 1.0)


def score_task_response(question, answer_words, part_order):
    count = len(answer_words)

    if not count:
        return 0.0

    target_words = 6 if part_order == 1 else 13
    length_component = clamp(count / target_words, 0.0, 1.0)

    intent = intent_score(question, answer_words)
    relevance = relevance_score(question, answer_words)

    score = (
        7.0
        + 10.0 * length_component
        + 6.0 * intent
        + 2.0 * relevance
    )

    return round(clamp(score, 0, 25), 1)


def score_language_control(answer_words):
    if not answer_words:
        return 0.0

    aset = set(answer_words)
    count = len(answer_words)

    verb_signal = 1.0 if COMMON_VERBS & aset else 0.45
    length_signal = clamp(count / 9.0, 0.25, 1.0)

    repeats = sum(
        1
        for left, right in zip(answer_words, answer_words[1:])
        if left == right
    )

    repeated_penalty = min(4.0, repeats * 1.5)

    # If a candidate gives a real short answer, do not require long complex grammar.
    score = (
        5.0
        + 8.0 * verb_signal
        + 7.0 * length_signal
        - repeated_penalty
    )

    return round(clamp(score, 0, 20), 1)


def score_vocabulary(answer_words):
    content = content_words(answer_words)

    if not content:
        return 0.0

    diversity = len(set(content)) / len(content)
    longer_ratio = sum(1 for word in content if len(word) >= 6) / len(content)

    score = (
        5.5
        + 9.5 * diversity
        + 5.0 * min(1.0, longer_ratio * 3.0)
    )

    return round(clamp(score, 0, 20), 1)


def score_fluency(answer_words, duration, silence_seconds):
    if not answer_words or duration <= 0:
        return 0.0, 0.0, 1.0

    silence_ratio = clamp(silence_seconds / duration, 0.0, 1.0)
    active_seconds = max(0.5, duration - silence_seconds)
    wpm = len(answer_words) / active_seconds * 60.0

    if 75 <= wpm <= 165:
        rate_points = 10.0
    elif 55 <= wpm < 75 or 165 < wpm <= 190:
        rate_points = 8.0
    elif 38 <= wpm < 55 or 190 < wpm <= 220:
        rate_points = 5.5
    else:
        rate_points = 3.0

    filler_count = sum(1 for word in answer_words if word in FILLERS)
    filler_ratio = filler_count / max(1, len(answer_words))

    silence_points = clamp(
        8.0 * (1.0 - silence_ratio / 0.65),
        0.0,
        8.0,
    )

    filler_penalty = clamp(filler_ratio * 28.0, 0.0, 4.0)

    score = 2.0 + rate_points + silence_points - filler_penalty

    return (
        round(clamp(score, 0, 20), 1),
        round(wpm, 1),
        round(silence_ratio, 3),
    )


def score_intelligibility(answer_words, confidence, silence_ratio, mean_db):
    if not answer_words:
        return 0.0

    if confidence is None:
        confidence_component = 0.5
    else:
        confidence_component = clamp(
            (confidence - 0.20) / 0.70,
            0.0,
            1.0,
        )

    activity_component = clamp(1.0 - silence_ratio, 0.0, 1.0)

    if mean_db is None:
        volume_component = 0.65
    else:
        # Around -28 to -12 dB is treated as a healthy speech recording level.
        volume_component = clamp((mean_db + 48.0) / 25.0, 0.0, 1.0)

    score = (
        2.5
        + 8.0 * confidence_component
        + 2.5 * activity_component
        + 2.0 * volume_component
    )

    return round(clamp(score, 0, 15), 1)


def cefr_estimate(total):
    # Practice-only internal thresholds, not official Cambridge cut scores.
    if total < 48:
        return "A1"
    if total < 72:
        return "A2"
    return "B1"


def make_feedback(
    task,
    language,
    vocabulary,
    fluency,
    intelligibility,
    word_count,
    wpm,
    silence_ratio,
):
    strengths = []
    improvements = []

    if task >= 19:
        strengths.append("You answered the task directly and gave enough relevant information.")
    else:
        improvements.append("Answer the exact question first, then add one useful supporting detail.")

    if language >= 15:
        strengths.append("Your basic sentence structure and language control were reasonably stable.")
    else:
        improvements.append("Use complete simple sentences with a clear subject and verb.")

    if vocabulary >= 15:
        strengths.append("You used a useful range of everyday vocabulary.")
    else:
        improvements.append("Try to use a wider range of everyday words instead of repeating the same terms.")

    if fluency >= 15:
        strengths.append("Your delivery had a reasonably steady speaking flow.")
    elif silence_ratio > 0.40:
        improvements.append("Reduce long pauses by planning your first sentence during preparation time.")
    elif wpm > 190:
        improvements.append("Slow down slightly so your words remain easy to understand.")
    else:
        improvements.append("Practise speaking in slightly longer chunks with fewer hesitations.")

    if intelligibility >= 11:
        strengths.append("Your recording was generally understandable to the local speech-recognition engine.")
    else:
        improvements.append("Speak clearly at a steady volume and keep the microphone close enough for a clean recording.")

    if word_count <= 2:
        improvements.append("Give more than a one-word answer when the task allows it.")

    return strengths[:4], improvements[:4]


def evaluate(source_path, question, part_order):
    wav_path = convert_to_wav(source_path)

    try:
        duration = audio_duration(wav_path)
        silence_seconds = silence_duration(wav_path, duration)
        mean_db = mean_volume_db(wav_path)

        whisper = transcribe(wav_path)

        transcript = whisper["transcript"]
        confidence = whisper["confidence"]
        answer_words = tokenize(transcript)

        silence_ratio = (
            clamp(silence_seconds / duration, 0.0, 1.0)
            if duration > 0 else 1.0
        )

        no_speech_reasons = detect_no_speech(
            transcript=transcript,
            answer_words=answer_words,
            duration=duration,
            silence_ratio=silence_ratio,
            confidence=confidence,
            mean_db=mean_db,
        )

        if no_speech_reasons:
            return {
                "status": "no_speech",
                "engine": "whisper.cpp base.en Q5_1 + local practice scoring v2",
                "paid_api_used": False,
                "official_score": False,
                "transcript": transcript,
                "score_total": None,
                "cefr_estimate": None,
                "word_count": len(answer_words),
                "audio_duration_seconds": round(duration, 2),
                "silence_ratio": round(silence_ratio, 3),
                "mean_volume_db": mean_db,
                "whisper_confidence": (
                    round(confidence, 3)
                    if confidence is not None
                    else None
                ),
                "no_speech_reasons": no_speech_reasons,
                "feedback": (
                    "We could not detect enough clear spoken English to grade this response. "
                    "Please retry the question in a quiet place and speak clearly."
                ),
                "disclaimer": (
                    "No score was assigned because there was not enough clear speech."
                ),
            }

        task = score_task_response(question, answer_words, part_order)
        language = score_language_control(answer_words)
        vocabulary = score_vocabulary(answer_words)

        fluency, wpm, silence_ratio = score_fluency(
            answer_words,
            duration,
            silence_seconds,
        )

        intelligibility = score_intelligibility(
            answer_words,
            confidence,
            silence_ratio,
            mean_db,
        )

        total = round(
            task + language + vocabulary + fluency + intelligibility,
            1,
        )

        strengths, improvements = make_feedback(
            task,
            language,
            vocabulary,
            fluency,
            intelligibility,
            len(answer_words),
            wpm,
            silence_ratio,
        )

        return {
            "status": "graded",
            "engine": "whisper.cpp base.en Q5_1 + local practice scoring v2",
            "paid_api_used": False,
            "official_score": False,
            "transcript": transcript,
            "score_total": total,
            "task_response": task,
            "language_control": language,
            "vocabulary": vocabulary,
            "fluency": fluency,
            "intelligibility_proxy": intelligibility,
            "cefr_estimate": cefr_estimate(total),
            "word_count": len(answer_words),
            "words_per_minute": wpm,
            "audio_duration_seconds": round(duration, 2),
            "silence_ratio": silence_ratio,
            "mean_volume_db": mean_db,
            "whisper_confidence": (
                round(confidence, 3)
                if confidence is not None
                else None
            ),
            "strengths": strengths,
            "improvements": improvements,
            "disclaimer": (
                "Local AI-assisted practice estimate only. "
                "It is not an official Cambridge score. "
                "The intelligibility value is a local speech-recognition proxy, "
                "not a phoneme-level pronunciation examination."
            ),
        }

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
