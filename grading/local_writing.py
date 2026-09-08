import re
import subprocess
from collections import Counter

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")

STOPWORDS = {
    "a","an","the","and","or","but","if","to","of","in","on","at","for",
    "from","with","about","is","am","are","was","were","be","been","being",
    "do","does","did","have","has","had","will","would","can","could","should",
    "i","you","he","she","it","we","they","my","your","our","their","me",
    "him","her","them","this","that","these","those","what","where","when",
    "why","how","who","which","write","email","reply","say","tell","ask",
}

LINKERS = {
    "and","but","because","also","first","second","then","however","so",
    "therefore","finally","although","while","after","before",
}

INFORMAL_FORMS = {"u","ur","gr8","lol","omg","btw","thx","pls"}
GREETING_PATTERNS = [r"^\s*hi\b", r"^\s*hello\b", r"^\s*dear\b"]
CLOSING_TERMS = {"regards","sincerely","thanks","thank","soon","best","yours"}


def clamp(value, low, high):
    return max(low, min(high, value))


def words(text):
    return WORD_RE.findall(text or "")


def lower_words(text):
    return [word.lower() for word in words(text)]


def sentences(text):
    values = []
    for raw in SENTENCE_RE.findall(text or ""):
        cleaned = raw.strip()
        if cleaned and WORD_RE.search(cleaned):
            values.append(cleaned)
    return values


def prompt_points(prompt):
    result = []
    for raw in (prompt or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith(("•", "-", "*")):
            result.append(stripped.lstrip("•-* ").strip())
    return result


def content_terms(text):
    return {
        word.lower()
        for word in words(text)
        if word.lower() not in STOPWORDS and len(word) >= 3
    }


def point_coverage(prompt, response):
    points = prompt_points(prompt)
    if not points:
        return 0.75, []

    answer_terms = content_terms(response)
    details = []
    covered = 0

    for point in points:
        terms = content_terms(point)
        hit = True if not terms else bool(terms & answer_terms)
        details.append({"point": point, "covered": hit})
        if hit:
            covered += 1

    return covered / len(points), details


def hunspell_errors(text):
    try:
        process = subprocess.run(
            ["hunspell", "-d", "en_US", "-l"],
            input=text or "",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        errors = [
            item.strip()
            for item in process.stdout.splitlines()
            if item.strip()
        ]
        return sorted(set(errors), key=str.lower)
    except Exception:
        return []


def is_capitalized(sentence):
    match = re.search(r"[A-Za-z]", sentence)
    return bool(match and sentence[match.start()].isupper())


def analyze(prompt, response_text, part_title=""):
    token_list = lower_words(response_text)
    word_count = len(token_list)
    sentence_list = sentences(response_text)
    sentence_count = len(sentence_list)

    coverage, point_details = point_coverage(prompt, response_text)

    minimum_factor = clamp(word_count / 50.0, 0.0, 1.0)
    task_score = 10.0 * minimum_factor + 20.0 * coverage

    paragraph_count = len(
        [
            paragraph
            for paragraph in re.split(r"\n\s*\n|\n", response_text.strip())
            if paragraph.strip()
        ]
    )

    linker_count = sum(1 for word in token_list if word in LINKERS)
    greeting = any(re.search(pattern, response_text, re.I) for pattern in GREETING_PATTERNS)
    closing = bool(set(token_list[-12:]) & CLOSING_TERMS)

    structure_bonus = (2.5 if greeting else 0) + (2.5 if closing else 0)

    organization_score = (
        7.0
        + min(5.0, linker_count * 1.5)
        + min(3.0, max(0, paragraph_count - 1) * 1.5)
        + structure_bonus
    )

    if sentence_count:
        capitalized_ratio = (
            sum(is_capitalized(sentence) for sentence in sentence_list)
            / sentence_count
        )
        punctuation_ratio = (
            sum(sentence.rstrip().endswith((".", "!", "?")) for sentence in sentence_list)
            / sentence_count
        )
        sentence_lengths = [len(lower_words(sentence)) for sentence in sentence_list]
        overloaded = sum(1 for length in sentence_lengths if length > 30) / sentence_count
    else:
        capitalized_ratio = 0
        punctuation_ratio = 0
        overloaded = 1

    language_score = (
        7.0
        + 7.0 * capitalized_ratio
        + 6.0 * punctuation_ratio
        + 5.0 * (1.0 - overloaded)
    )

    content = [word for word in token_list if word not in STOPWORDS]
    diversity = len(set(content)) / len(content) if content else 0
    longer_ratio = sum(len(word) >= 6 for word in content) / len(content) if content else 0
    repeated = Counter(content)
    repetition_ratio = (
        sum(count - 1 for count in repeated.values() if count > 1)
        / max(1, len(content))
    )

    vocabulary_score = (
        4.0
        + 7.0 * diversity
        + 4.0 * min(1.0, longer_ratio * 3.0)
        - min(3.0, repetition_ratio * 8.0)
    )

    spelling_errors = hunspell_errors(response_text)
    spelling_ratio = min(1.0, len(spelling_errors) / max(1, len(token_list)))
    informal_hits = sorted(set(token_list) & INFORMAL_FORMS)

    mechanics_score = (
        10.0
        - min(7.0, spelling_ratio * 45.0)
        - min(3.0, len(informal_hits) * 1.5)
    )

    task_score = round(clamp(task_score, 0, 30), 1)
    organization_score = round(clamp(organization_score, 0, 20), 1)
    language_score = round(clamp(language_score, 0, 25), 1)
    vocabulary_score = round(clamp(vocabulary_score, 0, 15), 1)
    mechanics_score = round(clamp(mechanics_score, 0, 10), 1)

    total = round(
        task_score
        + organization_score
        + language_score
        + vocabulary_score
        + mechanics_score,
        1,
    )

    if total < 48:
        cefr = "A1"
    elif total < 72:
        cefr = "A2"
    else:
        cefr = "B1"

    strengths = []
    improvements = []

    if coverage >= 0.99:
        strengths.append("You appear to address all of the main prompt points.")
    else:
        improvements.append("Check the prompt again and make sure every required point is answered.")

    if word_count >= 50:
        strengths.append("You reached the 50-word minimum.")
    else:
        improvements.append("Write at least 50 words before submitting.")

    if linker_count >= 2:
        strengths.append("You use linking words to connect ideas.")
    else:
        improvements.append("Use simple linking words such as and, but, because, also, first or then.")

    if greeting and closing:
        strengths.append("Your response includes an email-style opening and closing.")
    else:
        improvements.append("For an email/reply task, check the greeting and closing/sign-off.")

    if spelling_errors:
        improvements.append(
            "Re-check spelling, especially: "
            + ", ".join(spelling_errors[:6])
            + "."
        )
    else:
        strengths.append("No obvious dictionary spelling errors were detected.")

    return {
        "status": "graded",
        "engine": "local writing practice analyzer v1",
        "paid_api_used": False,
        "official_score": False,
        "score_total": total,
        "cefr_estimate": cefr,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "task_completion": task_score,
        "organization": organization_score,
        "language_control": language_score,
        "vocabulary": vocabulary_score,
        "mechanics": mechanics_score,
        "prompt_points": point_details,
        "spelling_errors": spelling_errors[:20],
        "informal_forms": informal_hits,
        "strengths": strengths[:4],
        "improvements": improvements[:5],
        "disclaimer": (
            "Local practice estimate only. The supplied workshop does not provide "
            "a proprietary numeric Cambridge Writing rubric. This internal practice "
            "score can be reviewed or overridden by an evaluator."
        ),
    }
