from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.utils import timezone


SKILLS = ("reading", "writing", "listening", "speaking")
SKILL_LABELS = {
    "reading": "Reading",
    "writing": "Writing",
    "listening": "Listening",
    "speaking": "Speaking",
}
SKILL_TARGETS = {
    "reading": 240,
    "writing": 80,
    "listening": 250,
    "speaking": 70,
}
SKILL_RECOMMENDATIONS = {
    "reading": "B1 Reading - Matching Headings",
    "writing": "B1 Writing - Formal Email Accuracy",
    "listening": "B1 Listening - Part 4 Short Recordings",
    "speaking": "B1 Speaking - Describing Pictures",
}

# These descriptors follow the user's uploaded Test Report wording.
CEFR_DESCRIPTORS = {
    "speaking": {
        "B1": "Can speak with colleagues or clients within own job area about simple matters.",
        "A2": "Can produce a short series of simple phrases and sentences on familiar topics.",
        "A1": "Can produce simple, mainly isolated phrases, on very familiar topics.",
    },
    "listening": {
        "B1": "Can understand the general meaning of short, non-routine messages and longer articles within their work context.",
        "A2": "Can understand short work-related documentation and messages within their area of expertise.",
        "A1": "Can understand very short work-related messages if the language is simple and the topic is familiar.",
    },
    "reading": {
        "B1": "Can understand the main ideas of clear speech on familiar topics found in the workplace.",
        "A2": "Can understand the main points of short, clear speech.",
        "A1": "Can recognise familiar words and very basic phases from slow, clear speech.",
    },
    "writing": {
        "B1": "Can write straightforward messages to colleagues, customers, or contacts at other companies on a range of familiar subjects.",
        "A2": "Can write simple messages to colleagues or known contacts at other companies.",
        "A1": "Can write short, simple routine requests to colleagues.",
    },
}


