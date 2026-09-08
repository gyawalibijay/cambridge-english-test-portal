from __future__ import annotations

import re
from collections.abc import Iterable

from django.core.files.storage import default_storage

from assessments.models import MockTest
from question_bank.models import Question

VERSION = "38.6"
PRACTICE_SLUG = "cambridge-speaking-practice-1"
TITLE_RE = re.compile(r"^Speaking S(\d+) P([12]) Q([1-4])$", re.I)
REQUIRED = {(part_no, q_no) for part_no in (1, 2) for q_no in range(1, 5)}


def _physical_audio_ok(question: Question) -> bool:
    field = getattr(question, "prompt_audio", None)
    name = getattr(field, "name", "") if field else ""
    if not name:
        return False
    try:
        return bool(default_storage.exists(name))
    except Exception:
        return False


def speaking_audio_status(program_id: int | None) -> dict[int, dict]:
    statuses = {
        set_no: {
            "set_no": set_no,
            "present": 0,
            "missing": [f"P{p}Q{q}" for p, q in sorted(REQUIRED)],
            "public": False,
        }
        for set_no in range(2, 32)
    }
    if not program_id:
        return statuses

    found: dict[int, set[tuple[int, int]]] = {set_no: set() for set_no in range(2, 32)}
    questions = Question.objects.filter(
        program_id=program_id,
        skill="speaking",
        is_active=True,
    ).only("id", "title", "prompt_audio")

    for question in questions:
        match = TITLE_RE.match(question.title or "")
        if not match:
            continue
        set_no, part_no, q_no = map(int, match.groups())
        if set_no not in found:
            continue
        if _physical_audio_ok(question):
            found[set_no].add((part_no, q_no))

    for set_no, slots in found.items():
        missing = sorted(REQUIRED - slots)
        statuses[set_no] = {
            "set_no": set_no,
            "present": len(slots),
            "missing": [f"P{p}Q{q}" for p, q in missing],
            "public": slots == REQUIRED,
        }
    return statuses


def public_speaking_set_numbers(program_id: int | None, candidates: Iterable[int] | None = None) -> list[int]:
    status = speaking_audio_status(program_id)
    allowed = {set_no for set_no, row in status.items() if row["public"]}
    if candidates is not None:
        allowed &= {int(value) for value in candidates}
    return sorted(allowed)


def sync_speaking_practice_publication(program_id: int | None = None) -> list[int]:
    test = (
        MockTest.objects.filter(slug=PRACTICE_SLUG)
        .select_related("program")
        .order_by("pk")
        .first()
    )
    if not test:
        return []

    effective_program_id = program_id or test.program_id
    public_sets = public_speaking_set_numbers(effective_program_id)
    should_publish = bool(public_sets)
    if bool(test.is_published) != should_publish:
        test.is_published = should_publish
        test.save(update_fields=["is_published"])
    return public_sets
