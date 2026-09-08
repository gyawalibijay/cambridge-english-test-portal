"""Arya Academy Practice Mock Test Report, inspired by the supplied report hierarchy."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from attempts.models import TestAttempt
from attempts.full_mock_v35_part2 import is_continuous_full_mock
from attempts.full_mock_v35_part3 import summary_for_attempt

PRACTICE_BANDS = (
    (70.0, "B1"),
    (45.0, "A2"),
    (0.0, "A1"),
)

DESCRIPTORS = {
    "reading": {
        "A1": "Recognise familiar words and very simple phrases.",
        "A2": "Understand the main points of short, clear texts on familiar topics.",
        "B1": "Understand main ideas in straightforward texts about familiar work and everyday topics.",
    },
    "listening": {
        "A1": "Follow very slow, clearly articulated speech on familiar topics.",
        "A2": "Understand the main points of short, clear speech.",
        "B1": "Follow clear speech and identify main ideas on familiar workplace and everyday topics.",
    },
    "speaking": {
        "A1": "Produce simple phrases about very familiar personal topics.",
        "A2": "Give a short connected description or presentation on a familiar topic.",
        "B1": "Sustain straightforward conversation and descriptions on familiar work and everyday subjects.",
    },
    "writing": {
        "A1": "Write short, simple phrases and sentences.",
        "A2": "Write simple connected messages to familiar contacts.",
        "B1": "Write straightforward connected messages on a range of familiar subjects.",
    },
}

SKILL_ORDER_PAGE1 = ("reading", "writing", "speaking", "listening")
SKILL_ORDER_PAGE2 = ("speaking", "listening", "reading", "writing")


def _owned(request, attempt_id):
    qs = TestAttempt.objects.select_related("user", "mock_test", "mock_test__program")
    if request.user.is_staff:
        return get_object_or_404(qs, pk=attempt_id)
    return get_object_or_404(qs, pk=attempt_id, user=request.user)


def _level(percent):
    value = float(percent or 0)
    for minimum, level in PRACTICE_BANDS:
        if value >= minimum:
            return level
    return "A1"


def _candidate_name(user):
    try:
        name = user.get_full_name().strip()
    except Exception:
        name = ""
    return name or getattr(user, "username", "") or f"Student {user.pk}"


def _photo_path(user):
    objects = [user]
    for relation in ("profile", "student_profile", "studentprofile", "learner_profile"):
        try:
            obj = getattr(user, relation)
        except Exception:
            obj = None
        if obj is not None:
            objects.append(obj)

    for obj in objects:
        for field in ("profile_photo", "photo", "avatar", "image", "profile_image"):
            try:
                value = getattr(obj, field)
            except Exception:
                value = None
            if not value:
                continue
            try:
                path = Path(value.path)
            except Exception:
                path = None
            if path and path.is_file():
                return path
    return None


def _font_path(bold=False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for value in candidates:
        if Path(value).is_file():
            return value
    return None


def _build_pdf(attempt, summary):
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except Exception as exc:
        raise RuntimeError("Pillow is required for the Practice Mock Report.") from exc

    W, H = 1240, 1754
    WHITE = "#ffffff"
    INK = "#4f5053"
    DARK = "#101a35"
    MUTED = "#6f7277"
    TEAL = "#08b9b5"
    TEAL_SOFT = "#dff8f6"
    LIGHT = "#f4f4f3"
    MID = "#dededb"
    RED = "#ff4058"

    def font(size, bold=False):
        path = _font_path(bold)
        if path:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    F = {
        "brand": font(34, True),
        "h1": font(50, True),
        "h2": font(31, True),
        "h3": font(25, True),
        "body": font(19, False),
        "body_b": font(19, True),
        "small": font(15, False),
        "small_b": font(15, True),
        "level": font(68, True),
        "level_small": font(28, True),
    }

    def wrap(draw, text, fnt, max_width):
        words = str(text).split()
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            box = draw.textbbox((0, 0), trial, font=fnt)
            if box[2] - box[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def draw_wrapped(draw, xy, text, fnt, fill, max_width, line_gap=6):
        x, y = xy
        line_h = (draw.textbbox((0, 0), "Ag", font=fnt)[3] + line_gap)
        for line in wrap(draw, text, fnt, max_width):
            draw.text((x, y), line, font=fnt, fill=fill)
            y += line_h
        return y

    def paste_contain(canvas, image_path, box):
        x, y, w, h = box
        try:
            img = Image.open(image_path).convert("RGB")
            fitted = ImageOps.contain(img, (w, h), Image.Resampling.LANCZOS)
            px = x + (w - fitted.width) // 2
            py = y + (h - fitted.height) // 2
            canvas.paste(fitted, (px, py))
            return True
        except Exception:
            return False

    def background(page):
        draw = ImageDraw.Draw(page)
        draw.rounded_rectangle((-210, 220, 410, 1130), radius=180, fill=LIGHT)
        draw.rounded_rectangle((650, 330, 1280, 1190), radius=190, fill="#f6f6f5")
        draw.polygon([(170, 1540), (600, 1130), (790, 1540), (540, 1754), (0, 1754)], fill="#f5f5f4")
        draw.polygon([(810, 650), (1100, 360), (1240, 500), (1240, 1050)], fill="#f7f7f6")

    skill_map = {row["key"]: row for row in summary["skills"]}
    levels = {
        skill: _level(skill_map.get(skill, {}).get("percent"))
        for skill in ("reading", "writing", "speaking", "listening")
    }
    overall_level = _level(summary["overall_percent"])

    candidate = _candidate_name(attempt.user).upper()
    issued = (attempt.completed_at or attempt.started_at).strftime("%d-%m-%Y")
    candidate_id = f"ARYA-MOCK-{attempt.pk:06d}"
    logo_path = Path(settings.BASE_DIR) / "static/images/public/cambridge-b1/arya-academy-logo.jpg"
    photo_path = _photo_path(attempt.user)

    page1 = Image.new("RGB", (W, H), WHITE)
    background(page1)
    d = ImageDraw.Draw(page1)

    # Brand / report metadata.
    if logo_path.is_file():
        paste_contain(page1, logo_path, (55, 35, 250, 130))
    else:
        d.text((65, 55), "ARYA ACADEMY", font=F["brand"], fill=DARK)

    d.rounded_rectangle((625, 35, 875, 165), radius=0, fill=WHITE, outline=MID, width=3)
    d.rounded_rectangle((895, 35, 1155, 165), radius=0, fill=WHITE, outline=MID, width=3)
    d.text((660, 65), "DATE ISSUED", font=F["small_b"], fill=DARK)
    d.text((660, 105), issued, font=F["body"], fill=DARK)
    d.text((930, 65), "CANDIDATE ID", font=F["small_b"], fill=DARK)
    d.text((930, 105), candidate_id, font=F["small_b"], fill=DARK)

    d.rounded_rectangle((55, 180, 1155, 225), radius=10, fill="#fff1f3", outline="#ffc3cc", width=2)
    d.text((79, 192), "PRACTICE MOCK — NOT AN OFFICIAL CAMBRIDGE RESULT", font=F["small_b"], fill=RED)

    d.text((65, 265), "Practice Mock Test Report", font=F["h1"], fill=INK)
    d.text((65, 380), "Candidate name", font=F["small"], fill=MUTED)
    d.rectangle((65, 415, 790, 490), fill=TEAL_SOFT, outline=TEAL, width=5)
    d.text((90, 433), candidate, font=F["h3"], fill=INK)

    # Candidate photo / initials.
    photo_box = (865, 270, 280, 280)
    d.rectangle((photo_box[0], photo_box[1], photo_box[0]+photo_box[2], photo_box[1]+photo_box[3]), fill="#f1f3f5")
    if not (photo_path and paste_contain(page1, photo_path, photo_box)):
        initials = "".join(part[0] for part in candidate.split()[:2]) or "ST"
        d.text((944, 365), initials, font=F["level"], fill="#93a0b4")

    # Overall practice level circle.
    cx, cy, r = 255, 850, 155
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=TEAL_SOFT, outline=TEAL, width=7)
    d.text((160, 780), "Practice CEFR", font=F["small_b"], fill=INK)
    d.text((180, 812), "estimate", font=F["small"], fill=MUTED)
    level_box = d.textbbox((0, 0), overall_level, font=F["level"])
    d.text((cx - (level_box[2]-level_box[0])//2, 855), overall_level, font=F["level"], fill=INK)

    # Four skill blocks in the same 2x2 placement hierarchy.
    positions = {
        "reading": (525, 700),
        "writing": (825, 700),
        "speaking": (525, 895),
        "listening": (825, 895),
    }
    for skill in SKILL_ORDER_PAGE1:
        x, y = positions[skill]
        level = levels[skill]
        pct = skill_map.get(skill, {}).get("percent")
        d.text((x, y), skill.upper(), font=F["h3"], fill=INK)
        filled = {"A1": 1, "A2": 2, "B1": 3}[level]
        for i in range(3):
            x1 = x + i * 78
            d.rectangle((x1, y+55, x1+62, y+70), fill=TEAL if i < filled else "#6d6e71")
        label = f"{level} · {pct:.0f}%" if pct is not None else level
        d.text((x, y+92), label, font=F["body_b"], fill=INK)

    d.text((65, 1180), "These practice results suggest that the candidate can:", font=F["body_b"], fill=DARK)
    yy = 1225
    for skill in ("reading", "writing", "speaking", "listening"):
        statement = DESCRIPTORS[skill][levels[skill]]
        d.ellipse((73, yy+9, 82, yy+18), fill=INK)
        yy = draw_wrapped(d, (95, yy), statement, F["body"], INK, 1040, 5) + 4

    d.rounded_rectangle((65, 1500, 1155, 1625), radius=18, fill="#f7f9fc", outline="#e2e6ee", width=2)
    disclaimer = (
        "Arya Academy practice report only. Level labels are portal estimates based on internal practice score bands "
        "(A1 below 45%, A2 45–69.9%, B1 70%+). They are not official Cambridge scores or certificates."
    )
    draw_wrapped(d, (90, 1528), disclaimer, F["small"], MUTED, 1010, 4)
    d.text((65, 1680), "Arya Academy · Cambridge English Test Preparation Portal", font=F["small_b"], fill=INK)

    # Page 2 — descriptors.
    page2 = Image.new("RGB", (W, H), WHITE)
    background(page2)
    d2 = ImageDraw.Draw(page2)

    if logo_path.is_file():
        paste_contain(page2, logo_path, (55, 35, 220, 115))
    else:
        d2.text((65, 55), "ARYA ACADEMY", font=F["brand"], fill=DARK)

    d2.text((65, 210), "Practice CEFR Descriptors", font=F["h1"], fill=INK)
    d2.text((65, 280), "Internal guidance used to explain the practice level shown on page 1.", font=F["body"], fill=MUTED)
    d2.rounded_rectangle((65, 335, 1155, 385), radius=10, fill="#fff1f3", outline="#ffc3cc", width=2)
    d2.text((90, 348), "PRACTICE MOCK — NOT AN OFFICIAL CAMBRIDGE RESULT", font=F["small_b"], fill=RED)

    top = 445
    for skill in SKILL_ORDER_PAGE2:
        d2.text((65, top), skill.title(), font=F["h2"], fill=DARK)
        d2.line((65, top+48, 1155, top+48), fill="#b8bdc7", width=2)
        row_y = top + 65
        for level in ("A1", "A2", "B1"):
            d2.text((80, row_y), level, font=F["body_b"], fill=TEAL if level == levels[skill] else INK)
            statement = DESCRIPTORS[skill][level]
            row_y = draw_wrapped(d2, (175, row_y), statement, F["body"], INK, 930, 4) + 12
            d2.line((175, row_y-5, 1155, row_y-5), fill="#dedfe3", width=1)
        top = row_y + 28

    d2.rounded_rectangle((65, 1575, 1155, 1670), radius=16, fill="#f7f9fc", outline="#e2e6ee", width=2)
    draw_wrapped(
        d2,
        (90, 1597),
        "This descriptor page is a preparation aid. Arya Academy does not issue an official Cambridge qualification through this Mock Test.",
        F["small"],
        MUTED,
        1010,
        4,
    )
    d2.text((65, 1700), f"{candidate_id} · {candidate}", font=F["small_b"], fill=INK)

    output = BytesIO()
    page1.save(
        output,
        format="PDF",
        save_all=True,
        append_images=[page2],
        resolution=150.0,
    )
    return output.getvalue(), candidate_id


def _report_response(request, attempt_id, download):
    attempt = _owned(request, attempt_id)
    if not is_continuous_full_mock(attempt):
        raise Http404("Practice Mock Report is available only for Full Mock attempts.")

    summary = summary_for_attempt(attempt, sync=True)
    if summary["result_state"] != "ready":
        return redirect("results:attempt_report", attempt_id=attempt.pk)

    pdf_bytes, candidate_id = _build_pdf(summary["attempt"], summary)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    disposition = "attachment" if download else "inline"
    response["Content-Disposition"] = (
        f'{disposition}; filename="Arya_Academy_Practice_Mock_Report_{candidate_id}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def practice_report(request, attempt_id):
    return _report_response(request, attempt_id, download=False)


@login_required
def practice_report_download(request, attempt_id):
    return _report_response(request, attempt_id, download=True)