def _get_model(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


def _model_has_field(model, field_name: str) -> bool:
    if model is None:
        return False
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _safe_attr(obj: Any, names, default=None):
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if value not in (None, ""):
            return value
    return default


def _pct_from_score(score, max_score=None):
    try:
        score = float(score)
    except Exception:
        return None

    if max_score not in (None, ""):
        try:
            max_score = float(max_score)
        except Exception:
            max_score = None

    if max_score and max_score > 0:
        # Some old records stored a percentage directly in score while points=1.
        if 0 <= score <= 100 and score > max_score * 1.5:
            pct = score
        else:
            pct = (score / max_score) * 100.0
    else:
        pct = score

    return round(max(0.0, min(100.0, pct)), 1)


def _response_pct(response):
    score = None
    for field in ("final_score", "evaluator_score", "ai_score", "auto_score"):
        value = getattr(response, field, None)
        if value is not None:
            score = value
            break

    attempt_question = getattr(response, "attempt_question", None)
    points = getattr(attempt_question, "points", None) if attempt_question else None

    pct = _pct_from_score(score, points)
    if pct is not None:
        return pct

    is_correct = getattr(response, "is_correct", None)
    if is_correct is True:
        return 100.0
    if is_correct is False:
        return 0.0
    return None


def _explicit_cefr(response):
    candidates = []

    for field in ("cefr_level", "cefr_estimate", "estimated_cefr"):
        value = getattr(response, field, None)
        if value:
            candidates.append(str(value))

    feedback = getattr(response, "ai_feedback", None)
    if isinstance(feedback, dict):
        for key in ("cefr", "cefr_level", "cefr_estimate", "estimated_cefr"):
            value = feedback.get(key)
            if value:
                candidates.append(str(value))

    for raw in candidates:
        clean = raw.upper().strip()
        for level in ("B1", "A2", "A1"):
            if level in clean:
                return level

    return None


def _student_responses(user):
    StudentResponse = _get_model("attempts", "StudentResponse")
    if StudentResponse is None:
        return []

    try:
        qs = (
            StudentResponse.objects
            .filter(attempt_question__attempt__user=user)
            .select_related(
                "attempt_question",
                "attempt_question__question",
                "attempt_question__attempt",
                "attempt_question__part",
            )
            .order_by("created_at")
        )
        return list(qs)
    except Exception:
        return []


def _skill_for_response(response):
    aq = getattr(response, "attempt_question", None)
    question = getattr(aq, "question", None) if aq else None
    skill = getattr(question, "skill", None)
    return str(skill).lower() if skill else ""


def _skill_stats(user):
    responses = _student_responses(user)
    grouped = defaultdict(list)

    for response in responses:
        skill = _skill_for_response(response)
        if skill in SKILLS:
            grouped[skill].append(response)

    stats = {}

    for skill in SKILLS:
        items = grouped.get(skill, [])
        scored = [p for p in (_response_pct(r) for r in items) if p is not None]
        accuracy = round(sum(scored) / len(scored), 1) if scored else 0.0
        completed = len(items)
        target = SKILL_TARGETS[skill]
        progress = round(min(100.0, (completed / target) * 100.0), 1) if target else 0.0

        explicit_levels = [level for level in (_explicit_cefr(r) for r in items) if level]
        cefr = explicit_levels[-1] if explicit_levels else None

        stats[skill] = {
            "key": skill,
            "label": SKILL_LABELS[skill],
            "completed": completed,
            "target": target,
            "accuracy": accuracy,
            "progress": progress,
            "cefr": cefr,
            "recommended": SKILL_RECOMMENDATIONS[skill],
        }

    return stats


def _attempt_queryset(user):
    TestAttempt = _get_model("attempts", "TestAttempt")
    if TestAttempt is None:
        return []

    try:
        return list(
            TestAttempt.objects
            .filter(user=user)
            .select_related("mock_test")
            .order_by("-started_at")
        )
    except Exception:
        return []


def _attempt_pct(attempt):
    pct = _pct_from_score(
        getattr(attempt, "overall_score", None),
        getattr(attempt, "max_score", None),
    )
    if pct is not None:
        return pct

    StudentResponse = _get_model("attempts", "StudentResponse")
    if StudentResponse is None:
        return None

    try:
        responses = StudentResponse.objects.filter(
            attempt_question__attempt=attempt
        ).select_related("attempt_question")
        values = [p for p in (_response_pct(r) for r in responses) if p is not None]
        if values:
            return round(sum(values) / len(values), 1)
    except Exception:
        pass

    return None


# DASHBOARD_INSIGHTS_20260829
def _day_streak(user):
    """Return the student's real consecutive-day activity and last seven days."""
    from datetime import timedelta

    TestAttempt = _get_model("attempts", "TestAttempt")
    activity_dates = set()

    if TestAttempt is not None:
        try:
            timestamps = TestAttempt.objects.filter(user=user).values_list(
                "started_at", flat=True
            )
            for value in timestamps:
                if value is None:
                    continue
                try:
                    activity_dates.add(timezone.localtime(value).date())
                except Exception:
                    activity_dates.add(value.date())
        except Exception:
            activity_dates = set()

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    cursor = today if today in activity_dates else yesterday if yesterday in activity_dates else None
    count = 0

    while cursor is not None and cursor in activity_dates:
        count += 1
        cursor -= timedelta(days=1)

    days = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        days.append({
            "label": day.strftime("%a")[:1],
            "number": day.day,
            "active": day in activity_dates,
            "today": day == today,
        })

    return {
        "count": count,
        "active_today": today in activity_dates,
        "days": days,
    }


def _top_performers(limit=5):
    """Build a small student leaderboard from completed, scored test attempts."""
    TestAttempt = _get_model("attempts", "TestAttempt")
    if TestAttempt is None:
        return []

    try:
        attempts = list(
            TestAttempt.objects
            .exclude(status__in=("in_progress", "cancelled"))
            .filter(user__is_active=True, user__is_staff=False)
            .select_related("user")
            .order_by("-started_at")[:250]
        )
    except Exception:
        return []

    grouped = {}
    for attempt in attempts:
        score = _attempt_pct(attempt)
        user = getattr(attempt, "user", None)
        if score is None or user is None:
            continue

        row = grouped.setdefault(user.pk, {"user": user, "scores": []})
        row["scores"].append(float(score))

    performers = []
    for row in grouped.values():
        user = row["user"]
        scores = row["scores"]
        name = ""
        try:
            name = user.get_full_name().strip()
        except Exception:
            pass
        name = name or getattr(user, "first_name", "") or getattr(user, "username", "Student")

        words = [part for part in str(name).split() if part]
        initials = "".join(part[0] for part in words[:2]).upper() or "ST"
        performers.append({
            "name": str(name),
            "initials": initials,
            "score": round(sum(scores) / len(scores), 1),
            "attempts": len(scores),
        })

    performers.sort(
        key=lambda item: (-item["score"], -item["attempts"], item["name"].lower())
    )
    output = performers[:limit]
    for index, performer in enumerate(output, start=1):
        performer["rank"] = index
    return output


def _attempt_title(attempt):
    test = getattr(attempt, "mock_test", None)
    return _safe_attr(test, ("title", "name"), "Practice Test")


def _attempt_slug(attempt):
    test = getattr(attempt, "mock_test", None)
    return _safe_attr(test, ("slug",), "")


def _published_tests():
    MockTest = _get_model("assessments", "MockTest")
    if MockTest is None:
        return []

    try:
        qs = MockTest.objects.all()
        if _model_has_field(MockTest, "is_published"):
            qs = qs.filter(is_published=True)
        return list(qs.order_by("title"))
    except Exception:
        return []


def _test_sections(test):
    for rel in ("sections", "testsection_set"):
        manager = getattr(test, rel, None)
        if manager is not None and hasattr(manager, "all"):
            try:
                return list(manager.all().order_by("order"))
            except Exception:
                try:
                    return list(manager.all())
                except Exception:
                    pass
    return []


def _test_skill_start_url(skill):
    for test in _published_tests():
        sections = _test_sections(test)
        if any(str(getattr(section, "skill", "")).lower() == skill for section in sections):
            slug = getattr(test, "slug", "")
            if slug:
                return f"/practice/test/{slug}/"
    return "/practice/cambridge/"


def _featured_mock():
    tests = _published_tests()
    if not tests:
        return None

    for test in tests:
        title = str(getattr(test, "title", "")).lower()
        if "full mock" in title or "full test" in title:
            return test

    return tests[0]


def _materials(limit=12):
    possible = [
        ("academy", "CourseMaterial"),
        ("academy", "Material"),
        ("academy", "TestMaterial"),
    ]

    model = None
    for app_label, model_name in possible:
        model = _get_model(app_label, model_name)
        if model is not None:
            break

    if model is None:
        return []

    try:
        qs = model.objects.all()
        for flag in ("is_published", "is_active", "active"):
            if _model_has_field(model, flag):
                qs = qs.filter(**{flag: True})
                break
        if _model_has_field(model, "created_at"):
            qs = qs.order_by("-created_at")
        items = list(qs[:limit])
    except Exception:
        return []

    output = []

    for item in items:
        title = _safe_attr(item, ("title", "name"), "Learning resource")
        description = _safe_attr(
            item,
            ("description", "summary", "caption"),
            "Open this learning resource from your course library.",
        )
        material_type = str(
            _safe_attr(item, ("material_type", "type", "kind"), "resource")
        ).lower()

        url = _safe_attr(item, ("external_url", "url", "video_url"), "")

        if not url:
            for file_field in ("file", "document", "attachment", "pdf_file", "media_file"):
                f = getattr(item, file_field, None)
                try:
                    if f and f.url:
                        url = f.url
                        break
                except Exception:
                    pass

        output.append({
            "title": str(title),
            "description": str(description),
            "type": material_type,
            "url": url or "/courses/",
        })

    return output


def _profile(user):
    for related in ("studentprofile", "profile"):
        try:
            return getattr(user, related)
        except Exception:
            pass

    StudentProfile = _get_model("accounts", "StudentProfile")
    if StudentProfile is not None:
        try:
            return StudentProfile.objects.filter(user=user).first()
        except Exception:
            pass
    return None


def _profile_photo_path(user):
    profile = _profile(user)
    if profile is None:
        return None

    for field in ("profile_photo", "photo", "image", "avatar"):
        value = getattr(profile, field, None)
        try:
            if value and value.path and Path(value.path).exists():
                return value.path
        except Exception:
            continue
    return None


def _target_level(user):
    profile = _profile(user)
    if profile is not None:
        level = _safe_attr(profile, ("target_level", "cefr_target", "target_cefr"), None)
        if level:
            clean = str(level).upper()
            if clean in {"A1", "A2", "B1"}:
                return clean
    return "B1"


def _base_context(request, active):
    skill_stats = _skill_stats(request.user)
    readiness = round(
        sum(skill_stats[s]["accuracy"] for s in SKILLS) / len(SKILLS),
        1,
    )

    return {
        "active": active,
        "skill_stats": skill_stats,
        "readiness": readiness,
        "target_level": _target_level(request.user),
        "display_name": request.user.first_name or request.user.username,
    }


@login_required
def dashboard(request):
    context = _base_context(request, "home")
    attempts = _attempt_queryset(request.user)
    current = next(
        (a for a in attempts if str(getattr(a, "status", "")).lower() == "in_progress"),
        attempts[0] if attempts else None,
    )

    hour = timezone.localtime().hour
    greeting = "Good morning"
    if hour >= 17:
        greeting = "Good evening"
    elif hour >= 12:
        greeting = "Good afternoon"

    context.update({
        "greeting": greeting,
        "current_attempt": current,
        "current_attempt_title": _attempt_title(current) if current else None,
        "current_attempt_pct": _attempt_pct(current) if current else None,
        "current_attempt_slug": _attempt_slug(current) if current else "",
        "top_performers": _top_performers(limit=8),
    })
    from .dashboard_reference_data import build_reference_dashboard
    context.update(build_reference_dashboard(request.user, _response_pct, _explicit_cefr))
    return render(request, "student_final/dashboard.html", context)


@login_required
def practice_hub(request):
    # PRACTICE_FOCUS_NO_VISIBLE_SETS_20260828
    # The focused Practice screen intentionally has no desktop dashboard shell.
    practice_skills = [
        {"key": "reading", "label": "Reading", "parts": 5},
        {"key": "listening", "label": "Listening", "parts": 5},
        {"key": "speaking", "label": "Speaking", "parts": 5},
        {"key": "writing", "label": "Writing", "parts": 2},
    ]
    return render(
        request,
        "student_final/practice_reference.html",
        {"practice_skills": practice_skills},
    )


@login_required
def mock_tests(request):
    context = _base_context(request, "mock")
    featured = _featured_mock()
    sections = _test_sections(featured) if featured else []
    attempts = _attempt_queryset(request.user)

    history = []
    for attempt in attempts[:8]:
        history.append({
            "attempt": attempt,
            "title": _attempt_title(attempt),
            "score": _attempt_pct(attempt),
            "date": getattr(attempt, "completed_at", None) or getattr(attempt, "started_at", None),
        })

    context.update({
        "featured": featured,
        "featured_sections": sections,
        "test_history": history,
    })
    return render(request, "student_final/mock_tests.html", context)


@login_required
def learn(request):
    context = _base_context(request, "learn")
    context["materials"] = _materials(limit=12)
    return render(request, "student_final/learn.html", context)


@login_required
def progress(request):
    context = _base_context(request, "progress")
    attempts = _attempt_queryset(request.user)
    completed_attempts = [
        a for a in attempts
        if str(getattr(a, "status", "")).lower() in {"completed", "submitted"}
    ]
    response_count = sum(context["skill_stats"][skill]["completed"] for skill in SKILLS)

    context.update({
        "overall_progress": round(
            sum(context["skill_stats"][skill]["progress"] for skill in SKILLS) / len(SKILLS),
            1,
        ),
        "completed_attempts": len(completed_attempts),
        "response_count": response_count,
    })
    return render(request, "student_final/progress.html", context)


@login_required
def certificates(request):
    context = _base_context(request, "certificates")
    attempts = _attempt_queryset(request.user)
    reports = []

    for attempt in attempts:
        status = str(getattr(attempt, "status", "")).lower()
        if status not in {"completed", "submitted"}:
            continue
        reports.append({
            "attempt": attempt,
            "title": _attempt_title(attempt),
            "date": getattr(attempt, "completed_at", None) or getattr(attempt, "started_at", None),
            "score": _attempt_pct(attempt),
        })

    context["reports"] = reports
    return render(request, "student_final/certificates.html", context)


@login_required
def profile_summary(request):
    context = _base_context(request, "profile")
    context["profile"] = _profile(request.user)
    return render(request, "student_final/profile.html", context)


def _report_skill_levels(user, attempt):
    StudentResponse = _get_model("attempts", "StudentResponse")
    levels = {skill: None for skill in SKILLS}

    if StudentResponse is None:
        return levels

    try:
        qs = (
            StudentResponse.objects
            .filter(attempt_question__attempt=attempt)
            .select_related("attempt_question__question")
            .order_by("created_at")
        )
    except Exception:
        return levels

    for response in qs:
        skill = _skill_for_response(response)
        level = _explicit_cefr(response)
        if skill in levels and level:
            levels[skill] = level

    return levels


def _overall_cefr(levels):
    # The uploaded report says an average score is awarded when multiple
    # skills are assessed, but it does not provide a score-to-CEFR conversion.
    # We therefore do not invent one. If all explicit estimates agree, show it;
    # otherwise label the overall level as "Mixed" or "Pending".
    explicit = [level for level in levels.values() if level]
    if not explicit:
        return "Pending"
    if len(set(explicit)) == 1:
        return explicit[0]
    return "Mixed"


@login_required
def practice_report_pdf(request, attempt_id):
    TestAttempt = _get_model("attempts", "TestAttempt")
    if TestAttempt is None:
        raise Http404("Attempt model is unavailable.")

    try:
        attempt = TestAttempt.objects.select_related("mock_test").get(
            pk=attempt_id,
            user=request.user,
        )
    except Exception:
        raise Http404("Practice attempt not found.")

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            Paragraph,
            PageBreak,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception as exc:
        raise Http404(f"PDF engine unavailable: {exc}")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Upskill Practice Test Report",
        author="Surakshya Technologies",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=29,
        textColor=colors.HexColor("#22272B"),
        alignment=TA_LEFT,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SmallMuted",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=11.4,
        textColor=colors.HexColor("#667085"),
    ))
    styles.add(ParagraphStyle(
        name="BodyCompact",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.5,
        textColor=colors.HexColor("#30363B"),
    ))
    styles.add(ParagraphStyle(
        name="SectionHead",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#161B22"),
        spaceAfter=5,
    ))

    teal = colors.HexColor("#16B8B3")
    mint = colors.HexColor("#DDF7F4")
    navy = colors.HexColor("#1721B6")
    grey = colors.HexColor("#F3F4F4")
    line = colors.HexColor("#D9DEDE")

    levels = _report_skill_levels(request.user, attempt)
    overall = _overall_cefr(levels)
    issued = timezone.localtime(
        getattr(attempt, "completed_at", None) or timezone.now()
    ).strftime("%d-%m-%Y")
    candidate_id = f"UP{request.user.pk:05d}{attempt.pk:04d}"
    candidate_name = (
        request.user.get_full_name().strip()
        or request.user.username
    ).upper()

    story = []

    brand = Table([
        [
            Paragraph("<b><font color='#16B8B3' size='28'>Upskill</font></b><br/><font color='#777777' size='10'>Practice by Surakshya Technologies</font>", styles["BodyText"]),
            Table([
                [Paragraph("<b>DATE ISSUED</b>", styles["SmallMuted"]), Paragraph("<b>CANDIDATE ID</b>", styles["SmallMuted"])],
                [Paragraph(issued, styles["BodyCompact"]), Paragraph(candidate_id, styles["BodyCompact"])],
            ], colWidths=[35*mm, 35*mm]),
        ]
    ], colWidths=[105*mm, 70*mm])
    brand.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
    ]))
    story.append(brand)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Practice Test Report", styles["ReportTitle"]))
    story.append(Paragraph(
        "This is an internal practice report generated by Upskill Practice. It is not an official Cambridge English result or certificate.",
        styles["SmallMuted"],
    ))
    story.append(Spacer(1, 5*mm))

    photo_path = _profile_photo_path(request.user)
    photo_cell = ""
    if photo_path:
        try:
            photo_cell = Image(photo_path, width=34*mm, height=42*mm)
        except Exception:
            photo_cell = ""

    candidate_box = Table([
        [Paragraph("Candidate name", styles["SmallMuted"]), photo_cell],
        [Paragraph(f"<b>{candidate_name}</b>", styles["BodyCompact"]), ""],
    ], colWidths=[130*mm, 38*mm], rowHeights=[12*mm, 18*mm])
    candidate_box.setStyle(TableStyle([
        ("BACKGROUND", (0,1), (0,1), mint),
        ("BOX", (0,1), (0,1), 2, teal),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("SPAN", (1,0), (1,1)),
        ("ALIGN", (1,0), (1,1), "CENTER"),
    ]))
    story.append(candidate_box)
    story.append(Spacer(1, 8*mm))

    skill_rows = []
    for first, second in (("reading", "writing"), ("speaking", "listening")):
        cells = []
        for skill in (first, second):
            level = levels.get(skill) or "Pending"
            bar_count = {"A1": 1, "A2": 2, "B1": 3}.get(level, 0)
            bars = "  ".join(["■" for _ in range(bar_count)]) or "-"
            cells.append(Paragraph(
                f"<b>{SKILL_LABELS[skill].upper()}</b><br/><font color='#16B8B3'>{bars}</font><br/><b>{level}</b>",
                styles["BodyCompact"],
            ))
        skill_rows.append(cells)

    summary = Table([
        [
            Table([
                [Paragraph("On the practice CEFR scale", styles["SmallMuted"])],
                [Paragraph(f"<font size='30'><b>{overall}</b></font>", styles["BodyCompact"])],
            ], colWidths=[45*mm], rowHeights=[10*mm, 28*mm]),
            Table(skill_rows, colWidths=[53*mm, 53*mm], rowHeights=[28*mm, 28*mm]),
        ]
    ], colWidths=[48*mm, 112*mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), mint),
        ("BOX", (0,0), (0,0), 2, teal),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (0,0), "CENTER"),
    ]))
    story.append(summary)
    story.append(Spacer(1, 7*mm))

    statements = []
    for skill in SKILLS:
        level = levels.get(skill)
        if level and level in CEFR_DESCRIPTORS[skill]:
            statements.append(
                f"• {CEFR_DESCRIPTORS[skill][level]}"
            )

    story.append(Paragraph("These practice results show that the candidate can:", styles["SectionHead"]))
    if statements:
        for statement in statements:
            story.append(Paragraph(statement, styles["BodyCompact"]))
    else:
        story.append(Paragraph(
            "No explicit A1/A2/B1 estimates are stored for this attempt yet. The portal does not invent a CEFR level from a percentage score.",
            styles["BodyCompact"],
        ))

    story.append(Spacer(1, 9*mm))
    story.append(Paragraph(
        "Practice CEFR descriptors and layout are based on the Test Report reference provided by the client. Practice results are generated by this portal and are not official Cambridge University Press & Assessment results.",
        styles["SmallMuted"],
    ))

    # Page 2 descriptor reference.
    story.append(PageBreak())
    story.append(Paragraph("CEFR Level Descriptors", styles["ReportTitle"]))
    story.append(Paragraph(
        "This portal uses A1, A2 and B1 practice labels where an explicit level estimate is available. The uploaded reference report states that each assessed skill is awarded a CEFR level and provides typical 'Can do' statements.",
        styles["BodyCompact"],
    ))
    story.append(Spacer(1, 5*mm))

    for skill in ("speaking", "listening", "reading", "writing"):
        data = [[SKILL_LABELS[skill].upper(), "Level", "Can do Statements"]]
        for label, level in (("Intermediate", "B1"), ("Elementary", "A2"), ("Beginner", "A1")):
            data.append([
                label,
                level,
                Paragraph(CEFR_DESCRIPTORS[skill][level], styles["BodyCompact"]),
            ])
        table = Table(data, colWidths=[35*mm, 28*mm, 103*mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#8BE0D5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.3, colors.white),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 4*mm))

    doc.build(story)
    buffer.seek(0)

    filename = f"practice-test-report-{attempt.pk}.pdf"
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )

@login_required
def practice_skill(request, skill):
    skill = str(skill).lower().strip()
    labels = {
        "reading": "Reading",
        "listening": "Listening",
        "speaking": "Speaking",
        "writing": "Writing",
    }
    if skill not in labels:
        raise Http404("Unknown practice skill")

    counts = {
        "reading": 5,
        "listening": 5,
        "speaking": 5,
        "writing": 2,
    }
    durations = {
        "reading": ["05:00", "05:00", "05:00", "05:00", "05:00"],
        "listening": ["05:00", "05:00", "05:00", "05:00", "05:00"],
        "speaking": ["05:00", "05:00", "05:00", "05:00", "01:50"],
        "writing": ["15:00", "15:00"],
    }

    # Each Part opens directly. Question grouping stays internal so students
    # progress through the configured questions without a visible Set screen.
    parts = []
    for i in range(1, counts[skill] + 1):
        parts.append({
            "number": i,
            "duration": durations[skill][i - 1],
        })

    return render(
        request,
        "student_final/practice_skill_reference.html",
        {
            "skill": skill,
            "skill_label": labels[skill],
            "parts": parts,
            "start_url": _test_skill_start_url(skill),
        },
    )

# ============================================================================
# FULL MOCK 4-SKILL TEST REPORT V6
# The visual structure follows the user's supplied 2-page Test Report reference.
# It is deliberately portal-branded and clearly marked as a PRACTICE report.
# ============================================================================

FULL_MOCK_REPORT_SKILLS_V6 = (
    "reading",
    "writing",
    "speaking",
    "listening",
)

# IMPORTANT:
# These descriptors intentionally preserve the wording/grouping in the supplied
# Test_Report.pdf. Do not silently "correct" or swap them here.
FULL_MOCK_CEFR_DESCRIPTORS_V6 = {
    "speaking": {
        "B1": "Can speak with colleagues or clients within own job area about simple matters.",
        "A2": "Can produce a short series of simple phrases and sentences on familiar topics.",
        "A1": "Can produce simple, mainly isolated phrases, on very familiar topics.",
    },
    "listening": {
        "B1": "Can understand the general meaning of short, non-routine messages and longer articles within their work context.",
        "A2": "Can understand short work-related documentation and messages within their area of expertise.",
        "A1": "Can understand very short work-related messages if the language is simple and the topic is familiar.",
    },
    "reading": {
        "B1": "Can understand the main ideas of clear speech on familiar topics found in the workplace.",
        "A2": "Can understand the main points of short, clear speech.",
        "A1": "Can recognise familiar words and very basic phases from slow, clear speech.",
    },
    "writing": {
        "B1": "Can write straightforward messages to colleagues, customers, or contacts at other companies on a range of familiar subjects.",
        "A2": "Can write simple messages to colleagues or known contacts at other companies.",
        "A1": "Can write short, simple routine requests to colleagues.",
    },
}


def _fm6_models():
    from django.apps import apps

    TestAttempt = apps.get_model("attempts", "TestAttempt")
    StudentResponse = apps.get_model("attempts", "StudentResponse")
    return TestAttempt, StudentResponse


def _fm6_attempt_skill_set(attempt):
    try:
        values = (
            attempt.attempt_questions
            .values_list("question__skill", flat=True)
            .distinct()
        )
        return {
            str(value).lower()
            for value in values
            if value
        }
    except Exception:
        return set()


def _fm6_is_full_mock(attempt):
    skills = _fm6_attempt_skill_set(attempt)

    if not set(FULL_MOCK_REPORT_SKILLS_V6).issubset(skills):
        return False

    status = str(getattr(attempt, "status", "") or "").lower()

    return status in {
        "submitted",
        "grading",
        "completed",
    }


def _fm6_feedback(response):
    value = getattr(response, "ai_feedback", None)
    return value if isinstance(value, dict) else {}


def _fm6_clean_cefr(value):
    if value in (None, ""):
        return None

    raw = str(value).upper().strip()

    for level in ("B1", "A2", "A1"):
        if level in raw:
            return level

    return None


def _fm6_response_cefr(response):
    for field in (
        "cefr_level",
        "cefr_estimate",
        "estimated_cefr",
    ):
        try:
            level = _fm6_clean_cefr(
                getattr(response, field)
            )
            if level:
                return level
        except Exception:
            pass

    feedback = _fm6_feedback(response)

    for key in (
        "practice_cefr",
        "cefr_estimate",
        "cefr",
        "estimated_cefr",
        "cefr_level",
    ):
        level = _fm6_clean_cefr(
            feedback.get(key)
        )
        if level:
            return level

    return None


def _fm6_metadata_level(attempt, skill):
    metadata = (
        attempt.metadata
        if isinstance(
            getattr(attempt, "metadata", None),
            dict,
        )
        else {}
    )

    for key in (
        "skill_cefr",
        "cefr_by_skill",
        "skill_levels",
        "cefr_levels",
    ):
        container = metadata.get(key)

        if isinstance(container, dict):
            level = _fm6_clean_cefr(
                container.get(skill)
                or container.get(skill.upper())
                or container.get(skill.title())
            )

            if level:
                return level

    return None


def _fm6_skill_levels(attempt):
    _, StudentResponse = _fm6_models()

    result = {
        skill: _fm6_metadata_level(
            attempt,
            skill,
        )
        for skill in FULL_MOCK_REPORT_SKILLS_V6
    }

    try:
        responses = (
            StudentResponse.objects
            .filter(
                attempt_question__attempt=attempt
            )
            .select_related(
                "attempt_question__question",
            )
            .order_by(
                "attempt_question__order",
                "id",
            )
        )
    except Exception:
        responses = []

    for response in responses:
        question = getattr(
            getattr(
                response,
                "attempt_question",
                None,
            ),
            "question",
            None,
        )

        skill = str(
            getattr(question, "skill", "") or ""
        ).lower()

        if (
            skill in result
            and not result[skill]
        ):
            level = _fm6_response_cefr(
                response
            )

            if level:
                result[skill] = level

    return result


def _fm6_explicit_overall_cefr(attempt):
    metadata = (
        attempt.metadata
        if isinstance(
            getattr(attempt, "metadata", None),
            dict,
        )
        else {}
    )

    for key in (
        "overall_cefr",
        "cefr",
        "cefr_level",
        "practice_cefr",
    ):
        level = _fm6_clean_cefr(
            metadata.get(key)
        )
        if level:
            return level

    # No invented percentage-to-CEFR threshold.
    return None


def _fm6_candidate_name(user):
    try:
        profile = user.student_profile

        name = str(
            getattr(
                profile,
                "certificate_name",
                "",
            )
            or ""
        ).strip()

        if name:
            return name.upper()
    except Exception:
        pass

    full = str(
        user.get_full_name() or ""
    ).strip()

    return (
        full
        or str(user.username)
    ).upper()


def _fm6_profile_photo_path(user):
    try:
        photo = user.student_profile.profile_photo

        if photo and photo.name:
            return photo.path
    except Exception:
        pass

    return None


def _fm6_candidate_id(attempt):
    import hashlib

    user_id = getattr(
        getattr(attempt, "user", None),
        "pk",
        0,
    )

    seed = (
        f"{user_id}:"
        f"{attempt.pk}:"
        f"{getattr(attempt, 'started_at', '')}"
    )

    return hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()[:10].upper()


def _fm6_date_issued(attempt):
    from django.utils import timezone

    value = (
        getattr(attempt, "completed_at", None)
        or getattr(attempt, "started_at", None)
        or timezone.now()
    )

    try:
        value = timezone.localtime(value)
    except Exception:
        pass

    return value.strftime("%d-%m-%Y")


def _fm6_level_segments(level):
    count = {
        "A1": 1,
        "A2": 2,
        "B1": 3,
    }.get(level, 0)

    return [
        index <= count
        for index in range(1, 4)
    ]


def _fm6_report_rows(user):
    TestAttempt, _ = _fm6_models()

    attempts = (
        TestAttempt.objects
        .filter(user=user)
        .select_related("mock_test")
        .order_by("-started_at")
    )

    rows = []

    for attempt in attempts:
        if not _fm6_is_full_mock(attempt):
            continue

        levels = _fm6_skill_levels(attempt)

        rows.append({
            "attempt": attempt,
            "levels": levels,
            "all_levels_ready": all(
                levels.get(skill)
                for skill
                in FULL_MOCK_REPORT_SKILLS_V6
            ),
            "overall_cefr": _fm6_explicit_overall_cefr(
                attempt
            ),
        })

    return rows


def _fm6_draw_photo(
    canvas,
    photo_path,
    x,
    y,
    width,
    height,
    initials,
):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    if photo_path:
        try:
            canvas.drawImage(
                ImageReader(photo_path),
                x,
                y,
                width,
                height,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            return
        except Exception:
            pass

    canvas.setFillColor(
        HexColor("#E8EBEF")
    )
    canvas.rect(
        x,
        y,
        width,
        height,
        fill=1,
        stroke=0,
    )

    canvas.setFillColor(
        HexColor("#6B7280")
    )
    canvas.setFont(
        "Helvetica-Bold",
        24,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height / 2 - 8,
        initials[:2],
    )


def _fm6_make_report_pdf(attempt):
    from io import BytesIO

    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph

    W, H = A4
    teal = HexColor("#13BBB8")
    teal_light = HexColor("#D5F5F1")
    charcoal = HexColor("#5C5C5C")
    dark = HexColor("#252525")
    light = HexColor("#F1F2F3")
    line = HexColor("#E4E2DE")
    gray = HexColor("#747474")
    white = HexColor("#FFFFFF")

    buffer = BytesIO()
    c = canvas.Canvas(
        buffer,
        pagesize=A4,
    )

    candidate_name = _fm6_candidate_name(
        attempt.user
    )
    candidate_id = _fm6_candidate_id(
        attempt
    )
    issue_date = _fm6_date_issued(
        attempt
    )
    levels = _fm6_skill_levels(
        attempt
    )
    overall = _fm6_explicit_overall_cefr(
        attempt
    ) or "—"

    initials = "".join(
        part[:1]
        for part
        in candidate_name.split()
        if part
    )

    photo_path = _fm6_profile_photo_path(
        attempt.user
    )

    # ---------------------------------------------------------------------
    # PAGE 1 — follows the supplied Test_Report.pdf layout.
    # ---------------------------------------------------------------------
    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Soft abstract background pieces similar to the reference.
    c.setFillColor(light)
    c.circle(
        -22 * mm,
        H - 96 * mm,
        72 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        W - 5 * mm,
        H - 128 * mm,
        52 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        W - 20 * mm,
        72 * mm,
        62 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        18 * mm,
        20 * mm,
        58 * mm,
        fill=1,
        stroke=0,
    )

    # Portal brand in the same top-left visual position.
    c.setFillColor(teal)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(
        10 * mm,
        H - 18 * mm,
        "Upskill."
    )
    c.setFillColor(gray)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(
        31 * mm,
        H - 27 * mm,
        "PRACTICE PORTAL"
    )

    # Date / Candidate ID boxes.
    box_y = H - 28 * mm
    box_h = 23 * mm
    box_w = 42 * mm

    for x, label, value in (
        (
            W - 94 * mm,
            "DATE ISSUED",
            issue_date,
        ),
        (
            W - 49 * mm,
            "Candidate ID",
            candidate_id,
        ),
    ):
        c.setFillColor(white)
        c.setStrokeColor(line)
        c.setLineWidth(1.2)
        c.rect(
            x,
            box_y,
            box_w,
            box_h,
            fill=1,
            stroke=1,
        )

        c.setFillColor(dark)
        c.setFont(
            "Helvetica-Bold",
            8.5,
        )
        c.drawCentredString(
            x + box_w / 2,
            box_y + 15.2 * mm,
            label,
        )

        c.setFont(
            "Helvetica",
            9.4,
        )
        c.drawCentredString(
            x + box_w / 2,
            box_y + 8.0 * mm,
            value,
        )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        25,
    )
    c.drawString(
        10 * mm,
        H - 52 * mm,
        "Test Report",
    )

    # Student photo.
    _fm6_draw_photo(
        c,
        photo_path,
        W - 54 * mm,
        H - 87 * mm,
        44 * mm,
        45 * mm,
        initials,
    )

    # Candidate name.
    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        8,
    )
    c.drawString(
        10 * mm,
        H - 68 * mm,
        "Candidate name",
    )

    c.setFillColor(teal_light)
    c.setStrokeColor(teal)
    c.setLineWidth(2.0)
    c.rect(
        10 * mm,
        H - 82 * mm,
        130 * mm,
        11 * mm,
        fill=1,
        stroke=1,
    )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        12,
    )
    c.drawString(
        15 * mm,
        H - 78.5 * mm,
        candidate_name[:42],
    )

    # Overall CEFR circle.
    center_x = 44 * mm
    center_y = H - 142 * mm
    radius = 26 * mm

    c.setFillColor(teal_light)
    c.setStrokeColor(teal)
    c.setLineWidth(2.5)
    c.circle(
        center_x,
        center_y,
        radius,
        fill=1,
        stroke=1,
    )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        7.5,
    )
    c.drawCentredString(
        center_x,
        center_y + 10 * mm,
        "On the CEFR scale",
    )

    c.setFont(
        "Helvetica-Bold",
        34,
    )
    c.drawCentredString(
        center_x,
        center_y - 5 * mm,
        overall,
    )

    # Four skill blocks.
    positions = {
        "reading": (
            88 * mm,
            H - 123 * mm,
        ),
        "writing": (
            134 * mm,
            H - 123 * mm,
        ),
        "speaking": (
            88 * mm,
            H - 150 * mm,
        ),
        "listening": (
            134 * mm,
            H - 150 * mm,
        ),
    }

    for skill in (
        "reading",
        "writing",
        "speaking",
        "listening",
    ):
        x, y = positions[skill]
        level = levels.get(skill)

        c.setFillColor(charcoal)
        c.setFont(
            "Helvetica-Bold",
            11,
        )
        c.drawString(
            x,
            y,
            skill.upper(),
        )

        segment_y = y - 8 * mm
        segment_w = 10.5 * mm
        gap = 2 * mm

        for index, active in enumerate(
            _fm6_level_segments(level)
        ):
            c.setFillColor(
                teal if active else charcoal
            )
            c.rect(
                x + index * (
                    segment_w + gap
                ),
                segment_y,
                segment_w,
                2.8 * mm,
                fill=1,
                stroke=0,
            )

        c.setFillColor(charcoal)
        c.setFont(
            "Helvetica-Bold",
            9,
        )
        c.drawString(
            x,
            segment_y - 7 * mm,
            level or "—",
        )

    # Can-do statements.
    c.setFillColor(dark)
    c.setFont(
        "Helvetica-Bold",
        10.5,
    )
    c.drawString(
        10 * mm,
        79 * mm,
        "These results show that the candidate can:",
    )

    body_style = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.2,
        textColor=charcoal,
        alignment=TA_LEFT,
    )

    # The bullet order mirrors the supplied reference page.
    bullet_skills = (
        "listening",
        "writing",
        "speaking",
        "reading",
    )

    y = 72 * mm

    for skill in bullet_skills:
        level = levels.get(skill)

        statement = (
            FULL_MOCK_CEFR_DESCRIPTORS_V6
            .get(skill, {})
            .get(
                level,
                "CEFR estimate is not available yet for this skill.",
            )
        )

        paragraph = Paragraph(
            "• " + statement,
            body_style,
        )

        _, height = paragraph.wrap(
            W - 28 * mm,
            18 * mm,
        )

        paragraph.drawOn(
            c,
            14 * mm,
            y - height,
        )

        y -= height + 2.1 * mm

    # Footer / practice disclaimer.
    c.setStrokeColor(line)
    c.line(
        10 * mm,
        13 * mm,
        W - 10 * mm,
        13 * mm,
    )

    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        6.5,
    )
    c.drawString(
        10 * mm,
        8 * mm,
        "Upskill Practice · Surakshya Technologies · Practice Test Report",
    )

    c.drawRightString(
        W - 10 * mm,
        8 * mm,
        "Not an official Cambridge result or certificate",
    )

    c.showPage()

    # ---------------------------------------------------------------------
    # PAGE 2 — CEFR descriptor page, matching the source report structure.
    # ---------------------------------------------------------------------
    c.setFillColor(white)
    c.rect(
        0,
        0,
        W,
        H,
        fill=1,
        stroke=0,
    )

    c.setFillColor(dark)
    c.setFont(
        "Helvetica-Bold",
        19,
    )
    c.drawString(
        12 * mm,
        H - 20 * mm,
        "CEFR Level Descriptors",
    )

    intro = (
        "Upskill assesses English language ability at A1, A2, and B1 on the "
        "Common European Framework of Reference (CEFR). For each skill assessed, "
        "candidates are awarded a CEFR level. If more than one skill is assessed, "
        "an average score is awarded. A short description of what a typical "
        "candidate can do at the achieved CEFR level is also reported."
    )

    intro_style = ParagraphStyle(
        "intro",
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=charcoal,
    )

    intro_p = Paragraph(
        intro,
        intro_style,
    )

    _, intro_h = intro_p.wrap(
        W - 24 * mm,
        35 * mm,
    )

    intro_p.drawOn(
        c,
        12 * mm,
        H - 27 * mm - intro_h,
    )

    current_y = (
        H
        - 31 * mm
        - intro_h
        - 6 * mm
    )

    level_rows = (
        ("Intermediate", "B1"),
        ("Elementary", "A2"),
        ("Beginner", "A1"),
    )

    section_style = ParagraphStyle(
        "section",
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.2,
        textColor=charcoal,
    )

    for skill in (
        "speaking",
        "listening",
        "reading",
        "writing",
    ):
        c.setFillColor(dark)
        c.setFont(
            "Helvetica-Bold",
            10,
        )
        c.drawString(
            12 * mm,
            current_y,
            skill.upper(),
        )

        c.setFont(
            "Helvetica-Bold",
            7.4,
        )
        c.drawString(
            57 * mm,
            current_y,
            "Level",
        )
        c.drawString(
            75 * mm,
            current_y,
            "Can do Statements",
        )

        current_y -= 5.5 * mm

        for title, level in level_rows:
            c.setFillColor(charcoal)
            c.setFont(
                "Helvetica",
                7.5,
            )
            c.drawString(
                12 * mm,
                current_y,
                title,
            )

            c.setFont(
                "Helvetica-Bold",
                7.5,
            )
            c.drawString(
                57 * mm,
                current_y,
                level,
            )

            statement = (
                FULL_MOCK_CEFR_DESCRIPTORS_V6
                [skill][level]
            )

            para = Paragraph(
                statement,
                section_style,
            )

            _, para_h = para.wrap(
                W - 88 * mm,
                18 * mm,
            )

            para.drawOn(
                c,
                75 * mm,
                current_y - para_h + 2 * mm,
            )

            row_height = max(
                para_h + 2 * mm,
                7 * mm,
            )

            c.setStrokeColor(
                HexColor("#ECEEF1")
            )
            c.line(
                12 * mm,
                current_y - row_height + 1 * mm,
                W - 12 * mm,
                current_y - row_height + 1 * mm,
            )

            current_y -= row_height

        current_y -= 5 * mm

    c.setStrokeColor(line)
    c.line(
        10 * mm,
        13 * mm,
        W - 10 * mm,
        13 * mm,
    )

    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        6.5,
    )
    c.drawString(
        10 * mm,
        8 * mm,
        "Upskill Practice · Surakshya Technologies · Practice CEFR descriptor reference",
    )

    c.drawRightString(
        W - 10 * mm,
        8 * mm,
        "Not an official Cambridge result or certificate",
    )

    c.save()
    buffer.seek(0)
    return buffer


