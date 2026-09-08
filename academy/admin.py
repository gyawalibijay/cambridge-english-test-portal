from django.contrib import admin

from .models import Course, CourseMaterial, TestMaterial


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program",
        "created_by",
        "is_published",
        "sort_order",
    )
    list_filter = (
        "program",
        "is_published",
    )
    search_fields = (
        "title",
        "program__name",
    )
    prepopulated_fields = {
        "slug": ("title",)
    }


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "skill",
        "material_type",
        "is_published",
    )
    list_filter = (
        "skill",
        "material_type",
        "is_published",
    )
    search_fields = (
        "title",
        "course__title",
    )


@admin.register(TestMaterial)
class TestMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program",
        "skill",
        "course",
        "is_published",
        "is_question_bank_ready",
    )
    list_filter = (
        "program",
        "skill",
        "is_published",
        "is_question_bank_ready",
    )
    search_fields = (
        "title",
        "program__name",
        "course__title",
    )
