"""Easy Cambridge Reading Set manager for the supplied 50-set bank."""
from __future__ import annotations

import re
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from assessments.models import MockTest, TestPart
from assessments.reading_bank_v36_data import TOTAL_SETS, load_sets
from question_bank.models import AcceptableAnswer, Question, QuestionOption, Stimulus

SLUG = "cambridge-reading-reference-practice"
TITLE_RE = re.compile(r"^Reading S(\d+) P(\d+) Q(\d+)$", re.I)
PART_GUIDE = {
    1: {"title": "Short texts", "help": "Four short notices/messages. Student chooses the meaning.", "type": "choice"},
    2: {"title": "Choose one word", "help": "Four sentence gaps. Student chooses one word from A/B/C.", "type": "choice"},
    3: {"title": "Write one word", "help": "Four sentence gaps. Student types the missing word.", "type": "short"},
    4: {"title": "Complete a form", "help": "One practical message with four form-field answers.", "type": "short_shared"},
    5: {"title": "Longer text", "help": "One longer text with four comprehension questions.", "type": "choice_shared"},
}


def _program():
    test = MockTest.objects.filter(slug=SLUG).select_related("program").first()
    if not test:
        raise ValidationError("The 50-set Reading bank is not installed yet. Run the Reading V36 installer first.")
    return test.program


def _test():
    test = MockTest.objects.filter(slug=SLUG).first()
    if not test:
        raise Http404("Reading practice bank not found.")
    return test


def _part(part_no):
    test = _test()
    try:
        return TestPart.objects.get(section__mock_test=test, section__skill="reading", order=part_no)
    except TestPart.DoesNotExist as exc:
        raise Http404("Reading Part not found.") from exc


def _question(set_no, part_no, local_q):
    title = f"Reading S{set_no} P{part_no} Q{local_q}"
    try:
        return Question.objects.select_related("stimulus").prefetch_related("options", "acceptable_answers").get(
            program=_program(), skill="reading", title=title
        )
    except Question.DoesNotExist as exc:
        raise Http404(f"{title} was not found.") from exc


def _rows_for(set_no, part_no):
    return [_question(set_no, part_no, q) for q in range(1, 5)]


def _is_ready(q, part_no):
    if part_no in (1, 2, 5):
        return q.options.count() == 3 and q.options.filter(is_correct=True).count() == 1 and bool((q.prompt_text or "").strip())
    return q.acceptable_answers.exclude(answer_text="").exists() and bool((q.prompt_text or "").strip())


def _source_spec(set_no, part_no):
    data = load_sets()
    return data[set_no - 1]["parts"][str(part_no)]


def _context(request, title):
    context = admin.site.each_context(request)
    context.update({"title": title, "opts": None, "has_permission": True})
    return context


def reading_sets(request):
    test = _test()
    bank = list(
        Question.objects.filter(
            program=test.program, skill="reading", title__startswith="Reading S"
        ).select_related("stimulus").prefetch_related("options", "acceptable_answers")
    )
    question_map = {q.title: q for q in bank}
    rows = []
    for set_no in range(1, TOTAL_SETS + 1):
        parts = []
        total_ready = 0
        for part_no in range(1, 6):
            qs = [
                question_map.get(f"Reading S{set_no} P{part_no} Q{local_q}")
                for local_q in range(1, 5)
            ]
            ready_count = sum(1 for q in qs if q is not None and _is_ready(q, part_no))
            total_ready += ready_count
            parts.append({
                "number": part_no,
                "guide": PART_GUIDE[part_no],
                "question_count": sum(1 for q in qs if q is not None),
                "ready_count": ready_count,
                "ready": ready_count == 4,
                "url": reverse("admin:b1_reading_set_part", args=[set_no, part_no]),
            })
        rows.append({
            "set_no": set_no,
            "parts": parts,
            "ready": total_ready == 20,
            "ready_count": total_ready,
        })
    context = _context(request, "Reading Sets")
    context.update({"rows": rows, "test": test, "total_sets": TOTAL_SETS})
    return TemplateResponse(request, "admin/reading_sets_v36.html", context)


