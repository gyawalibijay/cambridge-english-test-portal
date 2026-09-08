import json


def normalize(value):
    return " ".join(str(value or "").strip().split())


def mark_objective_question(question, payload):
    qtype = question.question_type

    if qtype == question.Type.SINGLE_CHOICE:
        selected = str(payload.get("option", "")).strip()
        correct_ids = {
            str(option.pk)
            for option in question.options.filter(is_correct=True)
        }
        return selected in correct_ids, {"option": selected}

    if qtype == question.Type.MULTIPLE_CHOICE:
        selected = {
            str(value)
            for value in payload.getlist("options")
            if str(value).strip()
        }
        correct_ids = {
            str(option.pk)
            for option in question.options.filter(is_correct=True)
        }
        return selected == correct_ids, {"options": sorted(selected)}

    if qtype in {question.Type.SHORT_ANSWER, question.Type.GAP_FILL}:
        submitted = normalize(payload.get("text", ""))
        correct = False
        for answer in question.acceptable_answers.all():
            target = normalize(answer.answer_text)
            if answer.case_sensitive:
                if submitted == target:
                    correct = True
                    break
            elif submitted.casefold() == target.casefold():
                correct = True
                break
        return correct, {"text": submitted}

    if qtype == question.Type.ORDERING:
        raw = payload.get("ordering", "[]")
        try:
            submitted_ids = [int(value) for value in json.loads(raw)]
        except (TypeError, ValueError, json.JSONDecodeError):
            submitted_ids = []
        expected_ids = list(
            question.ordering_items.order_by("correct_position").values_list("id", flat=True)
        )
        return submitted_ids == expected_ids, {"ordering": submitted_ids}

    raise ValueError(f"Unsupported automatic question type: {qtype}")
