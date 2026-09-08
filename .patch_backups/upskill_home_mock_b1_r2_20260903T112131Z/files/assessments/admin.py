from django.contrib import admin

from .models import Program, MockTest, TestSection, TestPart


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "sort_order",
    )

    list_editable = (
        "is_active",
        "sort_order",
    )

    search_fields = (
        "name",
        "code",
    )


class TestPartInline(admin.TabularInline):
    model = TestPart
    extra = 0


@admin.register(TestSection)
class TestSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "skill",
        "order",
        "duration_seconds",
    )

    list_filter = (
        "skill",
        "mock_test__program",
    )

    search_fields = (
        "title",
        "mock_test__title",
    )

    inlines = [
        TestPartInline,
    ]


class TestSectionInline(admin.TabularInline):
    model = TestSection
    extra = 0
    show_change_link = True


@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program",
        "duration_minutes",
        "is_published",
        "created_at",
    )

    list_filter = (
        "program",
        "is_published",
    )

    search_fields = (
        "title",
        "description",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    inlines = [
        TestSectionInline,
    ]


@admin.register(TestPart)
class TestPartAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "section",
        "order",
        "preparation_seconds",
        "response_seconds",
        "minimum_response_seconds",
        "question_visible",
        "recording_required",
    )

    list_filter = (
        "section__skill",
        "question_visible",
        "recording_required",
    )

    search_fields = (
        "title",
        "section__title",
        "section__mock_test__title",
    )