from django.contrib.auth.decorators import login_required as _fm6_login_required


@_fm6_login_required
def certificates(request):
    from django.shortcuts import render

    rows = _fm6_report_rows(
        request.user
    )

    return render(
        request,
        "student_final/certificates.html",
        {
            "rows": rows,
        },
    )


@_fm6_login_required
def practice_report_pdf(
    request,
    attempt_id,
):
    from django.http import (
        FileResponse,
        Http404,
    )

    TestAttempt, _ = _fm6_models()

    try:
        attempt = (
            TestAttempt.objects
            .select_related(
                "user",
                "mock_test",
            )
            .get(
                pk=attempt_id,
                user=request.user,
            )
        )
    except TestAttempt.DoesNotExist:
        raise Http404(
            "Test attempt not found."
        )

    if not _fm6_is_full_mock(
        attempt
    ):
        raise Http404(
            "A Test Report is available only for a completed full mock containing Reading, Writing, Speaking and Listening."
        )

    pdf = _fm6_make_report_pdf(
        attempt
    )

    filename = (
        f"upskill-practice-test-report-"
        f"{attempt.pk}.pdf"
    )

    return FileResponse(
        pdf,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )


# ============================================================================
# FULL MOCK 4-SKILL TEST REPORT V6
# The visual structure follows the user's supplied 2-page Test Report reference.
# It is deliberately portal-branded and clearly marked as a PRACTICE report.
# ============================================================================