def _post_text(request, name):
    return (request.POST.get(name) or "").strip()


def _save_choice(q, request, index):
    prompt = _post_text(request, f"q{index}_prompt")
    options = [_post_text(request, f"q{index}_option_{n}") for n in range(1, 4)]
    correct = _post_text(request, f"q{index}_correct")
    if not prompt or any(not x for x in options) or correct not in {"1", "2", "3"}:
        raise ValidationError(f"Question {index}: enter the question, all three choices, and the correct answer.")
    q.prompt_text = prompt
    q.question_type = "single_choice"
    q.automatic_marking = True
    q.ai_grading_required = False
    q.manual_review_allowed = False
    q.is_active = True
    q.save(update_fields=["prompt_text", "question_type", "automatic_marking", "ai_grading_required", "manual_review_allowed", "is_active", "updated_at"])
    q.options.all().delete()
    for n, text in enumerate(options, start=1):
        QuestionOption.objects.create(question=q, text=text, order=n, is_correct=str(n) == correct)
    q.acceptable_answers.all().delete()


def _save_short(q, request, index):
    prompt = _post_text(request, f"q{index}_prompt")
    answers = _post_text(request, f"q{index}_answer")
    values = [x.strip() for x in answers.split("|") if x.strip()]
    if not prompt or not values:
        raise ValidationError(f"Question {index}: enter the question/field and at least one correct answer.")
    q.prompt_text = prompt
    q.question_type = "gap_fill"
    q.automatic_marking = True
    q.ai_grading_required = False
    q.manual_review_allowed = False
    q.is_active = True
    q.save(update_fields=["prompt_text", "question_type", "automatic_marking", "ai_grading_required", "manual_review_allowed", "is_active", "updated_at"])
    q.options.all().delete()
    q.acceptable_answers.all().delete()
    for value in values:
        AcceptableAnswer.objects.create(question=q, answer_text=value, case_sensitive=False)


def _restore_part(set_no, part_no):
    spec = _source_spec(set_no, part_no)
    rows = _rows_for(set_no, part_no)
    if part_no in (4, 5):
        shared = rows[0].stimulus
        if shared is None:
            shared = Stimulus.objects.create(program=_program(), title=f"Reading S{set_no} P{part_no} Source", stimulus_type="text")
        shared.content = spec.get("stimulus", "")
        shared.is_active = True
        shared.save(update_fields=["content", "is_active", "updated_at"])
        for q in rows:
            if q.stimulus_id != shared.pk:
                q.stimulus = shared
                q.save(update_fields=["stimulus", "updated_at"])
    for index, (q, source_q) in enumerate(zip(rows, spec["questions"]), start=1):
        if part_no == 1:
            stimulus = q.stimulus
            if stimulus is None:
                stimulus = Stimulus.objects.create(program=_program(), title=f"Reading S{set_no} P1 Source {index}", stimulus_type="text")
                q.stimulus = stimulus
                q.save(update_fields=["stimulus", "updated_at"])
            stimulus.content = source_q.get("stimulus", "")
            stimulus.is_active = True
            stimulus.save(update_fields=["content", "is_active", "updated_at"])
        q.prompt_text = source_q["prompt"]
        q.is_active = True
        q.save(update_fields=["prompt_text", "is_active", "updated_at"])
        if part_no in (1, 2, 5):
            q.question_type = "single_choice"
            q.save(update_fields=["question_type", "updated_at"])
            q.options.all().delete()
            q.acceptable_answers.all().delete()
            for n, text in enumerate(source_q["options"], start=1):
                QuestionOption.objects.create(question=q, text=text, order=n, is_correct=(n - 1) == int(source_q["correct"]))
        else:
            q.question_type = "gap_fill"
            q.save(update_fields=["question_type", "updated_at"])
            q.options.all().delete()
            q.acceptable_answers.all().delete()
            for value in source_q.get("answers", []):
                AcceptableAnswer.objects.create(question=q, answer_text=value, case_sensitive=False)


