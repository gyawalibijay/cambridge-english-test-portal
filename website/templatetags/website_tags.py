from urllib.parse import quote

from django import template
from django.db import OperationalError, ProgrammingError

from website.models import PublicProgramLanding, PublicSiteSettings


register = template.Library()


@register.simple_tag
def public_site_settings():
    try:
        return PublicSiteSettings.load()
    except (OperationalError, ProgrammingError):
        return None


@register.simple_tag
def public_program_links():
    try:
        return PublicProgramLanding.objects.filter(is_active=True).order_by(
            "sort_order", "name"
        )
    except (OperationalError, ProgrammingError):
        return []


@register.filter
def whatsapp_url(settings_obj):
    if not settings_obj or not settings_obj.whatsapp_number:
        return ""
    number = "".join(ch for ch in settings_obj.whatsapp_number if ch.isdigit())
    if not number:
        return ""
    return f"https://wa.me/{number}?text={quote(settings_obj.whatsapp_message)}"
