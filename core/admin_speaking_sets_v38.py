from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.text import get_valid_filename

from assessments.models import Program
from question_bank.models import Question
from core.speaking_audio_gate_v38_6 import speaking_audio_status, sync_speaking_practice_publication

DATA_PATH = Path(__file__).resolve().parents[1] / "assessments" / "speaking_bank_v38_5.json"
TITLE_RE = re.compile(r"^Speaking S(\d+) P(\d+) Q(\d+)$", re.I)
SOURCE_PREFIX = "question_bank/question_audio/imported/speaking/source_library"
CUSTOM_PREFIX = "question_bank/question_audio/imported/speaking/custom"
PART_LABELS = {
    1: ("Listen and answer", "4 audio questions · 10-second responses"),
    2: ("Longer answers", "4 audio questions · 20-second responses"),
    3: ("Read aloud", "4 written sentences · no prompt audio required"),
    4: ("Extended read aloud", "4 longer written sentences · no prompt audio required"),
    5: ("Leave a message", "40 seconds preparation · 60 seconds speaking · no prompt audio required"),
}


def _data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _program():
    qs = Program.objects.filter(code="cambridge-general")
    if not qs.exists():
        qs = Program.objects.filter(name__icontains="Cambridge")
    return qs.order_by("pk").first()


def _context(request, title):
    ctx = admin.site.each_context(request)
    ctx.update({"title": title, "site_title": admin.site.site_title, "site_header": admin.site.site_header})
    return ctx


def _question(set_no, part_no, q_no):
    prog = _program()
    if not prog:
        raise Http404
    return Question.objects.filter(
        program=prog, skill="speaking", title=f"Speaking S{set_no} P{part_no} Q{q_no}", is_active=True
    ).order_by("pk").first()


def _source_prompt(data, set_no, part_no, q_no):
    row = data["sets"][str(set_no)]
    if part_no == 5:
        info = row["5"]
        return "\\n".join([f"Task: {info['task']}", "", "You should:"] + [f"• {x}" for x in info.get("bullets", [])])
    return row[str(part_no)][q_no-1]


def _library_choices(data, part_no):
    if part_no not in (1, 2):
        return []
    rows = []
    for item in data.get("audio_library", {}).get(str(part_no), []):
        rel = f"{SOURCE_PREFIX}/part_{part_no}/{item['file']}"
        rows.append({"value": rel, "label": item["display"], "bytes": item.get("bytes", 0)})
    return sorted(rows, key=lambda x: x["label"].lower())


def _current_audio(q):
    if not q or not q.prompt_audio:
        return ""
    return q.prompt_audio.name or ""


def _safe_match(data, set_no, part_no, q_no):
    if part_no not in (1,2):
        return ""
    prompt = _source_prompt(data, set_no, part_no, q_no)
    filename = data.get("audio_match", {}).get(str(part_no), {}).get(prompt)
    if not filename:
        return ""
    return f"{SOURCE_PREFIX}/part_{part_no}/{filename}"


def speaking_sets(request):
    data = _data()
    prog = _program()
    audio_status = speaking_audio_status(prog.pk) if prog else {}
    rows = []
    for set_no in range(2,32):
        parts=[]
        total_ready=0
        physical_audio=0
        for part_no in range(1,6):
            count=1 if part_no==5 else 4
            qs=[_question(set_no,part_no,i) for i in range(1,count+1)]
            ready=sum(1 for q in qs if q and (q.prompt_text or q.prompt_audio))
            audio=sum(1 for q in qs if q and q.prompt_audio)
            total_ready += ready
            physical_audio += audio
            label, help_text = PART_LABELS[part_no]
            parts.append({
                "number":part_no,"label":label,"help":help_text,"ready":ready,"count":count,"audio":audio,
                "url":reverse("admin:b1_speaking_set_part", args=[set_no,part_no]),
            })
        gate = audio_status.get(set_no, {"present": 0, "missing": [], "public": False})
        rows.append({
            "set_no":set_no,
            "parts":parts,
            "ready":total_ready,
            "physical_audio":physical_audio,
            "required_audio":gate["present"],
            "missing_audio":gate["missing"],
            "public":gate["public"],
        })

    context=_context(request,"Speaking Sets")
    context.update({
        "rows":rows,
        "public_sets":sum(1 for row in rows if row["public"]),
        "total_sets":30,
        "total_questions":510,
        "p1_library":len(data.get("audio_library",{}).get("1",[])),
        "p2_library":len(data.get("audio_library",{}).get("2",[])),
        "p1_attached": Question.objects.filter(program=prog, skill="speaking", is_active=True, title__regex=r"^Speaking S\d+ P1 Q\d+$").exclude(prompt_audio="").exclude(prompt_audio__isnull=True).count() if prog else 0,
        "p2_attached": Question.objects.filter(program=prog, skill="speaking", is_active=True, title__regex=r"^Speaking S\d+ P2 Q\d+$").exclude(prompt_audio="").exclude(prompt_audio__isnull=True).count() if prog else 0,
    })
    return TemplateResponse(request,"admin/speaking_sets_v38.html",context)


