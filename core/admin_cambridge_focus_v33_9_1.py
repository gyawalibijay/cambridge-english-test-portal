from __future__ import annotations

import re
from functools import lru_cache

from django.apps import apps
from django.contrib import admin
from django.db import models
from django.db.models import Q
from django.utils.html import format_html


TARGET_APPS = {
    "question_bank",
    "academy",
    "assessments",
    "commerce",
    "website",
}

SKILLS = ("Reading", "Listening", "Speaking", "Writing")


def _model(label):
    try:
        return apps.get_model(label)
    except LookupError:
        return None


def _field_names(model):
    if model is None:
        return set()
    return {f.name for f in model._meta.get_fields()}


def _first_field(model, candidates):
    names = _field_names(model)
    for candidate in candidates:
        if candidate in names:
            return candidate
    return None


def _forward_relation_fields(model):
    for field in model._meta.get_fields():
        if (
            getattr(field, "is_relation", False)
            and getattr(field, "related_model", None) is not None
            and not getattr(field, "auto_created", False)
            and getattr(field, "concrete", False)
        ):
            yield field


def _program_match_text(obj):
    values = [str(obj)]
    for name in ("title", "name", "slug", "code", "short_name", "display_name"):
        if hasattr(obj, name):
            try:
                values.append(str(getattr(obj, name) or ""))
            except Exception:
                pass
    return " ".join(values).lower()


@lru_cache(maxsize=32)
def _cambridge_pks_for_model(model):
    """
    Do not guess from a hard-coded primary key. Match the actual records whose
    visible/admin text contains Cambridge or General English.
    """
    try:
        rows = list(model._default_manager.all())
    except Exception:
        return tuple()

    matches = []
    for obj in rows:
        text = _program_match_text(obj)
        if "cambridge" in text or "general english" in text:
            matches.append(obj.pk)
    return tuple(matches)


def _find_program_relation(model, max_depth=3):
    """
    Return (lookup_path, ProgramModel) for the shortest forward relation chain
    from model to a model named Program.

    Handles common structures such as:
      Question.program
      MockTest.program
      TestSection.mock_test.program
      TestPart.section.mock_test.program
    """
    if model is None:
        return None, None

    if model._meta.model_name == "program":
        return "", model

    queue = [(model, "", 0)]
    visited = {model}

    while queue:
        current, prefix, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        for field in _forward_relation_fields(current):
            related = field.related_model
            path = f"{prefix}__{field.name}" if prefix else field.name

            if related._meta.model_name == "program" or field.name == "program":
                return path, related

            # Follow only likely structural relations to avoid wandering through
            # users/payments and creating expensive joins.
            if field.name in {
                "course",
                "mock_test",
                "test",
                "section",
                "part",
                "test_part",
                "assessment",
                "package",
                "access_package",
                "landing_page",
            } and related not in visited:
                visited.add(related)
                queue.append((related, path, depth + 1))

    return None, None


def _restrict_queryset_to_cambridge(qs, model):
    if model._meta.model_name == "program":
        pks = _cambridge_pks_for_model(model)
        return qs.filter(pk__in=pks) if pks else qs

    lookup, program_model = _find_program_relation(model)
    if not lookup or program_model is None:
        return qs

    pks = _cambridge_pks_for_model(program_model)
    if not pks:
        return qs

    try:
        return qs.filter(**{f"{lookup}__pk__in": pks}).distinct()
    except Exception:
        return qs


def _matching_related_pk(model, text):
    wanted = str(text or "").strip().lower()
    if not wanted:
        return None

    try:
        for obj in model._default_manager.all():
            combined = _program_match_text(obj)
            if wanted == str(obj).strip().lower() or wanted in combined:
                return obj.pk
    except Exception:
        pass
    return None


def _choice_initial(field, wanted):
    wanted = str(wanted or "").strip().lower()
    for value, label in getattr(field, "choices", ()) or ():
        if wanted in {str(value).lower(), str(label).lower()}:
            return value
    return wanted


def _question_skill_field():
    Question = _model("question_bank.Question")
    return _first_field(
        Question,
        ("skill", "test_skill", "section_type", "skill_type"),
    )


def _filter_questions_by_skill(qs, skill_field, wanted):
    if not skill_field or not wanted:
        return qs

    Question = qs.model
    try:
        field = Question._meta.get_field(skill_field)
    except Exception:
        return qs

    wanted = str(wanted).strip()

    try:
        if getattr(field, "is_relation", False) and field.related_model:
            related = field.related_model
            ids = []
            for obj in related._default_manager.all():
                text = _program_match_text(obj)
                if wanted.lower() in text:
                    ids.append(obj.pk)
            return qs.filter(**{f"{skill_field}__pk__in": ids}) if ids else qs.none()

        # CharField / choices.
        return qs.filter(
            Q(**{f"{skill_field}__iexact": wanted})
            | Q(**{f"{skill_field}__icontains": wanted})
        )
    except Exception:
        return qs