FULL_MOCK_REPORT_SKILLS_V6 = (
    "reading",
    "writing",
    "speaking",
    "listening",
)

# IMPORTANT:
# These descriptors intentionally preserve the wording/grouping in the supplied
# Test_Report.pdf. Do not silently "correct" or swap them here.
FULL_MOCK_CEFR_DESCRIPTORS_V6 = {
    "speaking": {
        "B1": "Can speak with colleagues or clients within own job area about simple matters.",
        "A2": "Can produce a short series of simple phrases and sentences on familiar topics.",
        "A1": "Can produce simple, mainly isolated phrases, on very familiar topics.",
    },
    "listening": {
        "B1": "Can understand the general meaning of short, non-routine messages and longer articles within their work context.",
        "A2": "Can understand short work-related documentation and messages within their area of expertise.",
        "A1": "Can understand very short work-related messages if the language is simple and the topic is familiar.",
    },
    "reading": {
        "B1": "Can understand the main ideas of clear speech on familiar topics found in the workplace.",
        "A2": "Can understand the main points of short, clear speech.",
        "A1": "Can recognise familiar words and very basic phases from slow, clear speech.",
    },
    "writing": {
        "B1": "Can write straightforward messages to colleagues, customers, or contacts at other companies on a range of familiar subjects.",
        "A2": "Can write simple messages to colleagues or known contacts at other companies.",
        "A1": "Can write short, simple routine requests to colleagues.",
    },
}


