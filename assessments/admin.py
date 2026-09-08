from django.contrib import admin
from django.utils.html import format_html

from .models import MockTest, Program, TestPart, TestSection


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name", "code", "description")


class TestPartInline(admin.TabularInline):
    model = TestPart
    extra = 0
    show_change_link = True
    fields = (
        "title",
        "order",
        "prompt_mode",
        "preparation_seconds",
        "response_seconds",
        "question_visible",
        "recording_required",
        "is_active",
    )


@admin.register(TestSection)
class TestSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "skill",
        "order",
        "duration_seconds",
        "part_count",
    )
    list_filter = ("skill", "mock_test__program", "mock_test__delivery_mode")
    search_fields = ("title", "mock_test__title", "instructions")
    inlines = [TestPartInline]

    @admin.display(description="Parts")
    def part_count(self, obj):
        return obj.parts.count()


class TestSectionInline(admin.TabularInline):
    model = TestSection
    extra = 0
    show_change_link = True
    fields = ("title", "skill", "order", "duration_seconds", "is_required")


@admin.action(description="Publish selected tests")
def publish_tests(modeladmin, request, queryset):
    queryset.update(is_published=True)


@admin.action(description="Unpublish selected tests")
def unpublish_tests(modeladmin, request, queryset):
    queryset.update(is_published=False)


@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program",
        "delivery_mode",
        "duration_minutes",
        "content_status",
        "is_published",
        "updated_at",
    )
    list_filter = ("program", "delivery_mode", "is_published")
    search_fields = ("title", "description", "instructions", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TestSectionInline]
    actions = [publish_tests, unpublish_tests]
    fieldsets = (
        ("Test identity", {"fields": ("program", "title", "slug", "delivery_mode", "is_published")}),
        ("Student instructions", {"fields": ("description", "instructions", "duration_minutes")}),
        ("Ownership", {"fields": ("created_by",), "classes": ("collapse",)}),
    )

    @admin.display(description="Content")
    def content_status(self, obj):
        sections = list(obj.sections.prefetch_related("parts__question_assignments"))
        if not sections:
            return format_html('<span style="color:#b42318;font-weight:700">No sections</span>')
        parts = [part for section in sections for part in section.parts.all() if part.is_active]
        if not parts:
            return format_html('<span style="color:#b42318;font-weight:700">No active parts</span>')
        missing = sum(1 for part in parts if not part.question_assignments.exists())
        if missing:
            return format_html(
                '<span style="color:#b54708;font-weight:700">{} part(s) need questions</span>',
                missing,
            )
        return format_html('<span style="color:#067647;font-weight:700">Ready</span>')


try:
    from question_bank.models import PartQuestion

    class PartQuestionInline(admin.TabularInline):
        model = PartQuestion
        extra = 0
        autocomplete_fields = ("question",)
        fields = ("order", "question", "points_override", "is_required")
        verbose_name = "Question in this part"
        verbose_name_plural = "Questions in this part — editing the Question changes its text/audio wherever it is reused"

except Exception:  # pragma: no cover - admin remains usable during partial migrations
    PartQuestionInline = None


@admin.register(TestPart)
class TestPartAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "section",
        "order",
        "preparation_seconds",
        "response_seconds",
        "question_visible",
        "recording_required",
        "question_total",
        "is_active",
    )
    list_filter = (
        "section__mock_test__program",
        "section__mock_test__delivery_mode",
        "section__skill",
        "question_visible",
        "recording_required",
        "is_active",
    )
    search_fields = ("title", "section__title", "section__mock_test__title", "instructions")
    fieldsets = (
        ("Part", {"fields": ("section", "title", "order", "instructions", "is_active")}),
        (
            "Prompt & timing",
            {
                "fields": (
                    "prompt_mode",
                    "question_visible",
                    "preparation_seconds",
                    "response_seconds",
                    "minimum_response_seconds",
                    "max_audio_plays",
                    "recording_required",
                )
            },
        ),
        ("Question limits", {"fields": ("question_count", "min_word_count"), "classes": ("collapse",)}),
    )
    if PartQuestionInline is not None:
        inlines = [PartQuestionInline]

    @admin.display(description="Questions")
    def question_total(self, obj):
        try:
            return obj.question_assignments.count()
        except Exception:
            return 0

# B1_MOCK_BUILDER_PART1_V35_0
from . import mock_builder_v35_part1  # noqa: F401,E402
# /B1_MOCK_BUILDER_PART1_V35_0
