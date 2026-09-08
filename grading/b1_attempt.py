from statistics import mean

from .b1_speaking import CRITERION_WEIGHTS, DISCLAIMER, PART_WEIGHTS, SPEC_ID


def _average(values):
    clean = [float(value) for value in values if value is not None]
    return mean(clean) if clean else None


def _criterion_value(feedback, name):
    try:
        value = feedback["criteria"][name]["score"]
        return float(value) if value is not None else None
    except (KeyError, TypeError, ValueError):
        return None


def _part_value(rows, part_order, criterion):
    values = [
        _criterion_value(feedback, criterion)
        for order, feedback in rows
        if order == part_order
    ]
    return _average(values)


def _weighted_criterion(rows, criterion):
    weighted = []
    total_weight = 0.0
    for part_order, weight in PART_WEIGHTS[criterion].items():
        if weight <= 0:
            continue
        value = _part_value(rows, part_order, criterion)
        if value is None:
            continue
        weighted.append(value * weight)
        total_weight += weight
    if not total_weight:
        return None
    return sum(weighted) / total_weight


def _decision_label(decision):
    return {
        "B1_DEMONSTRATED": "B1 demonstrated — practice estimate",
        "B1_BORDERLINE_REVIEW": "B1 borderline — human review recommended",
        "B1_NOT_YET_DEMONSTRATED": "B1 not yet demonstrated",
        "INSUFFICIENT_EVIDENCE": "Insufficient evidence",
        "PROCESSING": "Analysis in progress",
    }.get(decision, decision.replace("_", " ").title())


def build_attempt_assessment(attempt):
    responses = list(
        attempt.attempt_questions
        .filter(question__skill="speaking")
        .select_related("part", "response")
        .order_by("order")
    )

    if not responses:
        return None

    rows = []
    pending = False
    for item in responses:
        try:
            response = item.response
        except Exception:
            pending = True
            continue
        feedback = response.ai_feedback if isinstance(response.ai_feedback, dict) else {}
        if feedback.get("scoring_spec") != SPEC_ID:
            pending = True
        rows.append((int(item.part.order), feedback))

    if pending:
        return {
            "scoring_spec": SPEC_ID,
            "assessment_status": "PROCESSING",
            "target_level": "B1",
            "decision": "PROCESSING",
            "decision_label": _decision_label("PROCESSING"),
            "disclaimer": DISCLAIMER,
        }

    usable = {
        part: [
            feedback for order, feedback in rows
            if order == part and feedback.get("assessment_status") in {"SCORABLE", "HUMAN_REVIEW"}
        ]
        for part in range(1, 6)
    }
    part5_usable = any(
        float(item.get("audio_duration_seconds") or 0) >= 20
        and int(item.get("word_count") or 0) >= 35
        for item in usable[5]
    )
    evidence_checks = {
        "part_1_usable": len(usable[1]),
        "part_2_usable": len(usable[2]),
        "part_3_usable": len(usable[3]),
        "part_4_usable": len(usable[4]),
        "part_5_usable": part5_usable,
    }
    evidence_passed = (
        len(usable[1]) >= 3
        and len(usable[2]) >= 3
        and len(usable[3]) >= 3
        and len(usable[4]) >= 3
        and len(usable[3]) + len(usable[4]) >= 6
        and part5_usable
    )

    criteria = {
        name: _weighted_criterion(rows, name)
        for name in CRITERION_WEIGHTS
    }
    if any(value is None for value in criteria.values()):
        evidence_passed = False

    confidences = []
    review_flags = []
    for _, feedback in rows:
        value = feedback.get("decision_confidence")
        if isinstance(value, (int, float)):
            confidences.append(float(value))
        if feedback.get("assessment_status") == "HUMAN_REVIEW":
            review_flags.extend(feedback.get("review_flags") or ["item_human_review"])

    confidence = _average(confidences) or 0.0
    rounded_criteria = {
        name: round(value, 2) if value is not None else None
        for name, value in criteria.items()
    }

    if not evidence_passed:
        decision = "INSUFFICIENT_EVIDENCE"
        index = None
    else:
        index = 100 * sum(
            CRITERION_WEIGHTS[name] * (criteria[name] / 4.0)
            for name in CRITERION_WEIGHTS
        )
        weighted_mean = index / 25.0
        productive = []
        for part_order in (1, 2, 5):
            for criterion in CRITERION_WEIGHTS:
                value = _part_value(rows, part_order, criterion)
                if value is not None:
                    productive.append(value)
        generated_composite = _average(productive) or 0.0
        part5_task = _part_value(rows, 5, "task_achievement") or 0.0
        core_mean = mean(
            criteria[name] for name in ("fluency", "grammar", "vocabulary", "coherence")
        )
        low_core = sum(
            1 for name in CRITERION_WEIGHTS
            if criteria[name] < 2.5
        )
        # Keep the specification's 3.05 demonstrated threshold reachable.
        # Scores just below it are decision-sensitive; a high-confidence result
        # at or above it may demonstrate B1 when every safeguard passes.
        near_boundary = 2.75 <= weighted_mean < 3.05
        if near_boundary:
            review_flags.append("decision_near_b1_boundary")
        if confidence < 0.85:
            review_flags.append("model_confidence_below_0_85")

        demonstrated = (
            index >= 76.25
            and criteria["task_achievement"] >= 3.0
            and criteria["pronunciation_intelligibility"] >= 3.0
            and core_mean >= 2.8
            and part5_task >= 3.0
            and generated_composite >= 2.9
            and confidence >= 0.85
            and not review_flags
        )
        if demonstrated:
            decision = "B1_DEMONSTRATED"
        elif review_flags or near_boundary:
            decision = "B1_BORDERLINE_REVIEW"
        elif weighted_mean < 2.75 or low_core >= 2:
            decision = "B1_NOT_YET_DEMONSTRATED"
        else:
            decision = "B1_BORDERLINE_REVIEW"

    strengths = []
    improvement = "Complete enough clear speech in every part for a fair B1 estimate."
    if index is not None:
        ordered = sorted(criteria.items(), key=lambda item: item[1], reverse=True)
        strengths = [
            f"{ordered[0][0].replace('_', ' ').title()} provided the strongest B1 evidence."
        ]
        improvement = (
            f"Prioritise {ordered[-1][0].replace('_', ' ')} in the next practice session."
        )

    return {
        "scoring_spec": SPEC_ID,
        "assessment_status": (
            "INSUFFICIENT_EVIDENCE" if decision == "INSUFFICIENT_EVIDENCE"
            else "HUMAN_REVIEW" if decision == "B1_BORDERLINE_REVIEW"
            else "SCORABLE"
        ),
        "target_level": "B1",
        "criteria": rounded_criteria,
        "b1_evidence_index": round(index, 1) if index is not None else None,
        "decision": decision,
        "decision_label": _decision_label(decision),
        "decision_confidence": round(confidence, 3),
        "review_flags": sorted(set(review_flags)),
        "evidence_checks": evidence_checks,
        "feedback": {
            "demonstrated": strengths,
            "next_priority": improvement,
            "practice_action": (
                "Repeat one task from the weakest criterion and compare the new "
                "recording with the earlier attempt."
            ),
        },
        "disclaimer": DISCLAIMER,
    }


def update_attempt_assessment(attempt):
    result = build_attempt_assessment(attempt)
    if result is None:
        return None
    metadata = dict(attempt.metadata or {})
    metadata["b1_assessment"] = result
    type(attempt).objects.filter(pk=attempt.pk).update(metadata=metadata)
    return result