def _fm6_models():
    from django.apps import apps

    TestAttempt = apps.get_model("attempts", "TestAttempt")
    StudentResponse = apps.get_model("attempts", "StudentResponse")
    return TestAttempt, StudentResponse


def _fm6_attempt_skill_set(attempt):
    try:
        values = (
            attempt.attempt_questions
            .values_list("question__skill", flat=True)
            .distinct()
        )
        return {
            str(value).lower()
            for value in values
            if value
        }
    except Exception:
        return set()


def _fm6_is_full_mock(attempt):
    skills = _fm6_attempt_skill_set(attempt)

    if not set(FULL_MOCK_REPORT_SKILLS_V6).issubset(skills):
        return False

    status = str(getattr(attempt, "status", "") or "").lower()

    return status in {
        "submitted",
        "grading",
        "completed",
    }


def _fm6_feedback(response):
    value = getattr(response, "ai_feedback", None)
    return value if isinstance(value, dict) else {}


def _fm6_clean_cefr(value):
    if value in (None, ""):
        return None

    raw = str(value).upper().strip()

    for level in ("B1", "A2", "A1"):
        if level in raw:
            return level

    return None


def _fm6_response_cefr(response):
    for field in (
        "cefr_level",
        "cefr_estimate",
        "estimated_cefr",
    ):
        try:
            level = _fm6_clean_cefr(
                getattr(response, field)
            )
            if level:
                return level
        except Exception:
            pass

    feedback = _fm6_feedback(response)

    for key in (
        "practice_cefr",
        "cefr_estimate",
        "cefr",
        "estimated_cefr",
        "cefr_level",
    ):
        level = _fm6_clean_cefr(
            feedback.get(key)
        )
        if level:
            return level

    return None


