from django import forms
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .models import (
    AcceptableAnswer,
    OrderingItem,
    PartQuestion,
    Question,
    QuestionOption,
    Stimulus,
)


AUDIO_ACCEPT = "audio/*,.mp3,.wav,.m4a,.ogg,.webm,.aac"
IMAGE_ACCEPT = "image/*,.jpg,.jpeg,.png,.webp,.gif"


class AudioDeliveryFilter(admin.SimpleListFilter):
    title = "audio delivery"
    parameter_name = "audio_delivery"

    def lookups(self, request, model_admin):
        return (
            ("question", "Question-specific uploaded audio"),
            ("stimulus", "Shared Stimulus audio"),
            ("speaking_fallback", "Speaking: browser voice fallback"),
            ("listening_missing", "Listening: audio missing"),
            ("not_required", "Audio not required"),
        )

    def queryset(self, request, queryset):
        no_question_audio = Q(prompt_audio__isnull=True) | Q(prompt_audio="")
        has_question_audio = Q(prompt_audio__isnull=False) & ~Q(prompt_audio="")
        has_stimulus_audio = (
            Q(stimulus__audio_file__isnull=False)
            & ~Q(stimulus__audio_file="")
        )
        no_stimulus_audio = (
            Q(stimulus__isnull=True)
            | Q(stimulus__audio_file__isnull=True)
            | Q(stimulus__audio_file="")
        )

        if self.value() == "question":
            return queryset.filter(has_question_audio)

        if self.value() == "stimulus":
            return queryset.filter(no_question_audio & has_stimulus_audio)

        if self.value() == "speaking_fallback":
            return (
                queryset
                .filter(no_question_audio, skill=Question.Skill.SPEAKING)
                .filter(no_stimulus_audio)
            )

        if self.value() == "listening_missing":
            return (
                queryset
                .filter(no_question_audio, skill=Question.Skill.LISTENING)
                .filter(no_stimulus_audio)
            )

        if self.value() == "not_required":
            return queryset.exclude(
                skill__in=[Question.Skill.SPEAKING, Question.Skill.LISTENING]
            )

        return queryset


