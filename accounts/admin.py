from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    fieldsets = UserAdmin.fieldsets + (
        (
            "Portal Role",
            {
                "fields": ("role",),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Portal Role",
            {
                "fields": ("role",),
            },
        ),
    )

# Student profile management for certificate-ready student data.
try:
    from django.contrib import admin
    from .models import StudentProfile

    if not admin.site.is_registered(StudentProfile):

        @admin.register(StudentProfile)
        class StudentProfileAdmin(admin.ModelAdmin):
            list_display = (
                "user",
                "certificate_name",
                "phone_number",
                "country",
                "preferred_language",
                "email_notifications",
                "result_notifications",
                "updated_at",
            )
            search_fields = (
                "user__username",
                "user__email",
                "user__first_name",
                "user__last_name",
                "certificate_name",
                "phone_number",
            )
            list_filter = (
                "preferred_language",
                "email_notifications",
                "result_notifications",
                "country",
            )
            readonly_fields = (
                "created_at",
                "updated_at",
            )
except Exception:
    pass

# B1_READY_ADMIN_MEDIA_BOOTSTRAP_V33_3_2
try:
    from core import admin_media  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception("Could not initialize B1 Ready admin media center")
# /B1_READY_ADMIN_MEDIA_BOOTSTRAP_V33_3_2

# B1_READY_ADMIN_CONTENT_UX_V33_6
try:
    from core import admin_content_ux_v33_6  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception("Could not initialize B1 Ready Content Studio UX")
# /B1_READY_ADMIN_CONTENT_UX_V33_6

# B1_READY_ADMIN_OPERATIONS_V33_7_1
try:
    from core import admin_operations_v33_7_1  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception("Could not initialize B1 Ready Operations Center")
# /B1_READY_ADMIN_OPERATIONS_V33_7_1

# B1_READY_ADMIN_CRUD_V33_8_1
try:
    from core import admin_crud_ux_v33_8_1  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception("Could not initialize B1 Ready Admin CRUD V33.8")
# /B1_READY_ADMIN_CRUD_V33_8_1

# B1_READY_ADMIN_CAMBRIDGE_WORKSPACE_V33_9_1
try:
    from core import admin_cambridge_focus_v33_9_1  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception(
        "Could not initialize Cambridge Question Workspace V33.9"
    )
# /B1_READY_ADMIN_CAMBRIDGE_WORKSPACE_V33_9_1

# B1_READY_PRICING_OFFER_ADMIN_V34_1
try:
    from core import admin_pricing_offer_v34_1  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception(
        "Could not initialize Pricing Offer Control V34.1"
    )
# /B1_READY_PRICING_OFFER_ADMIN_V34_1

# B1_READY_LISTENING_SET_BUILDER_V34_2
try:
    from core import admin_listening_sets_v34_2  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception('Could not initialize B1 Listening Set Builder V34.2')
# /B1_READY_LISTENING_SET_BUILDER_V34_2


# B1_READY_READING_SET_BUILDER_V36
try:
    from core import admin_reading_sets_v36  # noqa: F401
except Exception:
    import logging
    logging.getLogger(__name__).exception("Could not initialize B1 Reading Set Builder V36")
# /B1_READY_READING_SET_BUILDER_V36

# B1_SPEAKING_SETS_V38_5_ADMIN_HOOK
try:
    import core.admin_speaking_sets_v38  # noqa: F401
except Exception:
    pass

# B1_WRITING_SETS_V39_ADMIN_HOOK
try:
    import core.admin_writing_sets_v39  # noqa: F401
except Exception:
    pass

