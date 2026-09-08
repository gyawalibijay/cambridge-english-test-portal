from django.contrib import admin

from .models import PublicInquiry


@admin.register(PublicInquiry)
class PublicInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "program_interest",
        "subject",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "program_interest",
        "created_at",
    )
    search_fields = (
        "name",
        "email",
        "phone",
        "subject",
        "message",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
