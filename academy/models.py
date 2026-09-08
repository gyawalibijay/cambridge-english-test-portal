from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from assessments.models import Program


DOCUMENT_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "csv",
    "txt",
    "jpg",
    "jpeg",
    "png",
    "webp",
]

AUDIO_EXTENSIONS = [
    "mp3",
    "wav",
    "m4a",
    "ogg",
    "webm",
]


class Course(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="courses",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_courses",
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(
        max_length=255,
        blank=True,
    )
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(
        upload_to="courses/thumbnails/%Y/%m/",
        blank=True,
        null=True,
    )
    is_published = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "program__sort_order",
            "sort_order",
            "title",
        ]

    def __str__(self):
        return self.title


class CourseMaterial(models.Model):
    class Skill(models.TextChoices):
        GENERAL = "general", "General"
        SPEAKING = "speaking", "Speaking"
        LISTENING = "listening", "Listening"
        READING = "reading", "Reading"
        WRITING = "writing", "Writing"

    class MaterialType(models.TextChoices):
        TEXT = "text", "Text lesson"
        DOCUMENT = "document", "Document / PDF"
        AUDIO = "audio", "Audio lesson"
        VIDEO_LINK = "video_link", "Video link"
        DOWNLOAD = "download", "Downloadable file"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_course_materials",
    )
    skill = models.CharField(
        max_length=20,
        choices=Skill.choices,
        default=Skill.GENERAL,
    )
    material_type = models.CharField(
        max_length=24,
        choices=MaterialType.choices,
        default=MaterialType.TEXT,
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    content_text = models.TextField(blank=True)
    file = models.FileField(
        upload_to="courses/materials/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=DOCUMENT_EXTENSIONS
            )
        ],
    )
    audio_file = models.FileField(
        upload_to="courses/audio/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=AUDIO_EXTENSIONS
            )
        ],
    )
    external_url = models.URLField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "course",
            "sort_order",
            "title",
        ]

    def __str__(self):
        return f"{self.course} - {self.title}"


class TestMaterial(models.Model):
    class Skill(models.TextChoices):
        LISTENING = "listening", "Listening"
        READING = "reading", "Reading"
        WRITING = "writing", "Writing"

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="uploaded_test_materials",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_materials",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_test_materials",
    )
    skill = models.CharField(
        max_length=20,
        choices=Skill.choices,
    )
    title = models.CharField(max_length=180)
    instructions = models.TextField(blank=True)
    passage_text = models.TextField(
        blank=True,
        help_text="Reading passage or supporting text.",
    )
    prompt_text = models.TextField(
        blank=True,
        help_text="Writing prompt or question text.",
    )
    transcript = models.TextField(
        blank=True,
        help_text="Optional Listening transcript.",
    )
    audio_file = models.FileField(
        upload_to="test_materials/audio/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=AUDIO_EXTENSIONS
            )
        ],
    )
    attachment = models.FileField(
        upload_to="test_materials/files/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=DOCUMENT_EXTENSIONS
            )
        ],
    )
    answer_key = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional structured answer key.",
    )
    source_note = models.CharField(
        max_length=255,
        blank=True,
    )
    is_published = models.BooleanField(default=False)
    is_question_bank_ready = models.BooleanField(
        default=False,
        help_text=(
            "Mark when the material has been reviewed and is ready "
            "to be converted into question-bank items."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "program",
            "skill",
            "-created_at",
        ]

    def __str__(self):
        return f"{self.get_skill_display()} - {self.title}"