def _partquestion_info():
    Question = _model("question_bank.Question")
    PartQuestion = _model("question_bank.PartQuestion")
    if Question is None or PartQuestion is None:
        return None

    question_fk = None
    for field in _forward_relation_fields(PartQuestion):
        if field.related_model == Question:
            question_fk = field.name
            break

    if not question_fk:
        return None

    part_field = _first_field(
        PartQuestion,
        (
            "part",
            "test_part",
            "section",
            "test_section",
            "part_number",
            "part_no",
        ),
    )

    set_field = _first_field(
        PartQuestion,
        (
            "set",
            "set_number",
            "set_no",
            "set_index",
            "question_set",
            "variant",
            "group",
        ),
    )

    order_field = _first_field(
        PartQuestion,
        (
            "order",
            "position",
            "sequence",
            "sort_order",
            "question_order",
        ),
    )

    return {
        "model": PartQuestion,
        "question_fk": question_fk,
        "part_field": part_field,
        "set_field": set_field,
        "order_field": order_field,
    }


def _value_label(obj, field_name):
    if not obj or not field_name:
        return None
    try:
        value = getattr(obj, field_name)
        if callable(value):
            value = value()
        if value in (None, ""):
            return None
        return str(value)
    except Exception:
        return None


def _extract_set_from_part_text(text):
    if not text:
        return None
    text = str(text)
    patterns = (
        r"\bset\s*[-:#]?\s*(\d+)\b",
        r"\bS\s*(\d+)\b",
    )
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return f"Set {m.group(1)}"
    return None


def _placement_rows(question):
    info = _partquestion_info()
    if not info:
        return []

    PartQuestion = info["model"]
    try:
        qs = PartQuestion._default_manager.filter(
            **{info["question_fk"]: question}
        )
    except Exception:
        return []

    if info["order_field"]:
        try:
            qs = qs.order_by(info["order_field"], "pk")
        except Exception:
            pass

    return list(qs[:12])


def _part_label_for_question(question):
    info = _partquestion_info()
    if not info:
        return "—"

    labels = []
    for row in _placement_rows(question):
        value = _value_label(row, info["part_field"])
        if value and value not in labels:
            labels.append(value)

    return ", ".join(labels[:3]) if labels else "—"


def _set_label_for_question(question):
    info = _partquestion_info()
    if not info:
        return "—"

    labels = []

    for row in _placement_rows(question):
        direct = _value_label(row, info["set_field"])
        if direct:
            label = direct if "set" in direct.lower() else f"Set {direct}"
            if label not in labels:
                labels.append(label)
            continue

        # If the existing schema represents sets inside the Test Part name,
        # derive the visible label without altering data.
        part_text = _value_label(row, info["part_field"])
        derived = _extract_set_from_part_text(part_text)
        if derived and derived not in labels:
            labels.append(derived)

    return ", ".join(labels[:3]) if labels else "—"


def _install_partquestion_inline(question_admin):
    info = _partquestion_info()
    if not info:
        return False

    PartQuestion = info["model"]

    for inline in getattr(question_admin, "inlines", ()) or ():
        if getattr(inline, "model", None) == PartQuestion:
            return True

    editable_fields = []
    for name in (
        info["part_field"],
        info["set_field"],
        info["order_field"],
    ):
        if not name or name in editable_fields:
            continue
        try:
            field = PartQuestion._meta.get_field(name)
            if getattr(field, "editable", True):
                editable_fields.append(name)
        except Exception:
            pass

    attrs = {
        "model": PartQuestion,
        "fk_name": info["question_fk"],
        "extra": 1,
        "show_change_link": True,
        "verbose_name": "Part / Set placement",
        "verbose_name_plural": "Part / Set placement",
        "classes": ("collapse",),
    }

    if editable_fields:
        attrs["fields"] = tuple(editable_fields)

    Inline = type("B1PartSetPlacementInlineV339", (admin.TabularInline,), attrs)
    question_admin.inlines = tuple(getattr(question_admin, "inlines", ()) or ()) + (Inline,)
    return True