def _fm6_metadata_level(attempt, skill):
    metadata = (
        attempt.metadata
        if isinstance(
            getattr(attempt, "metadata", None),
            dict,
        )
        else {}
    )

    for key in (
        "skill_cefr",
        "cefr_by_skill",
        "skill_levels",
        "cefr_levels",
    ):
        container = metadata.get(key)

        if isinstance(container, dict):
            level = _fm6_clean_cefr(
                container.get(skill)
                or container.get(skill.upper())
                or container.get(skill.title())
            )

            if level:
                return level

    return None


def _fm6_skill_levels(attempt):
    _, StudentResponse = _fm6_models()

    result = {
        skill: _fm6_metadata_level(
            attempt,
            skill,
        )
        for skill in FULL_MOCK_REPORT_SKILLS_V6
    }

    try:
        responses = (
            StudentResponse.objects
            .filter(
                attempt_question__attempt=attempt
            )
            .select_related(
                "attempt_question__question",
            )
            .order_by(
                "attempt_question__order",
                "id",
            )
        )
    except Exception:
        responses = []

    for response in responses:
        question = getattr(
            getattr(
                response,
                "attempt_question",
                None,
            ),
            "question",
            None,
        )

        skill = str(
            getattr(question, "skill", "") or ""
        ).lower()

        if (
            skill in result
            and not result[skill]
        ):
            level = _fm6_response_cefr(
                response
            )

            if level:
                result[skill] = level

    return result