@transaction.atomic
def reading_set_part(request, set_no, part_no):
    if set_no < 1 or set_no > TOTAL_SETS or part_no not in PART_GUIDE:
        raise Http404
    rows = _rows_for(set_no, part_no)
    guide = PART_GUIDE[part_no]

    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            if action == "restore":
                _restore_part(set_no, part_no)
                messages.success(request, f"Reading Set {set_no} · Part {part_no} restored from the supplied source workbook.")
            elif action == "save":
                if part_no in (4, 5):
                    source = _post_text(request, "shared_source")
                    if not source:
                        raise ValidationError("Enter the shared message/text for this Part.")
                    stimulus = rows[0].stimulus
                    if stimulus is None:
                        stimulus = Stimulus.objects.create(program=_program(), title=f"Reading S{set_no} P{part_no} Source", stimulus_type="text")
                    stimulus.content = source
                    stimulus.is_active = True
                    stimulus.save(update_fields=["content", "is_active", "updated_at"])
                    for q in rows:
                        if q.stimulus_id != stimulus.pk:
                            q.stimulus = stimulus
                            q.save(update_fields=["stimulus", "updated_at"])
                for index, q in enumerate(rows, start=1):
                    if part_no == 1:
                        source = _post_text(request, f"q{index}_source")
                        if not source:
                            raise ValidationError(f"Question {index}: enter the short source text/message.")
                        stimulus = q.stimulus
                        if stimulus is None:
                            stimulus = Stimulus.objects.create(program=_program(), title=f"Reading S{set_no} P1 Source {index}", stimulus_type="text")
                            q.stimulus = stimulus
                            q.save(update_fields=["stimulus", "updated_at"])
                        stimulus.content = source
                        stimulus.is_active = True
                        stimulus.save(update_fields=["content", "is_active", "updated_at"])
                    if part_no in (1, 2, 5):
                        _save_choice(q, request, index)
                    else:
                        _save_short(q, request, index)
                messages.success(request, f"Reading Set {set_no} · Part {part_no} saved. Existing Question IDs were preserved for Practice/Mock placements.")
            else:
                raise ValidationError("Unknown action.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            return HttpResponseRedirect(reverse("admin:b1_reading_set_part", args=[set_no, part_no]))

    item_rows = []
    for index, q in enumerate(rows, start=1):
        options = list(q.options.order_by("order"))
        option_map = {int(opt.order): opt for opt in options}
        option_slots = [
            {"number": n, "label": ("A", "B", "C")[n - 1], "text": getattr(option_map.get(n), "text", "")}
            for n in range(1, 4)
        ]
        answers = list(q.acceptable_answers.order_by("pk").values_list("answer_text", flat=True))
        correct = next((str(opt.order) for opt in options if opt.is_correct), "")
        item_rows.append({
            "index": index,
            "question": q,
            "source": q.stimulus.content if part_no == 1 and q.stimulus else "",
            "option_slots": option_slots,
            "correct": correct,
            "answers": " | ".join(answers),
            "ready": _is_ready(q, part_no),
        })
    shared_source = ""
    if part_no in (4, 5) and rows and rows[0].stimulus:
        shared_source = rows[0].stimulus.content

    context = _context(request, f"Reading Set {set_no} · Part {part_no}")
    context.update({
        "set_no": set_no,
        "part_no": part_no,
        "guide": guide,
        "rows": item_rows,
        "shared_source": shared_source,
        "previous_part": part_no - 1 if part_no > 1 else None,
        "next_part": part_no + 1 if part_no < 5 else None,
        "previous_set": set_no - 1 if set_no > 1 else None,
        "next_set": set_no + 1 if set_no < TOTAL_SETS else None,
    })
    return TemplateResponse(request, "admin/reading_set_builder_v36.html", context)


if not getattr(admin.site, "_b1_reading_sets_v36_hooked", False):
    previous_get_urls = admin.site.get_urls

    def get_urls():
        return [
            path("reading-sets/", admin.site.admin_view(reading_sets), name="b1_reading_sets"),
            path("reading-sets/<int:set_no>/<int:part_no>/", admin.site.admin_view(reading_set_part), name="b1_reading_set_part"),
        ] + previous_get_urls()

    admin.site.get_urls = get_urls
    admin.site._b1_reading_sets_v36_hooked = True

