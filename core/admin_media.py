from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.shortcuts import render
from django.urls import NoReverseMatch, path, reverse


admin.site.site_header = "B1 Ready Administration"
admin.site.site_title = "B1 Ready Admin"
admin.site.index_title = "Operations & Content Control"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".webm"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".csv", ".zip"}


def _kind(name: str) -> str:
    ext = Path(name or "").suffix.lower()
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in DOC_EXTS:
        return "document"
    return "other"


def _human_size(size):
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return "—"


def _admin_change_url(obj):
    try:
        opts = obj._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=(obj.pk,))
    except (NoReverseMatch, AttributeError):
        return ""


def _file_url(field_file):
    try:
        return field_file.url
    except Exception:
        return ""


def _file_size(field_file):
    try:
        return field_file.size
    except Exception:
        return None


def _source_files():
    base = Path(settings.BASE_DIR)
    excluded = {
        ".venv", "venv", "env", "node_modules", ".git", "__pycache__",
        "backups", ".patch_backups", "staticfiles", "media",
    }
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".py", ".html"}:
            continue
        rel = p.relative_to(base)
        if any(part in excluded for part in rel.parts):
            continue
        if "migrations" in rel.parts or rel.name in {"admin.py", "models.py"}:
            continue
        yield p


@lru_cache(maxsize=256)
def _frontend_references(field_name: str, model_name: str):
    hits = []
    for p in _source_files():
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if field_name in body:
            hits.append(str(p.relative_to(settings.BASE_DIR)))
            if len(hits) >= 6:
                break
    return tuple(hits)


def _known_connection_checks():
    base = Path(settings.BASE_DIR)
    attempts = base / "attempts" / "views.py"
    attempts_text = attempts.read_text(encoding="utf-8", errors="ignore") if attempts.exists() else ""

    speaking_question_audio = "item.question.prompt_audio" in attempts_text
    stimulus_audio = (
        "stimulus.audio_file" in attempts_text
        or "item.question.stimulus.audio_file" in attempts_text
    )

    learning_hits = []
    for model_name in ("CourseMaterial", "TestMaterial"):
        for p in _source_files():
            try:
                body = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if model_name in body:
                rel = str(p.relative_to(base))
                if rel not in learning_hits:
                    learning_hits.append(rel)
            if len(learning_hits) >= 8:
                break

    return {
        "question_audio": {
            "ok": speaking_question_audio,
            "title": "Question audio → test/practice runner",
            "detail": (
                "Connected: question-specific uploaded audio is referenced by the active runner."
                if speaking_question_audio
                else "No direct runner reference was detected. Review before relying on this upload path."
            ),
        },
        "stimulus_audio": {
            "ok": stimulus_audio,
            "title": "Shared Stimulus audio → test/practice runner",
            "detail": (
                "Connected: shared listening/speaking Stimulus audio is referenced by the active runner."
                if stimulus_audio
                else "No direct Stimulus audio reference was detected in the active runner."
            ),
        },
        "learning_materials": {
            "ok": bool(learning_hits),
            "title": "Course/Test materials → student-facing source",
            "detail": (
                "Frontend/source references detected: " + ", ".join(learning_hits[:4])
                if learning_hits
                else "No CourseMaterial/TestMaterial source reference was detected outside models/admin. Uploads may be admin-only until a student view uses them."
            ),
        },
    }


@staff_member_required
def media_center(request):
    query = (request.GET.get("q") or "").strip().lower()
    selected_kind = (request.GET.get("kind") or "").strip().lower()
    selected_model = (request.GET.get("model") or "").strip().lower()

    entries = []
    model_choices = set()
    scan_warnings = []
    file_models = []

    for model in apps.get_models():
        file_fields = [
            f for f in model._meta.fields
            if isinstance(f, (models.FileField, models.ImageField))
        ]
        if not file_fields:
            continue
        label = f"{model._meta.app_label}.{model.__name__}"
        model_choices.add(label)
        file_models.append((model, file_fields))

    MAX_OBJECTS_PER_MODEL = 250
    MAX_ENTRIES = 1000

    for model, file_fields in file_models:
        label = f"{model._meta.app_label}.{model.__name__}"
        if selected_model and selected_model != label.lower():
            continue
        try:
            qs = model._default_manager.all().order_by("-pk")[:MAX_OBJECTS_PER_MODEL]
        except Exception as exc:
            scan_warnings.append(f"{label}: {exc}")
            continue

        for obj in qs:
            obj_text = str(obj)
            for field in file_fields:
                field_file = getattr(obj, field.name, None)
                if not field_file or not getattr(field_file, "name", ""):
                    continue
                name = field_file.name
                kind = _kind(name)

                if selected_kind and selected_kind != kind:
                    continue
                if query and query not in f"{obj_text} {name} {label} {field.name}".lower():
                    continue

                refs = _frontend_references(field.name, model.__name__)
                entries.append({
                    "kind": kind,
                    "name": Path(name).name,
                    "stored_name": name,
                    "size": _human_size(_file_size(field_file)),
                    "url": _file_url(field_file),
                    "model_label": label,
                    "model_verbose": str(model._meta.verbose_name).title(),
                    "object": obj_text,
                    "field": field.name,
                    "admin_url": _admin_change_url(obj),
                    "frontend_refs": refs,
                    "frontend_connected": bool(refs),
                })
                if len(entries) >= MAX_ENTRIES:
                    break
            if len(entries) >= MAX_ENTRIES:
                break
        if len(entries) >= MAX_ENTRIES:
            break

    counts = {"all": len(entries), "audio": 0, "video": 0, "image": 0, "document": 0, "other": 0}
    for entry in entries:
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1

    context = admin.site.each_context(request)
    context.update({
        "title": "Media Center",
        "entries": entries,
        "counts": counts,
        "query": request.GET.get("q", ""),
        "selected_kind": selected_kind,
        "selected_model": request.GET.get("model", ""),
        "model_choices": sorted(model_choices),
        "connection_checks": _known_connection_checks(),
        "scan_warnings": scan_warnings[:8],
        "entry_limit": MAX_ENTRIES,
    })
    return render(request, "admin/media_center.html", context)


# Attach Media Center directly to the existing Django AdminSite.
# No project URLconf assumptions are required.
if not getattr(admin.site, "_b1_media_v3332_installed", False):
    _original_get_urls = admin.site.get_urls

    def _b1_get_urls():
        custom = [
            path(
                "media-center/",
                admin.site.admin_view(media_center),
                name="media_center",
            )
        ]
        return custom + _original_get_urls()

    admin.site.get_urls = _b1_get_urls
    admin.site._b1_media_v3332_installed = True