def _fm6_explicit_overall_cefr(attempt):
    metadata = (
        attempt.metadata
        if isinstance(
            getattr(attempt, "metadata", None),
            dict,
        )
        else {}
    )

    for key in (
        "overall_cefr",
        "cefr",
        "cefr_level",
        "practice_cefr",
    ):
        level = _fm6_clean_cefr(
            metadata.get(key)
        )
        if level:
            return level

    # No invented percentage-to-CEFR threshold.
    return None


def _fm6_candidate_name(user):
    try:
        profile = user.student_profile

        name = str(
            getattr(
                profile,
                "certificate_name",
                "",
            )
            or ""
        ).strip()

        if name:
            return name.upper()
    except Exception:
        pass

    full = str(
        user.get_full_name() or ""
    ).strip()

    return (
        full
        or str(user.username)
    ).upper()


def _fm6_profile_photo_path(user):
    try:
        photo = user.student_profile.profile_photo

        if photo and photo.name:
            return photo.path
    except Exception:
        pass

    return None


def _fm6_candidate_id(attempt):
    import hashlib

    user_id = getattr(
        getattr(attempt, "user", None),
        "pk",
        0,
    )

    seed = (
        f"{user_id}:"
        f"{attempt.pk}:"
        f"{getattr(attempt, 'started_at', '')}"
    )

    return hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()[:10].upper()


def _fm6_date_issued(attempt):
    from django.utils import timezone

    value = (
        getattr(attempt, "completed_at", None)
        or getattr(attempt, "started_at", None)
        or timezone.now()
    )

    try:
        value = timezone.localtime(value)
    except Exception:
        pass

    return value.strftime("%d-%m-%Y")


def _fm6_level_segments(level):
    count = {
        "A1": 1,
        "A2": 2,
        "B1": 3,
    }.get(level, 0)

    return [
        index <= count
        for index in range(1, 4)
    ]


def _fm6_report_rows(user):
    TestAttempt, _ = _fm6_models()

    attempts = (
        TestAttempt.objects
        .filter(user=user)
        .select_related("mock_test")
        .order_by("-started_at")
    )

    rows = []

    for attempt in attempts:
        if not _fm6_is_full_mock(attempt):
            continue

        levels = _fm6_skill_levels(attempt)

        rows.append({
            "attempt": attempt,
            "levels": levels,
            "all_levels_ready": all(
                levels.get(skill)
                for skill
                in FULL_MOCK_REPORT_SKILLS_V6
            ),
            "overall_cefr": _fm6_explicit_overall_cefr(
                attempt
            ),
        })

    return rows


