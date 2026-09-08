"""
B1 Ready Admin Part 2 / Content Studio.

This module enhances registered Django ModelAdmin instances after autodiscovery.
It does not alter models or database schema.
"""

from __future__ import annotations

from pathlib import Path

from django import forms
from django.contrib import admin
from django.utils.html import format_html


AUDIO_ACCEPT = "audio/*,.mp3,.wav,.m4a,.ogg,.webm,.aac,.flac"
IMAGE_ACCEPT = "image/*,.jpg,.jpeg,.png,.webp,.gif,.avif"
DOC_ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv,.zip"
MEDIA_ACCEPT = f"{DOC_ACCEPT},{IMAGE_ACCEPT},{AUDIO_ACCEPT},video/*,.mp4,.mov,.m4v,.webm"


def _field_names(model):
    return {f.name for f in model._meta.get_fields()}


def _existing(model, names):
    available = _field_names(model)
    return tuple(name for name in names if name in available)


def _file_url(value):
    try:
        return value.url
    except Exception:
        return ""


def _preview_link(url, label="Open file"):
    if not url:
        return ""
    return format_html(
        '<a class="b1-server-file-link" href="{}" target="_blank" rel="noopener">{} ↗</a>',
        url,
        label,
    )


def _academy_forms_and_admins():
    try:
        from academy.models import CourseMaterial, TestMaterial
    except Exception:
        return

    # ---------- COURSE MATERIAL ----------
    course_admin = admin.site._registry.get(CourseMaterial)
    if course_admin is not None:
        model = CourseMaterial

        class B1CourseMaterialForm(forms.ModelForm):
            class Meta:
                model = CourseMaterial
                fields = "__all__"
                widgets = {
                    "description": forms.Textarea(attrs={"rows": 4}),
                    "content_text": forms.Textarea(attrs={"rows": 10}),
                }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

                labels = {
                    "title": "Lesson / resource title",
                    "skill": "Skill area",
                    "material_type": "Resource type",
                    "description": "Short student-facing description",
                    "content_text": "Lesson text / written content",
                    "file": "Document / downloadable file",
                    "audio_file": "Audio lesson",
                    "external_url": "External video / resource URL",
                    "is_published": "Visible to students",
                    "sort_order": "Display order",
                }
                for name, label in labels.items():
                    if name in self.fields:
                        self.fields[name].label = label

                if "file" in self.fields:
                    self.fields["file"].widget.attrs["accept"] = MEDIA_ACCEPT
                    self.fields["file"].help_text = (
                        "Upload the student resource here. PDF/document/download files work best "
                        "for material types that use a local file."
                    )
                if "audio_file" in self.fields:
                    self.fields["audio_file"].widget.attrs["accept"] = AUDIO_ACCEPT
                    self.fields["audio_file"].help_text = (
                        "Upload the lesson audio here. Listen to the preview before publishing."
                    )
                if "external_url" in self.fields:
                    self.fields["external_url"].help_text = (
                        "Use for an external lesson/video/resource URL when no local upload is needed."
                    )
                if "is_published" in self.fields:
                    self.fields["is_published"].help_text = (
                        "Turn this on only when the resource is ready for student access."
                    )

        def b1_material_preview(self, obj):
            if not obj or not getattr(obj, "pk", None):
                return format_html(
                    '<div class="b1-preview-empty">Save this material once to enable stored-file previews.</div>'
                )

            chunks = []

            audio = getattr(obj, "audio_file", None)
            if audio:
                url = _file_url(audio)
                if url:
                    chunks.append(
                        format_html(
                            '<div class="b1-server-preview-block">'
                            '<b>Audio lesson</b>'
                            '<audio controls preload="metadata" src="{}"></audio>'
                            '</div>',
                            url,
                        )
                    )

            local_file = getattr(obj, "file", None)
            if local_file:
                url = _file_url(local_file)
                suffix = Path(getattr(local_file, "name", "")).suffix.lower()

                if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"} and url:
                    chunks.append(
                        format_html(
                            '<div class="b1-server-preview-block">'
                            '<b>Uploaded image</b>'
                            '<img src="{}" alt="">'
                            '</div>',
                            url,
                        )
                    )
                elif url:
                    chunks.append(
                        format_html(
                            '<div class="b1-server-preview-block">'
                            '<b>Uploaded resource</b>{}'
                            '</div>',
                            _preview_link(url, Path(getattr(local_file, "name", "file")).name),
                        )
                    )

            external = getattr(obj, "external_url", "")
            if external:
                chunks.append(
                    format_html(
                        '<div class="b1-server-preview-block"><b>External resource</b>{}</div>',
                        _preview_link(external, "Open external resource"),
                    )
                )

            if not chunks:
                return format_html(
                    '<div class="b1-preview-empty">No media or external resource is attached yet.</div>'
                )

            return format_html('<div class="b1-server-preview-grid">{}</div>', format_html("".join(str(x) for x in chunks)))

        def b1_delivery_state(self, obj):
            if getattr(obj, "is_published", False):
                return format_html('<span class="b1-admin-badge is-live">Published</span>')
            return format_html('<span class="b1-admin-badge is-draft">Draft</span>')

        cls = course_admin.__class__
        setattr(cls, "b1_material_preview", admin.display(description="Resource preview")(b1_material_preview))
        setattr(cls, "b1_delivery_state", admin.display(description="Status")(b1_delivery_state))

        course_admin.form = B1CourseMaterialForm
        course_admin.list_display = _existing(
            model,
            ("title", "course", "skill", "material_type")
        ) + ("b1_delivery_state",) + _existing(model, ("sort_order", "updated_at"))
        course_admin.list_filter = _existing(model, ("course", "skill", "material_type", "is_published"))
        course_admin.search_fields = _existing(model, ("title", "description", "content_text", "external_url"))
        course_admin.list_per_page = 40
        course_admin.save_on_top = True
        course_admin.actions_on_top = True

        readonly = list(getattr(course_admin, "readonly_fields", ()))
        for field in ("b1_material_preview", "created_at", "updated_at"):
            if field == "b1_material_preview" or field in _field_names(model):
                if field not in readonly:
                    readonly.append(field)
        course_admin.readonly_fields = tuple(readonly)

        course_admin.fieldsets = (
            (
                "1. Resource identity",
                {
                    "description": "Choose where the lesson belongs and how students should recognize it.",
                    "fields": _existing(
                        model,
                        ("course", "title", "skill", "material_type", "is_published", "sort_order"),
                    ),
                },
            ),
            (
                "2. Lesson content",
                {
                    "description": "Add the text that explains or accompanies the lesson/resource.",
                    "fields": _existing(model, ("description", "content_text")),
                },
            ),
            (
                "3. Files / audio / external resource",
                {
                    "description": (
                        "Use the field that matches the material type. Preview the resource before publishing."
                    ),
                    "fields": _existing(model, ("file", "audio_file", "external_url"))
                    + ("b1_material_preview",),
                },
            ),
            (
                "4. Ownership & audit",
                {
                    "classes": ("collapse",),
                    "fields": _existing(model, ("created_by", "created_at", "updated_at")),
                },
            ),
        )

    # ---------- TEST MATERIAL ----------
    test_admin = admin.site._registry.get(TestMaterial)
    if test_admin is not None:
        model = TestMaterial

        class B1TestMaterialForm(forms.ModelForm):
            class Meta:
                model = TestMaterial
                fields = "__all__"
                widgets = {
                    "instructions": forms.Textarea(attrs={"rows": 4}),
                    "passage_text": forms.Textarea(attrs={"rows": 11}),
                    "prompt_text": forms.Textarea(attrs={"rows": 8}),
                    "transcript": forms.Textarea(attrs={"rows": 9}),
                }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

                labels = {
                    "title": "Material title",
                    "instructions": "Student / conversion instructions",
                    "passage_text": "Reading passage / supporting text",
                    "prompt_text": "Writing prompt / task text",
                    "transcript": "Listening transcript",
                    "audio_file": "Listening audio",
                    "attachment": "Supporting document / attachment",
                    "answer_key": "Structured answer key",
                    "source_note": "Private source note",
                    "is_published": "Published",
                    "is_question_bank_ready": "Reviewed and ready for Question Bank",
                }
                for name, label in labels.items():
                    if name in self.fields:
                        self.fields[name].label = label

                if "audio_file" in self.fields:
                    self.fields["audio_file"].widget.attrs["accept"] = AUDIO_ACCEPT
                if "attachment" in self.fields:
                    self.fields["attachment"].widget.attrs["accept"] = MEDIA_ACCEPT

                if "is_question_bank_ready" in self.fields:
                    self.fields["is_question_bank_ready"].help_text = (
                        "Use this only after the material has been checked and is ready to become real Question Bank items."
                    )

        def b1_test_material_preview(self, obj):
            if not obj or not getattr(obj, "pk", None):
                return format_html(
                    '<div class="b1-preview-empty">Save once to enable stored media previews.</div>'
                )
            chunks = []

            audio = getattr(obj, "audio_file", None)
            if audio:
                url = _file_url(audio)
                if url:
                    chunks.append(
                        format_html(
                            '<div class="b1-server-preview-block"><b>Listening audio</b>'
                            '<audio controls preload="metadata" src="{}"></audio></div>',
                            url,
                        )
                    )

            attachment = getattr(obj, "attachment", None)
            if attachment:
                url = _file_url(attachment)
                if url:
                    chunks.append(
                        format_html(
                            '<div class="b1-server-preview-block"><b>Attachment</b>{}</div>',
                            _preview_link(url, Path(getattr(attachment, "name", "attachment")).name),
                        )
                    )

            if not chunks:
                return format_html(
                    '<div class="b1-preview-empty">No audio or attachment uploaded yet.</div>'
                )
            return format_html('<div class="b1-server-preview-grid">{}</div>', format_html("".join(str(x) for x in chunks)))

        def b1_review_state(self, obj):
            if getattr(obj, "is_question_bank_ready", False):
                return format_html('<span class="b1-admin-badge is-ready">Question Bank ready</span>')
            if getattr(obj, "is_published", False):
                return format_html('<span class="b1-admin-badge is-live">Published</span>')
            return format_html('<span class="b1-admin-badge is-draft">Draft</span>')

        cls = test_admin.__class__
        setattr(cls, "b1_test_material_preview", admin.display(description="Media preview")(b1_test_material_preview))
        setattr(cls, "b1_review_state", admin.display(description="Workflow")(b1_review_state))

        test_admin.form = B1TestMaterialForm
        test_admin.list_display = _existing(model, ("title", "program", "skill", "course")) + (
            "b1_review_state",
        ) + _existing(model, ("updated_at",))
        test_admin.list_filter = _existing(
            model,
            ("program", "skill", "is_published", "is_question_bank_ready"),
        )
        test_admin.search_fields = _existing(
            model,
            ("title", "instructions", "passage_text", "prompt_text", "transcript", "source_note"),
        )
        test_admin.list_per_page = 40
        test_admin.save_on_top = True

        readonly = list(getattr(test_admin, "readonly_fields", ()))
        for field in ("b1_test_material_preview", "created_at", "updated_at"):
            if field == "b1_test_material_preview" or field in _field_names(model):
                if field not in readonly:
                    readonly.append(field)
        test_admin.readonly_fields = tuple(readonly)

        test_admin.fieldsets = (
            (
                "1. Material identity",
                {
                    "fields": _existing(
                        model,
                        ("program", "course", "title", "skill", "is_published", "is_question_bank_ready"),
                    )
                },
            ),
            (
                "2. Student / question source content",
                {
                    "description": (
                        "Fill only the content appropriate to the selected skill. "
                        "The guide above the form explains what is normally needed."
                    ),
                    "fields": _existing(
                        model,
                        ("instructions", "passage_text", "prompt_text", "transcript"),
                    ),
                },
            ),
            (
                "3. Audio / supporting files",
                {
                    "fields": _existing(model, ("audio_file", "attachment"))
                    + ("b1_test_material_preview",),
                },
            ),
            (
                "4. Answer / internal review information",
                {
                    "fields": _existing(model, ("answer_key", "source_note")),
                },
            ),
            (
                "5. Ownership & audit",
                {
                    "classes": ("collapse",),
                    "fields": _existing(model, ("created_by", "created_at", "updated_at")),
                },
            ),
        )


