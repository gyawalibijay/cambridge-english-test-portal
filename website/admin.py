from django.contrib import admin

from .models import PublicInquiry, PublicProgramLanding, PublicSiteSettings


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


@admin.register(PublicSiteSettings)
class PublicSiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Brand",
            {
                "fields": (
                    "site_name",
                    "brand_tagline",
                    "logo",
                    "mascot_image",
                    "mascot_alt_text",
                    "show_mascot",
                )
            },
        ),
        (
            "Home hero",
            {
                "fields": (
                    "announcement_text",
                    "hero_eyebrow",
                    "hero_title",
                    "hero_highlight",
                    "hero_description",
                    "primary_cta_label",
                    "primary_cta_url",
                    "secondary_cta_label",
                    "secondary_cta_url",
                    "trust_note",
                )
            },
        ),
        (
            "Student support",
            {
                "fields": (
                    "whatsapp_number",
                    "whatsapp_label",
                    "whatsapp_message",
                    "footer_text",
                )
            },
        ),
        (
            "Search engine optimisation",
            {
                "fields": (
                    "seo_title",
                    "seo_description",
                    "seo_keywords",
                )
            },
        ),
        ("Updated", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not PublicSiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PublicProgramLanding)
class PublicProgramLandingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "program_key",
        "status_label",
        "is_active",
        "sort_order",
        "updated_at",
    )
    list_editable = ("status_label", "is_active", "sort_order")
    list_filter = ("is_active", "status_tone")
    search_fields = (
        "name",
        "card_title",
        "card_summary",
        "hero_title",
        "hero_description",
        "seo_keywords",
    )
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "Program card",
            {
                "fields": (
                    "program_key",
                    "name",
                    "short_label",
                    "card_kicker",
                    "card_title",
                    "card_summary",
                    "card_image",
                    "card_image_alt",
                    "cursor_label",
                    "status_label",
                    "status_tone",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            "Landing-page hero",
            {
                "fields": (
                    "hero_eyebrow",
                    "hero_title",
                    "hero_description",
                    "hero_image",
                    "hero_image_alt",
                )
            },
        ),
        (
            "Focused information",
            {
                "fields": (
                    "audience_title",
                    "audience_text",
                    "format_title",
                    "format_text",
                    "benefit_one_title",
                    "benefit_one_text",
                    "benefit_two_title",
                    "benefit_two_text",
                    "benefit_three_title",
                    "benefit_three_text",
                )
            },
        ),
        (
            "Calls to action",
            {
                "fields": (
                    "primary_cta_label",
                    "primary_cta_url",
                    "secondary_cta_label",
                    "secondary_cta_url",
                )
            },
        ),
        (
            "Search engine optimisation",
            {"fields": ("seo_title", "seo_description", "seo_keywords")},
        ),
        ("Updated", {"fields": ("updated_at",)}),
    )