def speaking_set_part(request,set_no,part_no):
    if set_no<2 or set_no>31 or part_no not in PART_LABELS:
        raise Http404
    data=_data()
    count=1 if part_no==5 else 4
    questions=[_question(set_no,part_no,i) for i in range(1,count+1)]
    if any(q is None for q in questions):
        messages.error(request,"This Speaking Set is incomplete in the database. Re-run the V38.5.1 importer.")
        return HttpResponseRedirect(reverse("admin:b1_speaking_sets"))

    choices=_library_choices(data,part_no)
    allowed={row["value"] for row in choices}

    if request.method=="POST":
        action=request.POST.get("action","save")
        if action=="restore":
            for i,q in enumerate(questions,1):
                q.prompt_text=_source_prompt(data,set_no,part_no,i)
                q.show_prompt_text = part_no>=3
                if part_no in (1,2):
                    q.prompt_audio.name = _safe_match(data,set_no,part_no,i) or ""
                else:
                    q.prompt_audio = None
                q.save()
            public_sets = sync_speaking_practice_publication()
            set_public = set_no in public_sets
            messages.success(
                request,
                f"Speaking Set {set_no} · Part {part_no} restored. "
                + ("This Set is PUBLIC for students." if set_public else "This Set remains PRIVATE until all 8 Part 1/2 audio files are uploaded.")
            )
            return HttpResponseRedirect(reverse("admin:b1_speaking_set_part",args=[set_no,part_no]))

        if action!="save":
            messages.error(request,"Unknown action.")
        else:
            for i,q in enumerate(questions,1):
                prompt=(request.POST.get(f"prompt_{i}") or "").strip()
                if not prompt:
                    messages.error(request,f"Question {i}: prompt text cannot be blank.")
                    return HttpResponseRedirect(reverse("admin:b1_speaking_set_part",args=[set_no,part_no]))
                q.prompt_text=prompt
                q.show_prompt_text = part_no>=3
                if part_no in (1,2):
                    if request.POST.get(f"clear_audio_{i}") == "1":
                        q.prompt_audio = None
                    selected=(request.POST.get(f"library_audio_{i}") or "").strip()
                    if selected:
                        if selected not in allowed:
                            messages.error(request,f"Question {i}: invalid source-audio selection.")
                            return HttpResponseRedirect(reverse("admin:b1_speaking_set_part",args=[set_no,part_no]))
                        q.prompt_audio.name=selected
                    upload=request.FILES.get(f"upload_audio_{i}")
                    if upload:
                        suffix=Path(upload.name).suffix.lower()
                        if suffix not in {".mp3",".m4a",".wav",".ogg",".webm",".aac"}:
                            messages.error(request,f"Question {i}: unsupported audio type {suffix or '(none)' }.")
                            return HttpResponseRedirect(reverse("admin:b1_speaking_set_part",args=[set_no,part_no]))
                        filename=f"{CUSTOM_PREFIX}/set_{set_no}/part_{part_no}/q_{i}{suffix}"
                        if default_storage.exists(filename):
                            default_storage.delete(filename)
                        saved=default_storage.save(filename,upload)
                        q.prompt_audio.name=saved
                else:
                    q.prompt_audio=None
                q.save()
            public_sets = sync_speaking_practice_publication()
            set_public = set_no in public_sets
            messages.success(
                request,
                f"Speaking Set {set_no} · Part {part_no} saved. Existing Question IDs were preserved. "
                + ("This Set is now PUBLIC for students." if set_public else "This Set is PRIVATE until all 8 Part 1/2 audio files are uploaded.")
            )
            return HttpResponseRedirect(reverse("admin:b1_speaking_set_part",args=[set_no,part_no]))

    qrows=[]
    for i,q in enumerate(questions,1):
        current=_current_audio(q)
        qrows.append({
            "index":i,"question":q,"prompt":q.prompt_text,"audio_name":current,
            "audio_url":q.prompt_audio.url if q.prompt_audio else "",
            "safe_source":_safe_match(data,set_no,part_no,i),
        })
    label,help_text=PART_LABELS[part_no]
    context=_context(request,f"Speaking Set {set_no} · Part {part_no}")
    context.update({
        "set_no":set_no,"part_no":part_no,"part_label":label,"part_help":help_text,
        "rows":qrows,"library_choices":choices,
        "previous_part":part_no-1 if part_no>1 else None,
        "next_part":part_no+1 if part_no<5 else None,
        "previous_set":set_no-1 if set_no>2 else None,
        "next_set":set_no+1 if set_no<31 else None,
    })
    return TemplateResponse(request,"admin/speaking_set_builder_v38.html",context)


if not getattr(admin.site,"_b1_speaking_sets_v38_hooked",False):
    previous_get_urls=admin.site.get_urls
    def get_urls():
        return [
            path("speaking-sets/",admin.site.admin_view(speaking_sets),name="b1_speaking_sets"),
            path("speaking-sets/<int:set_no>/<int:part_no>/",admin.site.admin_view(speaking_set_part),name="b1_speaking_set_part"),
        ] + previous_get_urls()
    admin.site.get_urls=get_urls
    admin.site._b1_speaking_sets_v38_hooked=True