def _patch_question_admin():
    Question = _model("question_bank.Question")
    if Question is None:
        return

    ma = admin.site._registry.get(Question)
    if ma is None:
        return

    cls = ma.__class__
    skill_field = _question_skill_field()

    # These methods/config values are deliberately re-applied every time.
    # V33.8.1 also has a get_urls hook and may run after this patch. Reasserting
    # the final Question columns ensures the Cambridge workspace always wins.
    def b1_part(self, obj):
        return _part_label_for_question(obj)

    def b1_set(self, obj):
        return _set_label_for_question(obj)

    cls.b1_part = admin.display(description="Part")(b1_part)
    cls.b1_set = admin.display(description="Set")(b1_set)

    title_field = _first_field(
        Question,
        ("title", "name", "prompt_title", "label"),
    )
    type_field = _first_field(
        Question,
        ("question_type", "type", "response_type"),
    )
    active_field = _first_field(
        Question,
        ("is_active", "active", "is_published", "published"),
    )

    display = [
        x for x in (
            title_field,
            skill_field,
            "b1_part",
            "b1_set",
            type_field,
            active_field,
            "b1_manage" if hasattr(cls, "b1_manage") else None,
        )
        if x
    ]

    ma.list_display = tuple(dict.fromkeys(display))
    ma.list_filter = ()
    ma.list_display_links = None
    ma.list_editable = ()
    ma.list_per_page = 30
    ma.show_full_result_count = False

    # Wrap request behaviour once only; table/config above remains repeatable.
    if not getattr(cls, "_b1_cambridge_question_v3391_wrapped", False):
        original_get_queryset = cls.get_queryset

        def get_queryset(self, request, _orig=original_get_queryset):
            qs = _orig(self, request)
            qs = _restrict_queryset_to_cambridge(qs, Question)
            wanted = request.GET.get("b1_skill", "").strip()
            if wanted:
                qs = _filter_questions_by_skill(qs, skill_field, wanted)
            return qs

        cls.get_queryset = get_queryset

        original_initial = getattr(cls, "get_changeform_initial_data", None)

        def get_changeform_initial_data(self, request, _orig=original_initial):
            initial = {}
            if _orig:
                try:
                    initial.update(_orig(self, request) or {})
                except Exception:
                    pass

            wanted_skill = request.GET.get("skill", "").strip()
            if wanted_skill and skill_field:
                try:
                    field = Question._meta.get_field(skill_field)
                    if getattr(field, "is_relation", False) and field.related_model:
                        pk = _matching_related_pk(field.related_model, wanted_skill)
                        if pk is not None:
                            initial[skill_field] = pk
                    else:
                        initial[skill_field] = _choice_initial(field, wanted_skill)
                except Exception:
                    initial[skill_field] = wanted_skill

            return initial

        cls.get_changeform_initial_data = get_changeform_initial_data
        cls._b1_cambridge_question_v3391_wrapped = True

    _install_partquestion_inline(ma)


def _patch_program_restrictions():
    """
    Restrict targeted admin lists and Program foreign-key choices to Cambridge
    only. This hides IELTS/UKVI from admin workflows without deleting them.

    list_filter is re-applied every time because older admin hooks can restore
    their filters later in Django's URL construction process.
    """
    for model, ma in list(admin.site._registry.items()):
        if model._meta.app_label not in TARGET_APPS:
            continue

        cls = ma.__class__
        marker = f"_b1_cambridge_scope_v3391_{model._meta.label_lower.replace('.', '_')}"

        # Always reassert this final UI state.
        ma.list_filter = ()

        # Request/form wrappers are installed once to avoid wrapper stacking.
        if getattr(cls, marker, False):
            continue

        original_get_queryset = cls.get_queryset

        def get_queryset(self, request, _orig=original_get_queryset, _model=model):
            qs = _orig(self, request)
            return _restrict_queryset_to_cambridge(qs, _model)

        cls.get_queryset = get_queryset

        original_fk = getattr(cls, "formfield_for_foreignkey", None)

        if original_fk:
            def formfield_for_foreignkey(
                self, db_field, request, _orig=original_fk, **kwargs
            ):
                related = getattr(db_field, "related_model", None)
                if related is not None and (
                    related._meta.model_name == "program"
                    or db_field.name == "program"
                ):
                    pks = _cambridge_pks_for_model(related)
                    if pks:
                        kwargs["queryset"] = related._default_manager.filter(pk__in=pks)
                return _orig(self, db_field, request, **kwargs)

            cls.formfield_for_foreignkey = formfield_for_foreignkey

        original_m2m = getattr(cls, "formfield_for_manytomany", None)

        if original_m2m:
            def formfield_for_manytomany(
                self, db_field, request, _orig=original_m2m, **kwargs
            ):
                related = getattr(db_field, "related_model", None)
                if related is not None and (
                    related._meta.model_name == "program"
                    or db_field.name == "programs"
                ):
                    pks = _cambridge_pks_for_model(related)
                    if pks:
                        kwargs["queryset"] = related._default_manager.filter(pk__in=pks)
                return _orig(self, db_field, request, **kwargs)

            cls.formfield_for_manytomany = formfield_for_manytomany

        setattr(cls, marker, True)


def apply_cambridge_question_workspace():
    # Order matters: first scope all program-aware admin modules, then restore
    # Question's special skill tabs / concise columns / placement workflow.
    _patch_program_restrictions()
    _patch_question_admin()


# IMPORTANT: do not apply during module import because this file may be loaded
# from accounts/admin.py before question_bank/admin.py has registered Question.
#
# V33.8.1 also wraps admin.site.get_urls(). The previous V33.9 called its own
# changes BEFORE the older hook, so V33.8.1 overwrote list_filter/list_display
# afterwards. V33.9.1 first lets every older hook finish, then applies the
# Cambridge workspace last.
if not getattr(admin.site, "_b1_cambridge_workspace_v3391_hooked", False):
    _previous_get_urls = admin.site.get_urls

    def _b1_cambridge_get_urls():
        urls = _previous_get_urls()
        apply_cambridge_question_workspace()
        return urls

    admin.site.get_urls = _b1_cambridge_get_urls
    admin.site._b1_cambridge_workspace_v3391_hooked = True
