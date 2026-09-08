from django import template

register = template.Library()


@register.simple_tag
def portal_nav_active(request, section):
    path = getattr(request, "path", "") or ""

    rules = {
        "dashboard": ("/dashboard/",),
        "practice": ("/practice/", "/attempt/"),
        "courses": ("/courses/",),
        "store": ("/store/",),
        "results": ("/results/",),
        "profile": ("/profile/",),
        "management": ("/management/", "/evaluation/"),
    }

    prefixes = rules.get(section, ())

    return "active" if any(
        path.startswith(prefix)
        for prefix in prefixes
    ) else ""


@register.simple_tag
def portal_user_initial(user):
    first = (getattr(user, "first_name", "") or "").strip()

    if first:
        return first[:1].upper()

    username = (getattr(user, "username", "") or "").strip()

    return username[:1].upper() if username else "U"


@register.simple_tag
def portal_profile_photo(user):
    try:
        profile = user.student_profile
        if profile.profile_photo:
            return profile.profile_photo.url
    except Exception:
        pass
    return ""
