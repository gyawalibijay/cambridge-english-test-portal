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

    minimum_response_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Optional minimum response duration when the source specifies "
            "a minimum rather than a fixed timer."
        ),
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
