#!/bin/bash

set -e

echo "=========================================="
echo "Unified English Portal - Step 9"
echo "Core Assessment Architecture"
echo "=========================================="

cd ~/unified-english-portal
source .venv/bin/activate


echo ""
echo "[1/5] Creating assessment models..."

cat > assessments/models.py <<'PYTHON'
from django.conf import settings
from django.db import models


class Program(models.Model):
    """
    Main examination/practice program.

    Examples:
    - Cambridge / General English
    - IELTS Academic
    - IELTS General Training
    - UK Student / UKVI Interview
    """

    code = models.SlugField(
        max_length=60,
        unique=True,
    )

    name = models.CharField(
        max_length=150,
    )

    short_name = models.CharField(
        max_length=80,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class MockTest(models.Model):
    """
    A complete mock test belonging to one program.
    """

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="mock_tests",
    )

    title = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=220,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    instructions = models.TextField(
        blank=True,
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional total expected test duration.",
    )

    is_published = models.BooleanField(
        default=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_mock_tests",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["program", "-created_at"]

    def __str__(self):
        return f"{self.program.name} - {self.title}"


class TestSection(models.Model):

    class Skill(models.TextChoices):
        READING = "reading", "Reading"
        LISTENING = "listening", "Listening"
        WRITING = "writing", "Writing"
        SPEAKING = "speaking", "Speaking"
        INTERVIEW = "interview", "Interview"

    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="sections",
    )

    title = models.CharField(
        max_length=150,
    )

    skill = models.CharField(
        max_length=20,
        choices=Skill.choices,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    instructions = models.TextField(
        blank=True,
    )

    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional section timer in seconds.",
    )

    can_pause = models.BooleanField(
        default=False,
    )

    is_required = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=["mock_test", "order"],
                name="unique_section_order_per_test",
            )
        ]

    def __str__(self):
        return f"{self.mock_test.title} - {self.title}"


class TestPart(models.Model):

    class PromptMode(models.TextChoices):
        TEXT = "text", "Text"
        AUDIO = "audio", "Audio"
        TEXT_AUDIO = "text_audio", "Text + Audio"

    section = models.ForeignKey(
        TestSection,
        on_delete=models.CASCADE,
        related_name="parts",
    )

    title = models.CharField(
        max_length=150,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    instructions = models.TextField(
        blank=True,
    )

    prompt_mode = models.CharField(
        max_length=20,
        choices=PromptMode.choices,
        default=PromptMode.TEXT,
    )

    question_visible = models.BooleanField(
        default=True,
        help_text="Turn off when the candidate should hear but not see the question.",
    )

    preparation_seconds = models.PositiveIntegerField(
        default=0,
    )

    response_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    question_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    max_audio_plays = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave empty when no specific playback restriction is required.",
    )

    recording_required = models.BooleanField(
        default=False,
    )

    min_word_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=["section", "order"],
                name="unique_part_order_per_section",
            )
        ]

    def __str__(self):
        return f"{self.section.title} - {self.title}"
PYTHON


echo ""
echo "[2/5] Configuring Django Admin..."

cat > assessments/admin.py <<'PYTHON'
from django.contrib import admin

from .models import Program, MockTest, TestSection, TestPart


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "sort_order",
    )

    list_editable = (
        "is_active",
        "sort_order",
    )

    search_fields = (
        "name",
        "code",
    )


class TestPartInline(admin.TabularInline):
    model = TestPart
    extra = 0


@admin.register(TestSection)
class TestSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "skill",
        "order",
        "duration_seconds",
    )

    list_filter = (
        "skill",
        "mock_test__program",
    )

    search_fields = (
        "title",
        "mock_test__title",
    )

    inlines = [
        TestPartInline,
    ]


class TestSectionInline(admin.TabularInline):
    model = TestSection
    extra = 0
    show_change_link = True


@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program",
        "duration_minutes",
        "is_published",
        "created_at",
    )

    list_filter = (
        "program",
        "is_published",
    )

    search_fields = (
        "title",
        "description",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    inlines = [
        TestSectionInline,
    ]


@admin.register(TestPart)
class TestPartAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "section",
        "order",
        "preparation_seconds",
        "response_seconds",
        "question_visible",
        "recording_required",
    )

    list_filter = (
        "section__skill",
        "question_visible",
        "recording_required",
    )

    search_fields = (
        "title",
        "section__title",
        "section__mock_test__title",
    )
PYTHON


echo ""
echo "[3/5] Creating database migration..."

python manage.py makemigrations assessments

python manage.py migrate


echo ""
echo "[4/5] Creating the four portal programs..."

python manage.py shell <<'PYTHON'
from assessments.models import Program

programs = [
    {
        "code": "cambridge-general",
        "name": "Cambridge / General English",
        "short_name": "Cambridge English",
        "description": (
            "General English mock testing including Reading, Listening, "
            "Writing and Speaking."
        ),
        "sort_order": 1,
    },
    {
        "code": "ielts-academic",
        "name": "IELTS Academic",
        "short_name": "IELTS Academic",
        "description": (
            "IELTS Academic practice tests covering Listening, Reading, "
            "Writing and Speaking."
        ),
        "sort_order": 2,
    },
    {
        "code": "ielts-general",
        "name": "IELTS General Training",
        "short_name": "IELTS General",
        "description": (
            "IELTS General Training practice tests covering Listening, "
            "Reading, Writing and Speaking."
        ),
        "sort_order": 3,
    },
    {
        "code": "ukvi-interview",
        "name": "UK Student / UKVI Interview Practice",
        "short_name": "UKVI Interview",
        "description": (
            "Practice interviews and readiness assessment for UK student "
            "and UKVI-style interview preparation."
        ),
        "sort_order": 4,
    },
]

for data in programs:
    program, created = Program.objects.update_or_create(
        code=data["code"],
        defaults=data,
    )

    status = "CREATED" if created else "UPDATED"

    print(f"{status}: {program.name}")
PYTHON


echo ""
echo "[5/5] Running checks..."

python manage.py check

echo ""
echo "Programs currently available:"
echo ""

python manage.py shell <<'PYTHON'
from assessments.models import Program

for program in Program.objects.all():
    print(
        f"{program.sort_order}. "
        f"{program.name} "
        f"({program.code})"
    )
PYTHON


echo ""
echo "=========================================="
echo "STEP 9 COMPLETED SUCCESSFULLY"
echo "=========================================="
