from django.http import Http404, HttpResponse
from django.shortcuts import render

from assessments.models import MockTest, Program
from commerce.models import AccessPackage

from .models import PublicProgramLanding, PublicSiteSettings

try:
    from academy.models import Course
except Exception:
    Course = None


PROGRAM_PRESENTATION = {
    "cambridge-general": {
        "eyebrow": "Cambridge / General English",
        "title": "Cambridge-style four-skill practice",
        "short_title": "Cambridge",
        "summary": (
            "Structured Speaking, Listening, Reading and Writing practice "
            "with timed parts, recordings, objective marking and results."
        ),
        "badge": "4 skills",
        "icon": "C",
        "features": [
            "5-part Speaking flow",
            "5-part Listening practice",
            "5-part Reading practice",
            "2-part Writing practice",
            "Recorded Speaking replay",
            "Practice result history",
        ],
    },
    "ielts-academic": {
        "eyebrow": "IELTS Academic",
        "title": "IELTS Academic preparation workspace",
        "short_title": "IELTS Academic",
        "summary": (
            "A dedicated Academic practice mode for candidates preparing "
            "for university and higher-education English requirements."
        ),
        "badge": "Academic",
        "icon": "IA",
        "features": [
            "Listening practice",
            "Academic Reading",
            "Academic Writing",
            "Speaking practice",
            "Progress history",
            "Admin-managed course library",
        ],
    },
    "ielts-general": {
        "eyebrow": "IELTS General Training",
        "title": "IELTS General Training practice",
        "short_title": "IELTS General",
        "summary": (
            "A General Training practice mode with separate program content "
            "while sharing the same student account and result history."
        ),
        "badge": "General",
        "icon": "IG",
        "features": [
            "Listening practice",
            "General Reading",
            "General Writing",
            "Speaking practice",
            "Progress history",
            "Admin-managed course library",
        ],
    },
    "ukvi-interview": {
        "eyebrow": "UK Student / UKVI",
        "title": "UK student interview practice",
        "short_title": "UKVI Interview",
        "summary": (
            "Interview-focused preparation for students who want structured "
            "practice, recorded responses and readiness-oriented feedback."
        ),
        "badge": "Interview",
        "icon": "UK",
        "features": [
            "Interview question practice",
            "Recorded responses",
            "Replay before submission",
            "Practice feedback",
            "Result history",
            "Course resources",
        ],
    },
}


def _program_cards():
    programs = {
        p.code: p
        for p in Program.objects.filter(
            is_active=True
        ).order_by("sort_order", "name")
    }

    cards = []

    for code, presentation in PROGRAM_PRESENTATION.items():
        program = programs.get(code)

        if not program:
            continue

        test_count = MockTest.objects.filter(
            program=program,
            is_published=True,
        ).count()

        course_count = 0

        if Course is not None:
            try:
                course_count = Course.objects.filter(
                    program=program,
                    is_published=True,
                ).count()
            except Exception:
                course_count = 0

        cards.append({
            "program": program,
            "presentation": presentation,
            "test_count": test_count,
            "course_count": course_count,
        })

    return cards


def home(request):
    return render(
        request,
        "website/home.html",
        {
            "site_settings": PublicSiteSettings.load(),
            "landing_programs": PublicProgramLanding.objects.filter(
                is_active=True
            ).order_by("sort_order", "name"),
        },
    )


def public_program_landing(request, program_key):
    landing = (
        PublicProgramLanding.objects
        .filter(program_key=program_key, is_active=True)
        .first()
    )
    if landing is None:
        raise Http404("Program page not found.")

    return render(
        request,
        "website/program_landing.html",
        {
            "site_settings": PublicSiteSettings.load(),
            "landing": landing,
        },
    )


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: " + sitemap_url + "\n"
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(request):
    urls = [
        (request.build_absolute_uri("/"), "1.0", "daily"),
        (request.build_absolute_uri("/cambridge-english/"), "0.9", "weekly"),
        (request.build_absolute_uri("/ielts/"), "0.9", "weekly"),
        (request.build_absolute_uri("/uk-interview/"), "0.9", "weekly"),
        (request.build_absolute_uri("/contact/"), "0.6", "monthly"),
    ]
    items = "".join(
        "<url><loc>{}</loc><changefreq>{}</changefreq><priority>{}</priority></url>".format(
            location.replace("&", "&amp;"), frequency, priority
        )
        for location, priority, frequency in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + items
        + "</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml")


def programs(request):
    return render(
        request,
        "website/programs.html",
        {
            "program_cards": _program_cards(),
        },
    )


def program_detail(request, code):
    presentation = PROGRAM_PRESENTATION.get(code)

    if not presentation:
        raise Http404("Program not found.")

    program = (
        Program.objects
        .filter(
            code=code,
            is_active=True,
        )
        .first()
    )

    if not program:
        raise Http404("Program not found.")

    packages = (
        AccessPackage.objects
        .filter(
            is_active=True,
            programs=program,
        )
        .distinct()
    )

    tests = (
        MockTest.objects
        .filter(
            program=program,
            is_published=True,
        )
        .order_by("title")
    )

    courses = []

    if Course is not None:
        try:
            courses = list(
                Course.objects
                .filter(
                    program=program,
                    is_published=True,
                )
                .order_by("sort_order", "title")[:8]
            )
        except Exception:
            courses = []

    return render(
        request,
        "website/program_detail.html",
        {
            "program": program,
            "presentation": presentation,
            "packages": packages,
            "tests": tests,
            "courses": courses,
        },
    )


def features(request):
    return render(
        request,
        "website/features.html",
        {
            "program_cards": _program_cards(),
        },
    )


def pricing(request):
    packages = (
        AccessPackage.objects
        .filter(is_active=True)
        .prefetch_related("programs")
        .order_by("sort_order", "title")
    )

    return render(
        request,
        "website/pricing.html",
        {
            "packages": packages,
        },
    )

# CAMBRIDGE_LAUNCH_PRICING_V14_10
def pricing(request):
    # Cambridge-first public pricing page. Older pricing code above remains
    # untouched for rollback/history; this final definition becomes active.
    from django.shortcuts import render as django_render
    from commerce.models import AccessPackage
    from website.models import PublicSiteSettings

    def package_for(codes):
        return (
            AccessPackage.objects
            .filter(programs__code__in=codes)
            .prefetch_related("programs")
            .distinct()
            .order_by("sort_order", "title")
            .first()
        )

    pricing_cards = [
        {
            "key": "cambridge",
            "title": "Cambridge Test Preparation",
            "eyebrow": "CAMBRIDGE / GENERAL ENGLISH",
            "summary": "Practice, mock tests and learning materials for Cambridge-style English preparation.",
            "package": package_for(["cambridge-general"]),
            "enabled": True,
        },
        {
            "key": "ielts",
            "title": "IELTS Preparation",
            "eyebrow": "ACADEMIC & GENERAL",
            "summary": "IELTS Academic and General Training preparation is currently in development.",
            "package": package_for(["ielts-academic", "ielts-general"]),
            "enabled": False,
        },
        {
            "key": "ukvi",
            "title": "UKVI Interview Preparation",
            "eyebrow": "UK STUDENT / UKVI",
            "summary": "UK student and credibility interview preparation is currently in development.",
            "package": package_for(["ukvi-interview"]),
            "enabled": False,
        },
    ]

    return django_render(
        request,
        "website/pricing.html",
        {
            "site_settings": PublicSiteSettings.load(),
            "pricing_cards": pricing_cards,
        },
    )