def _question_bank_admins():
    try:
        from question_bank.models import Question, Stimulus
    except Exception:
        return

    # Preserve the rich audio/content setup already installed.
    question_admin = admin.site._registry.get(Question)
    if question_admin is not None:
        question_admin.list_per_page = 50
        question_admin.actions_on_top = True
        question_admin.save_on_top = True
        question_admin.show_full_result_count = False

    stimulus_admin = admin.site._registry.get(Stimulus)
    if stimulus_admin is not None:
        stimulus_admin.list_per_page = 40
        stimulus_admin.actions_on_top = True
        stimulus_admin.save_on_top = True
        stimulus_admin.show_full_result_count = False


def _assessment_admins():
    try:
        from assessments.models import MockTest, TestSection, TestPart
    except Exception:
        return

    for model in (MockTest, TestSection, TestPart):
        ma = admin.site._registry.get(model)
        if ma is not None:
            ma.list_per_page = 40
            ma.actions_on_top = True
            ma.save_on_top = True
            ma.show_full_result_count = False


def apply_content_admin_ux():
    if getattr(admin.site, "_b1_content_ux_v336_applied", False):
        return
    _question_bank_admins()
    _academy_forms_and_admins()
    _assessment_admins()
    admin.site._b1_content_ux_v336_applied = True


# Run once now if registration is already complete.
try:
    apply_content_admin_ux()
except Exception:
    pass

# Also guarantee application when Django builds the admin URL set,
# which occurs after admin autodiscovery.
if not getattr(admin.site, "_b1_content_ux_v336_hooked", False):
    _original_get_urls = admin.site.get_urls

    def _b1_content_get_urls():
        apply_content_admin_ux()
        return _original_get_urls()

    admin.site.get_urls = _b1_content_get_urls
    admin.site._b1_content_ux_v336_hooked = True
