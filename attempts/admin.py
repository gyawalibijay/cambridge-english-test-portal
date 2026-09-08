from django.contrib import admin

from .models import AttemptQuestion, StudentResponse, TestAttempt


class AttemptQuestionInline(admin.TabularInline):
    model = AttemptQuestion
    extra = 0
    readonly_fields = ("part", "question", "order", "points", "created_at")
    can_delete = False


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "mock_test",
        "status",
        "started_at",
        "completed_at",
        "overall_score",
        "max_score",
    )
    list_filter = ("status", "mock_test__program", "mock_test")
    search_fields = ("user__username", "user__email", "mock_test__title")
    inlines = [AttemptQuestionInline]


@admin.register(AttemptQuestion)
class AttemptQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "part", "question", "order", "points")
    list_filter = ("part__section__skill", "part__section__mock_test")
    search_fields = ("question__title", "attempt__user__username")


@admin.register(StudentResponse)
class StudentResponseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt_question",
        "review_status",
        "final_score",
        "reviewer",
        "created_at",
    )
    list_filter = ("review_status", "attempt_question__question__skill")
    search_fields = (
        "attempt_question__attempt__user__username",
        "attempt_question__question__title",
    )
