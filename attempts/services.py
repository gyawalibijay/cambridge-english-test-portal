import random
import re
from decimal import Decimal

from django.db import transaction

from question_bank.models import PartQuestion

from .models import AttemptQuestion, StudentResponse, TestAttempt
from core.speaking_audio_gate_v38_6 import public_speaking_set_numbers


@transaction.atomic
def create_attempt_for_test(*, user, mock_test):
    attempt = TestAttempt.objects.create(
        user=user,
        mock_test=mock_test,
        status=TestAttempt.Status.IN_PROGRESS,
    )

    global_order = 1
    max_score = Decimal("0.00")

    sections = mock_test.sections.order_by("order")

    for section in sections:
        parts = section.parts.filter(is_active=True).order_by("order")

        for part in parts:
            assignments = list(
                PartQuestion.objects
                .filter(part=part, question__is_active=True)
                .select_related("question")
                .order_by("order")
            )

            if not assignments:
                continue

            # B1_LISTENING_SET_ATTEMPT_V34_4
            has_builder_listening = (
                str(getattr(section, "skill", "")).lower() == "listening"
                and any(
                    (assignment.question.title or "").startswith("Listening S")
                    for assignment in assignments
                )
            )
            # /B1_LISTENING_SET_ATTEMPT_V34_4
            # B1_FULL_MOCK_EXACT_ORDER_V35_PART2
            # A Full Mock is an authored exam. Deliver every assigned question in
            # exact PartQuestion.order. Practice keeps its existing deterministic
            # random selection behavior.
            is_full_mock = str(getattr(mock_test, "delivery_mode", "")).lower() == "full_mock"
            if is_full_mock:
                selected = assignments
            else:
                # B1_SPEAKING_AUDIO_GATED_SET_V38_6
                # New attempts may use only Sets whose Part 1 + Part 2 have all 8 real audio files.
                has_builder_speaking = (
                    str(getattr(section, "skill", "")).lower() == "speaking"
                    and any(
                        re.match(r"^Speaking S\d+ P\d+ Q\d+$", (a.question.title or ""), re.I)
                        for a in assignments
                    )
                )
                if has_builder_speaking:
                    metadata = dict(attempt.metadata or {})
                    speaking_set = metadata.get("speaking_set_no")
                    authored = sorted({
                        int(m.group(1))
                        for a in assignments
                        for m in [re.match(r"^Speaking S(\d+) P\d+ Q\d+$", a.question.title or "", re.I)]
                        if m
                    })
                    program_id = next(
                        (getattr(a.question, "program_id", None) for a in assignments if getattr(a, "question", None)),
                        None,
                    )

                    # Preserve an already-started coherent Set. Only NEW Set selection uses the public gate.
                    if speaking_set in authored:
                        selected = []
                        for a in assignments:
                            m = re.match(r"^Speaking S(\d+) P\d+ Q\d+$", a.question.title or "", re.I)
                            if m and int(m.group(1)) == int(speaking_set):
                                selected.append(a)
                    else:
                        available = public_speaking_set_numbers(program_id, candidates=authored)
                        if not available:
                            selected = []
                        else:
                            previous = TestAttempt.objects.filter(user=user, mock_test=mock_test).exclude(pk=attempt.pk).count()
                            speaking_set = available[previous % len(available)]
                            metadata["speaking_set_no"] = speaking_set
                            metadata["speaking_bank_version"] = "38.6"
                            metadata["speaking_audio_policy"] = "physical_audio_only"
                            attempt.metadata = metadata
                            attempt.save(update_fields=["metadata"])
                            selected = []
                            for a in assignments:
                                m = re.match(r"^Speaking S(\d+) P\d+ Q\d+$", a.question.title or "", re.I)
                                if m and int(m.group(1)) == int(speaking_set):
                                    selected.append(a)
                else:
                    requested = (
                        len(assignments)
                        if has_builder_listening
                        else (part.question_count or len(assignments))
                    )
                    requested = min(requested, len(assignments))
                    rng = random.Random(f"attempt:{attempt.pk}:part:{part.pk}")
                    selected = rng.sample(assignments, requested)
                    rng.shuffle(selected)
                # /B1_SPEAKING_AUDIO_GATED_SET_V38_6
                # B1_WRITING_COHERENT_SET_V39_0
                # The imported Writing bank is authored as 50 complete two-part Sets.
                # After normal selection logic runs, override Writing Practice only so P1/P2
                # keep the same Set number for the current attempt.
                if (
                    str(getattr(section, "skill", "")).lower() == "writing"
                    and any(
                        re.match(r"^Writing S\d+ P[12] Q1$", (a.question.title or ""), re.I)
                        for a in assignments
                    )
                ):
                    metadata = dict(attempt.metadata or {})
                    writing_set = metadata.get("writing_set_no")
                    available = sorted({
                        int(m.group(1))
                        for a in assignments
                        for m in [re.match(r"^Writing S(\d+) P[12] Q1$", a.question.title or "", re.I)]
                        if m
                    })

                    if available:
                        if writing_set not in available:
                            previous = (
                                TestAttempt.objects.filter(user=user, mock_test=mock_test)
                                .exclude(pk=attempt.pk)
                                .count()
                            )
                            writing_set = available[previous % len(available)]
                            metadata["writing_set_no"] = writing_set
                            metadata["writing_bank_version"] = "39.0"
                            attempt.metadata = metadata
                            attempt.save(update_fields=["metadata"])

                        selected = [
                            a
                            for a in assignments
                            if (
                                (lambda m: m and int(m.group(1)) == int(writing_set))(
                                    re.match(r"^Writing S(\d+) P[12] Q1$", a.question.title or "", re.I)
                                )
                            )
                        ]
                    else:
                        selected = []
                # /B1_WRITING_COHERENT_SET_V39_0
            # /B1_FULL_MOCK_EXACT_ORDER_V35_PART2

            for assignment in selected:
                points = (
                    assignment.points_override
                    if assignment.points_override is not None
                    else assignment.question.default_points
                )

                AttemptQuestion.objects.create(
                    attempt=attempt,
                    part=part,
                    question=assignment.question,
                    order=global_order,
                    points=points,
                )

                max_score += points
                global_order += 1

    attempt.max_score = max_score
    attempt.save(update_fields=["max_score"])

    return attempt


def next_unanswered_question(attempt):
    for item in attempt.attempt_questions.select_related(
        "part",
        "question",
    ).order_by("order"):
        try:
            item.response
        except StudentResponse.DoesNotExist:
            return item
    return None