def _fm6_draw_photo(
    canvas,
    photo_path,
    x,
    y,
    width,
    height,
    initials,
):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    if photo_path:
        try:
            canvas.drawImage(
                ImageReader(photo_path),
                x,
                y,
                width,
                height,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            return
        except Exception:
            pass

    canvas.setFillColor(
        HexColor("#E8EBEF")
    )
    canvas.rect(
        x,
        y,
        width,
        height,
        fill=1,
        stroke=0,
    )

    canvas.setFillColor(
        HexColor("#6B7280")
    )
    canvas.setFont(
        "Helvetica-Bold",
        24,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height / 2 - 8,
        initials[:2],
    )


def _fm6_make_report_pdf(attempt):
    from io import BytesIO

    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph

    W, H = A4
    teal = HexColor("#13BBB8")
    teal_light = HexColor("#D5F5F1")
    charcoal = HexColor("#5C5C5C")
    dark = HexColor("#252525")
    light = HexColor("#F1F2F3")
    line = HexColor("#E4E2DE")
    gray = HexColor("#747474")
    white = HexColor("#FFFFFF")

    buffer = BytesIO()
    c = canvas.Canvas(
        buffer,
        pagesize=A4,
    )

    candidate_name = _fm6_candidate_name(
        attempt.user
    )
    candidate_id = _fm6_candidate_id(
        attempt
    )
    issue_date = _fm6_date_issued(
        attempt
    )
    levels = _fm6_skill_levels(
        attempt
    )
    overall = _fm6_explicit_overall_cefr(
        attempt
    ) or "—"

    initials = "".join(
        part[:1]
        for part
        in candidate_name.split()
        if part
    )

    photo_path = _fm6_profile_photo_path(
        attempt.user
    )

    # ---------------------------------------------------------------------
    # PAGE 1 — follows the supplied Test_Report.pdf layout.
    # ---------------------------------------------------------------------
    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Soft abstract background pieces similar to the reference.
    c.setFillColor(light)
    c.circle(
        -22 * mm,
        H - 96 * mm,
        72 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        W - 5 * mm,
        H - 128 * mm,
        52 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        W - 20 * mm,
        72 * mm,
        62 * mm,
        fill=1,
        stroke=0,
    )
    c.circle(
        18 * mm,
        20 * mm,
        58 * mm,
        fill=1,
        stroke=0,
    )

    # Portal brand in the same top-left visual position.
    c.setFillColor(teal)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(
        10 * mm,
        H - 18 * mm,
        "Upskill."
    )
    c.setFillColor(gray)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(
        31 * mm,
        H - 27 * mm,
        "PRACTICE PORTAL"
    )

    # Date / Candidate ID boxes.
    box_y = H - 28 * mm
    box_h = 23 * mm
    box_w = 42 * mm

    for x, label, value in (
        (
            W - 94 * mm,
            "DATE ISSUED",
            issue_date,
        ),
        (
            W - 49 * mm,
            "Candidate ID",
            candidate_id,
        ),
    ):
        c.setFillColor(white)
        c.setStrokeColor(line)
        c.setLineWidth(1.2)
        c.rect(
            x,
            box_y,
            box_w,
            box_h,
            fill=1,
            stroke=1,
        )

        c.setFillColor(dark)
        c.setFont(
            "Helvetica-Bold",
            8.5,
        )
        c.drawCentredString(
            x + box_w / 2,
            box_y + 15.2 * mm,
            label,
        )

        c.setFont(
            "Helvetica",
            9.4,
        )
        c.drawCentredString(
            x + box_w / 2,
            box_y + 8.0 * mm,
            value,
        )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        25,
    )
    c.drawString(
        10 * mm,
        H - 52 * mm,
        "Test Report",
    )

    # Student photo.
    _fm6_draw_photo(
        c,
        photo_path,
        W - 54 * mm,
        H - 87 * mm,
        44 * mm,
        45 * mm,
        initials,
    )

    # Candidate name.
    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        8,
    )
    c.drawString(
        10 * mm,
        H - 68 * mm,
        "Candidate name",
    )

    c.setFillColor(teal_light)
    c.setStrokeColor(teal)
    c.setLineWidth(2.0)
    c.rect(
        10 * mm,
        H - 82 * mm,
        130 * mm,
        11 * mm,
        fill=1,
        stroke=1,
    )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        12,
    )
    c.drawString(
        15 * mm,
        H - 78.5 * mm,
        candidate_name[:42],
    )

    # Overall CEFR circle.
    center_x = 44 * mm
    center_y = H - 142 * mm
    radius = 26 * mm

    c.setFillColor(teal_light)
    c.setStrokeColor(teal)
    c.setLineWidth(2.5)
    c.circle(
        center_x,
        center_y,
        radius,
        fill=1,
        stroke=1,
    )

    c.setFillColor(charcoal)
    c.setFont(
        "Helvetica-Bold",
        7.5,
    )
    c.drawCentredString(
        center_x,
        center_y + 10 * mm,
        "On the CEFR scale",
    )

    c.setFont(
        "Helvetica-Bold",
        34,
    )
    c.drawCentredString(
        center_x,
        center_y - 5 * mm,
        overall,
    )

    # Four skill blocks.
    positions = {
        "reading": (
            88 * mm,
            H - 123 * mm,
        ),
        "writing": (
            134 * mm,
            H - 123 * mm,
        ),
        "speaking": (
            88 * mm,
            H - 150 * mm,
        ),
        "listening": (
            134 * mm,
            H - 150 * mm,
        ),
    }

    for skill in (
        "reading",
        "writing",
        "speaking",
        "listening",
    ):
        x, y = positions[skill]
        level = levels.get(skill)

        c.setFillColor(charcoal)
        c.setFont(
            "Helvetica-Bold",
            11,
        )
        c.drawString(
            x,
            y,
            skill.upper(),
        )

        segment_y = y - 8 * mm
        segment_w = 10.5 * mm
        gap = 2 * mm

        for index, active in enumerate(
            _fm6_level_segments(level)
        ):
            c.setFillColor(
                teal if active else charcoal
            )
            c.rect(
                x + index * (
                    segment_w + gap
                ),
                segment_y,
                segment_w,
                2.8 * mm,
                fill=1,
                stroke=0,
            )

        c.setFillColor(charcoal)
        c.setFont(
            "Helvetica-Bold",
            9,
        )
        c.drawString(
            x,
            segment_y - 7 * mm,
            level or "—",
        )

    # Can-do statements.
    c.setFillColor(dark)
    c.setFont(
        "Helvetica-Bold",
        10.5,
    )
    c.drawString(
        10 * mm,
        79 * mm,
        "These results show that the candidate can:",
    )

    body_style = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.2,
        textColor=charcoal,
        alignment=TA_LEFT,
    )

    # The bullet order mirrors the supplied reference page.
    bullet_skills = (
        "listening",
        "writing",
        "speaking",
        "reading",
    )

    y = 72 * mm

    for skill in bullet_skills:
        level = levels.get(skill)

        statement = (
            FULL_MOCK_CEFR_DESCRIPTORS_V6
            .get(skill, {})
            .get(
                level,
                "CEFR estimate is not available yet for this skill.",
            )
        )

        paragraph = Paragraph(
            "• " + statement,
            body_style,
        )

        _, height = paragraph.wrap(
            W - 28 * mm,
            18 * mm,
        )

        paragraph.drawOn(
            c,
            14 * mm,
            y - height,
        )

        y -= height + 2.1 * mm

    # Footer / practice disclaimer.
    c.setStrokeColor(line)
    c.line(
        10 * mm,
        13 * mm,
        W - 10 * mm,
        13 * mm,
    )

    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        6.5,
    )
    c.drawString(
        10 * mm,
        8 * mm,
        "Upskill Practice · Surakshya Technologies · Practice Test Report",
    )

    c.drawRightString(
        W - 10 * mm,
        8 * mm,
        "Not an official Cambridge result or certificate",
    )

    c.showPage()

    # ---------------------------------------------------------------------
    # PAGE 2 — CEFR descriptor page, matching the source report structure.
    # ---------------------------------------------------------------------
    c.setFillColor(white)
    c.rect(
        0,
        0,
        W,
        H,
        fill=1,
        stroke=0,
    )

    c.setFillColor(dark)
    c.setFont(
        "Helvetica-Bold",
        19,
    )
    c.drawString(
        12 * mm,
        H - 20 * mm,
        "CEFR Level Descriptors",
    )

    intro = (
        "Upskill assesses English language ability at A1, A2, and B1 on the "
        "Common European Framework of Reference (CEFR). For each skill assessed, "
        "candidates are awarded a CEFR level. If more than one skill is assessed, "
        "an average score is awarded. A short description of what a typical "
        "candidate can do at the achieved CEFR level is also reported."
    )

    intro_style = ParagraphStyle(
        "intro",
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=charcoal,
    )

    intro_p = Paragraph(
        intro,
        intro_style,
    )

    _, intro_h = intro_p.wrap(
        W - 24 * mm,
        35 * mm,
    )

    intro_p.drawOn(
        c,
        12 * mm,
        H - 27 * mm - intro_h,
    )

    current_y = (
        H
        - 31 * mm
        - intro_h
        - 6 * mm
    )

    level_rows = (
        ("Intermediate", "B1"),
        ("Elementary", "A2"),
        ("Beginner", "A1"),
    )

    section_style = ParagraphStyle(
        "section",
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.2,
        textColor=charcoal,
    )

    for skill in (
        "speaking",
        "listening",
        "reading",
        "writing",
    ):
        c.setFillColor(dark)
        c.setFont(
            "Helvetica-Bold",
            10,
        )
        c.drawString(
            12 * mm,
            current_y,
            skill.upper(),
        )

        c.setFont(
            "Helvetica-Bold",
            7.4,
        )
        c.drawString(
            57 * mm,
            current_y,
            "Level",
        )
        c.drawString(
            75 * mm,
            current_y,
            "Can do Statements",
        )

        current_y -= 5.5 * mm

        for title, level in level_rows:
            c.setFillColor(charcoal)
            c.setFont(
                "Helvetica",
                7.5,
            )
            c.drawString(
                12 * mm,
                current_y,
                title,
            )

            c.setFont(
                "Helvetica-Bold",
                7.5,
            )
            c.drawString(
                57 * mm,
                current_y,
                level,
            )

            statement = (
                FULL_MOCK_CEFR_DESCRIPTORS_V6
                [skill][level]
            )

            para = Paragraph(
                statement,
                section_style,
            )

            _, para_h = para.wrap(
                W - 88 * mm,
                18 * mm,
            )

            para.drawOn(
                c,
                75 * mm,
                current_y - para_h + 2 * mm,
            )

            row_height = max(
                para_h + 2 * mm,
                7 * mm,
            )

            c.setStrokeColor(
                HexColor("#ECEEF1")
            )
            c.line(
                12 * mm,
                current_y - row_height + 1 * mm,
                W - 12 * mm,
                current_y - row_height + 1 * mm,
            )

            current_y -= row_height

        current_y -= 5 * mm

    c.setStrokeColor(line)
    c.line(
        10 * mm,
        13 * mm,
        W - 10 * mm,
        13 * mm,
    )

    c.setFillColor(gray)
    c.setFont(
        "Helvetica",
        6.5,
    )
    c.drawString(
        10 * mm,
        8 * mm,
        "Upskill Practice · Surakshya Technologies · Practice CEFR descriptor reference",
    )

    c.drawRightString(
        W - 10 * mm,
        8 * mm,
        "Not an official Cambridge result or certificate",
    )

    c.save()
    buffer.seek(0)
    return buffer


from django.contrib.auth.decorators import login_required as _fm6_login_required


@_fm6_login_required
def certificates(request):
    from django.shortcuts import render

    rows = _fm6_report_rows(
        request.user
    )

    # DASHBOARD_REFERENCE_REPLICA_20260826: keep the final report implementation
    # while supplying the same shared sidebar context as every other student page.
    context = _base_context(
        request,
        "certificates",
    )
    context["rows"] = rows

    return render(
        request,
        "student_final/certificates.html",
        context,
    )


@_fm6_login_required
def practice_report_pdf(
    request,
    attempt_id,
):
    from django.http import (
        FileResponse,
        Http404,
    )

    TestAttempt, _ = _fm6_models()

    try:
        attempt = (
            TestAttempt.objects
            .select_related(
                "user",
                "mock_test",
            )
            .get(
                pk=attempt_id,
                user=request.user,
            )
        )
    except TestAttempt.DoesNotExist:
        raise Http404(
            "Test attempt not found."
        )

    if not _fm6_is_full_mock(
        attempt
    ):
        raise Http404(
            "A Test Report is available only for a completed full mock containing Reading, Writing, Speaking and Listening."
        )

    pdf = _fm6_make_report_pdf(
        attempt
    )

    filename = (
        f"upskill-practice-test-report-"
        f"{attempt.pk}.pdf"
    )

    return FileResponse(
        pdf,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )

