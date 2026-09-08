from __future__ import annotations

from django.apps import apps
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from assessments.writing_bank_v39_data import load_data

Question = apps.get_model("question_bank", "Question")
Stimulus = apps.get_model("question_bank", "Stimulus")
MockTest = apps.get_model("assessments", "MockTest")
Program = MockTest._meta.get_field("program").related_model

VERSION = "39.0"


def _program():
    ranked = []
    for obj in Program._default_manager.all():
        values = [str(obj)] + [
            str(getattr(obj, name, "") or "")
            for name in ("title", "name", "slug", "code", "short_name")
        ]
        text = " ".join(values).lower()
        score = (10 if "cambridge" in text else 0) + (8 if "general english" in text else 0)
        score -= 20 if ("ielts" in text or "ukvi" in text) else 0
        if score > 0:
            ranked.append((score, obj.pk, obj))
    if not ranked:
        raise Http404
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked[0][2]


def _context(request, title):
    ctx = admin.site.each_context(request)
    ctx.update(
        {
            "title": title,
            "site_title": admin.site.site_title,
            "site_header": admin.site.site_header,
        }
    )
    return ctx


def _canonical_source(set_no, part_no):
    data = load_data()
    row = next((row for row in data["canonical_sets"] if int(row["set_no"]) == int(set_no)), None)
    if row is None:
        raise Http404
    task = row["parts"].get(str(part_no))
    if task is None:
        raise Http404
    return task


def _extra_source(number):
    data = load_data()
    row = next((row for row in data["extra_part2"] if int(row["number"]) == int(number)), None)
    if row is None:
        raise Http404
    return row


def _question(title):
    return (
        Question._default_manager
        .filter(program=_program(), skill="writing", title=title, is_active=True)
        .select_related("stimulus")
        .order_by("pk")
        .first()
    )


def _canonical_question(set_no, part_no):
    return _question(f"Writing S{set_no} P{part_no} Q1")


def _extra_question(number):
    return _question(f"Writing Extra P2 Q{number:02d}")


def _stimulus_content(question):
    if not question or not question.stimulus:
        return ""
    return str(getattr(question.stimulus, "content", "") or "")


def _is_ready(question):
    return bool(
        question
        and question.is_active
        and (question.prompt_text or "").strip()
        and _stimulus_content(question).strip()
    )


def _save_question_text(question, context_text, prompt_text, min_words):
    if not question:
        raise ValidationError("This Writing question is missing. Re-run the V39 importer.")
    if not context_text.strip():
        raise ValidationError("Source / scenario text cannot be blank.")
    if not prompt_text.strip():
        raise ValidationError("Student task cannot be blank.")

    if question.stimulus is None:
        question.stimulus = Stimulus._default_manager.create(
            program=_program(),
            title=f"{question.title} Source",
            stimulus_type="text",
            content=context_text.strip(),
            is_active=True,
        )
    else:
        question.stimulus.content = context_text.strip()
        question.stimulus.is_active = True
        question.stimulus.save()

    question.prompt_text = prompt_text.strip()
    question.show_prompt_text = True
    question.min_word_count = min_words
    question.is_active = True
    question.save()


def writing_sets(request):
    data = load_data()
    rows = []
    for source_row in data["canonical_sets"]:
        set_no = int(source_row["set_no"])
        parts = []
        for part_no in (1, 2):
            q = _canonical_question(set_no, part_no)
            source = source_row["parts"][str(part_no)]
            parts.append(
                {
                    "part_no": part_no,
                    "type": source["type"],
                    "question": q,
                    "ready": _is_ready(q),
                    "min_words": getattr(q, "min_word_count", 50) if q else 50,
                    "url": reverse("admin:b1_writing_set_part", args=[set_no, part_no]),
                }
            )
        rows.append(
            {
                "set_no": set_no,
                "parts": parts,
                "ready": all(part["ready"] for part in parts),
                "search": " ".join(
                    [f"set {set_no}"] + [part["type"] for part in parts]
                ).lower(),
            }
        )

    extra_rows = []
    for source in data["extra_part2"]:
        number = int(source["number"])
        q = _extra_question(number)
        extra_rows.append(
            {
                "number": number,
                "title": source["title"],
                "ready": _is_ready(q),
                "url": reverse("admin:b1_writing_extra_part2", args=[number]),
            }
        )

    context = _context(request, "Writing Sets")
    context.update(
        {
            "rows": rows,
            "extra_rows": extra_rows,
            "ready_sets": sum(1 for row in rows if row["ready"]),
            "ready_extras": sum(1 for row in extra_rows if row["ready"]),
            "total_sets": 50,
            "total_tasks": 100,
            "version": VERSION,
        }
    )
    return TemplateResponse(request, "admin/writing_sets_v39.html", context)


@transaction.atomic
def writing_set_part(request, set_no, part_no):
    if set_no < 1 or set_no > 50 or part_no not in (1, 2):
        raise Http404

    source = _canonical_source(set_no, part_no)
    q = _canonical_question(set_no, part_no)
    if q is None:
        messages.error(request, "This Writing task is not in the database. Re-run the V39 importer.")
        return HttpResponseRedirect(reverse("admin:b1_writing_sets"))

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        try:
            if action == "restore":
                _save_question_text(q, source["context"], source["prompt"], 50)
                messages.success(
                    request,
                    f"Writing Set {set_no} · Part {part_no} restored from {source['source_file']}.",
                )
            elif action == "save":
                context_text = (request.POST.get("context_text") or "").strip()
                prompt_text = (request.POST.get("prompt_text") or "").strip()
                try:
                    min_words = int(request.POST.get("min_words") or 50)
                except (TypeError, ValueError):
                    raise ValidationError("Minimum words must be a whole number.")
                if min_words < 1 or min_words > 1000:
                    raise ValidationError("Minimum words must be between 1 and 1000.")
                _save_question_text(q, context_text, prompt_text, min_words)
                messages.success(
                    request,
                    f"Writing Set {set_no} · Part {part_no} saved. Existing Question ID {q.pk} was preserved.",
                )
            else:
                raise ValidationError("Unknown action.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("admin:b1_writing_set_part", args=[set_no, part_no]))

    context = _context(request, f"Writing Set {set_no} · Part {part_no}")
    context.update(
        {
            "set_no": set_no,
            "part_no": part_no,
            "task_type": source["type"],
            "source_file": source["source_file"],
            "question": q,
            "context_text": _stimulus_content(q),
            "prompt_text": q.prompt_text,
            "min_words": getattr(q, "min_word_count", 50) or 50,
            "previous_part": part_no - 1 if part_no > 1 else None,
            "next_part": part_no + 1 if part_no < 2 else None,
            "previous_set": set_no - 1 if set_no > 1 else None,
            "next_set": set_no + 1 if set_no < 50 else None,
        }
    )
    return TemplateResponse(request, "admin/writing_set_builder_v39.html", context)


@transaction.atomic
def writing_extra_part2(request, number):
    if number < 1 or number > 10:
        raise Http404

    source = _extra_source(number)
    q = _extra_question(number)
    if q is None:
        messages.error(request, "This supplementary Writing task is missing. Re-run the V39 importer.")
        return HttpResponseRedirect(reverse("admin:b1_writing_sets"))

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        try:
            if action == "restore":
                _save_question_text(q, source["context"], source["prompt"], 50)
                messages.success(request, f"Supplementary Part 2 task {number} restored from source.")
            elif action == "save":
                try:
                    min_words = int(request.POST.get("min_words") or 50)
                except (TypeError, ValueError):
                    raise ValidationError("Minimum words must be a whole number.")
                if min_words < 1 or min_words > 1000:
                    raise ValidationError("Minimum words must be between 1 and 1000.")
                _save_question_text(
                    q,
                    (request.POST.get("context_text") or "").strip(),
                    (request.POST.get("prompt_text") or "").strip(),
                    min_words,
                )
                messages.success(request, f"Supplementary Part 2 task {number} saved.")
            else:
                raise ValidationError("Unknown action.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("admin:b1_writing_extra_part2", args=[number]))

    context = _context(request, f"Supplementary Writing Part 2 · {number}")
    context.update(
        {
            "extra_mode": True,
            "number": number,
            "set_no": None,
            "part_no": 2,
            "task_type": source["type"],
            "extra_title": source["title"],
            "source_file": source["source_file"],
            "question": q,
            "context_text": _stimulus_content(q),
            "prompt_text": q.prompt_text,
            "min_words": getattr(q, "min_word_count", 50) or 50,
            "previous_extra": number - 1 if number > 1 else None,
            "next_extra": number + 1 if number < 10 else None,
        }
    )
    return TemplateResponse(request, "admin/writing_set_builder_v39.html", context)


if not getattr(admin.site, "_b1_writing_sets_v39_hooked", False):
    previous_get_urls = admin.site.get_urls

    def get_urls():
        return [
            path("writing-sets/", admin.site.admin_view(writing_sets), name="b1_writing_sets"),
            path(
                "writing-sets/<int:set_no>/<int:part_no>/",
                admin.site.admin_view(writing_set_part),
                name="b1_writing_set_part",
            ),
            path(
                "writing-sets/extra/<int:number>/",
                admin.site.admin_view(writing_extra_part2),
                name="b1_writing_extra_part2",
            ),
        ] + previous_get_urls()

    admin.site.get_urls = get_urls
    admin.site._b1_writing_sets_v39_hooked = True