class StimulusAdminForm(forms.ModelForm):
    class Meta:
        model = Stimulus
        fields = "__all__"
        widgets = {
            "content": forms.Textarea(attrs={"rows": 10}),
            "transcript": forms.Textarea(attrs={"rows": 8}),
            "source_notes": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "audio_file" in self.fields:
            self.fields["audio_file"].label = "Shared audio / Listening track"
            self.fields["audio_file"].widget.attrs["accept"] = AUDIO_ACCEPT
            self.fields["audio_file"].help_text = (
                "Use this for one real recording shared by several Listening questions, "
                "or as a shared Speaking source. Question-specific audio takes priority."
            )

        if "image_file" in self.fields:
            self.fields["image_file"].label = "Shared source image"
            self.fields["image_file"].widget.attrs["accept"] = IMAGE_ACCEPT

        if "content" in self.fields:
            self.fields["content"].label = "Reading passage / Writing scenario / source text"

        if "transcript" in self.fields:
            self.fields["transcript"].label = "Private audio transcript"
            self.fields["transcript"].help_text = (
                "Admin/evaluator reference only. It is not automatically shown to students."
            )


class QuestionAdminForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"
        widgets = {
            "prompt_text": forms.Textarea(attrs={"rows": 7}),
            "explanation": forms.Textarea(attrs={"rows": 5}),
            "evaluator_notes": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "prompt_text" in self.fields:
            self.fields["prompt_text"].label = "Question / task text"
            self.fields["prompt_text"].help_text = (
                "Exact Reading/Listening question, Writing task or Speaking prompt."
            )

        if "prompt_audio" in self.fields:
            self.fields["prompt_audio"].label = "Admin voice / question audio"
            self.fields["prompt_audio"].widget.attrs["accept"] = AUDIO_ACCEPT
            self.fields["prompt_audio"].help_text = (
                "Speaking: upload the exact approved voice here. "
                "Priority is question audio → shared Stimulus audio → current browser voice fallback. "
                "Listening: question audio overrides a linked shared Listening track."
            )

        if "prompt_image" in self.fields:
            self.fields["prompt_image"].label = "Question / task image"
            self.fields["prompt_image"].widget.attrs["accept"] = IMAGE_ACCEPT

        if "stimulus" in self.fields:
            self.fields["stimulus"].label = "Shared passage / track / scenario"
            self.fields["stimulus"].help_text = (
                "Attach reusable Reading passages, Listening recordings, Writing scenarios "
                "or other shared source material."
            )

        if "show_prompt_text" in self.fields:
            self.fields["show_prompt_text"].label = "Show prompt text to student"
            self.fields["show_prompt_text"].help_text = (
                "Keep this OFF for Cambridge Speaking questions that should be heard but not shown."
            )

        if "preparation_seconds" in self.fields:
            self.fields["preparation_seconds"].label = "Preparation time override (seconds)"
            self.fields["preparation_seconds"].help_text = (
                "Leave blank to keep the existing Test Part timer."
            )

        if "response_seconds" in self.fields:
            self.fields["response_seconds"].label = "Response time override (seconds)"
            self.fields["response_seconds"].help_text = (
                "Leave blank to keep the existing Test Part timer."
            )


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0
    fields = ("order", "text", "is_correct")


class AcceptableAnswerInline(admin.TabularInline):
    model = AcceptableAnswer
    extra = 0
    fields = ("answer_text", "case_sensitive")


class OrderingItemInline(admin.TabularInline):
    model = OrderingItem
    extra = 0
    fields = ("correct_position", "text")


class PartQuestionInline(admin.TabularInline):
    model = PartQuestion
    extra = 0
    fields = ("part", "order", "points_override", "is_required")
    autocomplete_fields = ("part",)
    verbose_name = "Practice / mock placement"
    verbose_name_plural = "Practice / mock-test placements"


@admin.register(Stimulus)
class StimulusAdmin(admin.ModelAdmin):
    form = StimulusAdminForm
    list_display = (
        "title",
        "program",
        "stimulus_type",
        "audio_state",
        "image_state",
        "question_count",
        "is_active",
        "updated_at",
    )
    list_filter = ("program", "stimulus_type", "is_active")
    search_fields = ("title", "content", "transcript", "source_notes")
    autocomplete_fields = ("program",)
    readonly_fields = (
        "audio_preview",
        "image_preview",
        "question_count_display",
        "created_at",
        "updated_at",
    )
    list_per_page = 40
    save_on_top = True

    fieldsets = (
        (
            "Source identity",
            {
                "fields": (
                    "program",
                    "title",
                    "stimulus_type",
                    "is_active",
                    "question_count_display",
                )
            },
        ),
        (
            "Reading / Writing source",
            {
                "description": (
                    "Use this text area for a Reading passage, notice, email, scenario "
                    "or reusable Writing context."
                ),
                "fields": ("content",),
            },
        ),
        (
            "Listening / media source",
            {
                "description": (
                    "Upload the real lesson/test recording here when several questions "
                    "use the same audio. You can listen to it before saving questions."
                ),
                "fields": (
                    "audio_file",
                    "audio_preview",
                    "image_file",
                    "image_preview",
                ),
            },
        ),
        (
            "Private admin reference",
            {
                "fields": ("transcript", "source_notes"),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Audio")
    def audio_state(self, obj):
        if obj.audio_file:
            return format_html(
                '<span style="color:#067647;font-weight:700">✓ Uploaded</span>'
            )
        return "—"

    @admin.display(description="Image")
    def image_state(self, obj):
        if obj.image_file:
            return format_html(
                '<span style="color:#175cd3;font-weight:700">✓ Uploaded</span>'
            )
        return "—"

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.questions.count()

    @admin.display(description="Questions using this source")
    def question_count_display(self, obj):
        return obj.questions.count() if obj and obj.pk else "Save first"

    @admin.display(description="Audio preview")
    def audio_preview(self, obj):
        if not obj or not obj.audio_file:
            return format_html(
                '<span style="color:#667085">No shared audio uploaded.</span>'
            )
        return format_html(
            '<audio controls preload="metadata" style="width:min(100%,580px)">'
            '<source src="{}"></audio>',
            obj.audio_file.url,
        )

    @admin.display(description="Image preview")
    def image_preview(self, obj):
        if not obj or not obj.image_file:
            return format_html(
                '<span style="color:#667085">No shared image uploaded.</span>'
            )
        return format_html(
            '<img src="{}" alt="" style="max-width:380px;max-height:240px;'
            'object-fit:contain;border:1px solid #d0d5dd;border-radius:12px;'
            'background:#fff;padding:6px">',
            obj.image_file.url,
        )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm
    list_display = (
        "title",
        "program",
        "skill",
        "question_type",
        "cefr_level",
        "delivery_status",
        "automatic_marking",
        "ai_grading_required",
        "placement_count",
        "is_active",
    )
    list_filter = (
        "program",
        "skill",
        "question_type",
        AudioDeliveryFilter,
        "difficulty",
        "cefr_level",
        "automatic_marking",
        "ai_grading_required",
        "is_active",
    )
    search_fields = (
        "title",
        "prompt_text",
        "explanation",
        "evaluator_notes",
        "stimulus__title",
        "stimulus__content",
        "stimulus__transcript",
    )
    autocomplete_fields = ("program", "stimulus")
    readonly_fields = (
        "effective_audio_preview",
        "audio_behavior",
        "effective_image_preview",
        "created_at",
        "updated_at",
    )
    list_select_related = ("program", "stimulus")
    list_per_page = 50
    save_on_top = True
    inlines = (
        QuestionOptionInline,
        AcceptableAnswerInline,
        OrderingItemInline,
        PartQuestionInline,
    )

    fieldsets = (
        (
            "1. Question identity",
            {
                "fields": (
                    "program",
                    "title",
                    "skill",
                    "question_type",
                    "difficulty",
                    "cefr_level",
                    "is_active",
                )
            },
        ),
        (
            "2. Student content",
            {
                "description": (
                    "This is the content students receive. Existing student-side design "
                    "and runner logic remain unchanged."
                ),
                "fields": (
                    "stimulus",
                    "prompt_text",
                    "show_prompt_text",
                    "prompt_image",
                    "effective_image_preview",
                ),
            },
        ),
        (
            "3. Voice / Listening audio",
            {
                "description": (
                    "Speaking: upload the exact approved lesson/question voice. "
                    "Listening: upload a question-specific clip here when it should "
                    "override the shared Stimulus track."
                ),
                "fields": (
                    "prompt_audio",
                    "effective_audio_preview",
                    "audio_behavior",
                ),
            },
        ),
        (
            "4. Timing / Writing limits",
            {
                "fields": (
                    "preparation_seconds",
                    "response_seconds",
                    "min_word_count",
                    "max_word_count",
                )
            },
        ),
        (
            "5. Marking / evaluator configuration",
            {
                "fields": (
                    "default_points",
                    "automatic_marking",
                    "ai_grading_required",
                    "manual_review_allowed",
                    "explanation",
                    "evaluator_notes",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("program", "stimulus")
            .prefetch_related("part_assignments")
        )

    def _effective_audio(self, obj):
        if not obj:
            return None, ""
        if obj.prompt_audio:
            return obj.prompt_audio, "Question-specific Admin audio"
        if obj.stimulus and obj.stimulus.audio_file:
            return obj.stimulus.audio_file, "Shared Stimulus audio"
        return None, ""

    @admin.display(description="Delivery")
    def delivery_status(self, obj):
        if obj.skill == Question.Skill.SPEAKING:
            if obj.prompt_audio:
                return format_html(
                    '<span style="color:#067647;font-weight:700">✓ Admin voice</span>'
                )
            if obj.stimulus and obj.stimulus.audio_file:
                return format_html(
                    '<span style="color:#175cd3;font-weight:700">✓ Shared audio</span>'
                )
            return format_html(
                '<span style="color:#b54708;font-weight:700">Browser fallback</span>'
            )

        if obj.skill == Question.Skill.LISTENING:
            if obj.prompt_audio:
                return format_html(
                    '<span style="color:#067647;font-weight:700">✓ Question audio</span>'
                )
            if obj.stimulus and obj.stimulus.audio_file:
                return format_html(
                    '<span style="color:#067647;font-weight:700">✓ Listening track</span>'
                )
            return format_html(
                '<span style="color:#b42318;font-weight:700">⚠ Audio missing</span>'
            )

        if obj.skill == Question.Skill.READING:
            return format_html(
                '<span style="color:#175cd3;font-weight:700">Reading content</span>'
            )

        if obj.skill == Question.Skill.WRITING:
            return format_html(
                '<span style="color:#6941c6;font-weight:700">Writing task</span>'
            )

        return "Configured"

    @admin.display(description="Effective audio preview")
    def effective_audio_preview(self, obj):
        audio, label = self._effective_audio(obj)

        if audio:
            return format_html(
                '<div style="max-width:600px">'
                '<div style="font-size:12px;color:#475467;margin-bottom:6px">{}</div>'
                '<audio controls preload="metadata" style="width:100%">'
                '<source src="{}"></audio></div>',
                label,
                audio.url,
            )

        if obj and obj.skill == Question.Skill.SPEAKING:
            return format_html(
                '<span style="color:#b54708;font-weight:700">'
                'No upload: existing browser English voice fallback remains active.</span>'
            )

        if obj and obj.skill == Question.Skill.LISTENING:
            return format_html(
                '<span style="color:#b42318;font-weight:700">'
                'No Listening audio configured.</span>'
            )

        return "No audio required."

    @admin.display(description="Audio priority")
    def audio_behavior(self, obj):
        if not obj:
            return "Save the question first."

        if obj.prompt_audio:
            return format_html(
                '<div style="max-width:760px;padding:10px 12px;border-radius:8px;'
                'background:#ecfdf3;color:#05603a">'
                '<strong>Question-specific audio is active.</strong> '
                'It overrides any shared Stimulus audio.</div>'
            )

        if obj.stimulus and obj.stimulus.audio_file:
            return format_html(
                '<div style="max-width:760px;padding:10px 12px;border-radius:8px;'
                'background:#eff8ff;color:#1849a9">'
                '<strong>Shared Stimulus audio is active.</strong> '
                'Upload question audio above whenever this item needs its own recording.</div>'
            )

        if obj.skill == Question.Skill.SPEAKING:
            return format_html(
                '<div style="max-width:760px;padding:10px 12px;border-radius:8px;'
                'background:#fffaeb;color:#93370d">'
                '<strong>Fallback voice is active.</strong> '
                'The current browser voice is preserved until Admin uploads real audio.</div>'
            )

        if obj.skill == Question.Skill.LISTENING:
            return format_html(
                '<div style="max-width:760px;padding:10px 12px;border-radius:8px;'
                'background:#fef3f2;color:#912018">'
                '<strong>Action required:</strong> upload question audio or link a '
                'Stimulus containing the Listening track.</div>'
            )

        return "Audio is not required for this skill."

    @admin.display(description="Effective image preview")
    def effective_image_preview(self, obj):
        if not obj:
            return "Save the question first."

        image = obj.prompt_image
        if not image and obj.stimulus:
            image = obj.stimulus.image_file

        if not image:
            return format_html(
                '<span style="color:#667085">No question/shared image uploaded.</span>'
            )

        return format_html(
            '<img src="{}" alt="" style="max-width:380px;max-height:240px;'
            'object-fit:contain;border:1px solid #d0d5dd;border-radius:12px;'
            'background:#fff;padding:6px">',
            image.url,
        )

    @admin.display(description="Used in")
    def placement_count(self, obj):
        return obj.part_assignments.count()


@admin.register(PartQuestion)
class PartQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "part",
        "question",
        "question_skill",
        "audio_source",
        "order",
        "points_override",
        "is_required",
    )
    list_filter = (
        "part__section__mock_test__program",
        "part__section__mock_test__delivery_mode",
        "part__section__skill",
        "question__program",
        "is_required",
    )
    search_fields = (
        "question__title",
        "question__prompt_text",
        "part__title",
        "part__section__title",
        "part__section__mock_test__title",
    )
    autocomplete_fields = ("part", "question")
    list_select_related = (
        "part",
        "part__section",
        "part__section__mock_test",
        "question",
        "question__stimulus",
    )
    list_per_page = 50

    @admin.display(description="Skill")
    def question_skill(self, obj):
        return obj.question.get_skill_display()

    @admin.display(description="Audio")
    def audio_source(self, obj):
        q = obj.question
        if q.prompt_audio:
            return "Question audio"
        if q.stimulus and q.stimulus.audio_file:
            return "Stimulus audio"
        if q.skill == Question.Skill.SPEAKING:
            return "Browser fallback"
        if q.skill == Question.Skill.LISTENING:
            return "Missing"
        return "—"


admin.site.register(QuestionOption)
admin.site.register(AcceptableAnswer)
admin.site.register(OrderingItem)

# B1_READY_QUESTION_ADD_INTEGRATION_V34_2_3
#
# IMPORTANT:
# This code intentionally lives at the END of the module that defines
# the registered QuestionAdmin. At this point Django has already
# registered the Question admin instance, avoiding the startup-order
# problem that caused V34.2.2 to fail verification.
#
# Normal Add Question -> simple Cambridge Listening builder.
# ?advanced=1        -> original advanced Question form.
import types as _b1_v3423_types
from django.apps import apps as _b1_v3423_apps
from django.contrib import admin as _b1_v3423_admin
from core import admin_listening_sets_v34_2 as _b1_v3423_builder

_b1_v3423_question = _b1_v3423_apps.get_model("question_bank", "Question")
_b1_v3423_question_admin = _b1_v3423_admin.site._registry.get(
    _b1_v3423_question
)

if _b1_v3423_question_admin is None:
    raise RuntimeError(
        "B1 V34.2.3: QuestionAdmin is still not registered at the end "
        "of its source module."
    )

if not getattr(
    _b1_v3423_question_admin,
    "_b1_simple_listening_add_v3423",
    False,
):
    _b1_v3423_original_add = _b1_v3423_question_admin.add_view

    def _b1_v3423_add_view(
        self,
        request,
        form_url="",
        extra_context=None,
    ):
        # Explicit technical fallback to the original advanced form.
        if request.GET.get("advanced") == "1":
            return self._b1_original_add_view_v3423(
                request,
                form_url=form_url,
                extra_context=extra_context,
            )

        # The requested normal workflow.
        return _b1_v3423_builder.listening_set_builder(request)

    _b1_v3423_question_admin._b1_original_add_view_v3423 = (
        _b1_v3423_original_add
    )

    _b1_v3423_question_admin.add_view = _b1_v3423_types.MethodType(
        _b1_v3423_add_view,
        _b1_v3423_question_admin,
    )

    _b1_v3423_question_admin._b1_simple_listening_add_v3423 = True

# /B1_READY_QUESTION_ADD_INTEGRATION_V34_2_3

# B1_READY_QUESTION_HUB_V34_3
import types as _b1qh_types
from django.apps import apps as _b1qh_apps
from django.contrib import admin as _b1qh_admin
from django.urls import reverse as _b1qh_reverse

_b1qh_Q=_b1qh_apps.get_model("question_bank","Question")
_b1qh_qa=_b1qh_admin.site._registry.get(_b1qh_Q)

if _b1qh_qa is None:
    raise RuntimeError("QuestionAdmin not registered")

if not getattr(_b1qh_qa,"_b1_question_hub_v343",False):
    _b1qh_qa._b1_orig_changelist_v343=_b1qh_qa.changelist_view
    _b1qh_qa._b1_orig_queryset_v343=_b1qh_qa.get_queryset
    _b1qh_qa.change_list_template="admin/question_bank/question/change_list_hub_v34_3.html"

    def _b1qh_value(name):
        field=_b1qh_Q._meta.get_field("skill")
        for value,label in list(getattr(field,"choices",()) or ()):
            hay=f"{value} {label}".lower().replace("_"," ").replace("-"," ")
            if name in hay:
                return value
        return name

    def _b1qh_queryset(self,request):
        qs=self._b1_orig_queryset_v343(request)
        forced=getattr(request,"_b1qh_skill_v343",None)
        if forced is not None:
            qs=qs.filter(skill=forced)
        return qs

    def _b1qh_changelist(self,request,extra_context=None):
        panel=(request.GET.get("panel") or "").strip().lower()

        defs=(
            ("listening","Listening","Audio tracks, Part/Set questions and answer keys."),
            ("reading","Reading","Reading passages, prompts and comprehension questions."),
            ("speaking","Speaking","Speaking prompts, recording tasks and responses."),
            ("writing","Writing","Writing prompts, source material and response tasks."),
        )

        values={slug:_b1qh_value(slug) for slug,_,_ in defs}
        base=self._b1_orig_queryset_v343(request)
        root=_b1qh_reverse("admin:question_bank_question_changelist")

        cards=[
            {
                "slug":slug,
                "label":label,
                "description":desc,
                "count":base.filter(skill=values[slug]).count(),
                "url":f"{root}?panel={slug}",
            }
            for slug,label,desc in defs
        ]

        cleaned=request.GET.copy()
        cleaned.pop("panel",None)
        request.GET=cleaned

        ctx=dict(extra_context or {})
        ctx["b1_question_cards"]=cards

        if panel in values:
            request._b1qh_skill_v343=values[panel]
            label=next(label for slug,label,_ in defs if slug==panel)
            ctx.update({
                "b1_question_hub":False,
                "b1_active_slug":panel,
                "b1_active_skill":label,
            })
        else:
            ctx.update({
                "b1_question_hub":True,
                "b1_active_slug":"",
                "b1_active_skill":"",
            })

        return self._b1_orig_changelist_v343(request,extra_context=ctx)

    _b1qh_qa.get_queryset=_b1qh_types.MethodType(_b1qh_queryset,_b1qh_qa)
    _b1qh_qa.changelist_view=_b1qh_types.MethodType(_b1qh_changelist,_b1qh_qa)
    _b1qh_qa._b1_question_hub_v343=True

# /B1_READY_QUESTION_HUB_V34_3
