from django.db import models

from assessments.models import Program, TestPart


class Stimulus(models.Model):
    """
    Shared source material for one or more questions.

    Examples:
    - Reading passage
    - Listening recording
    - Notice/email/article
    - Interview scenario
    """

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        AUDIO = "audio", "Audio"
        TEXT_AUDIO = "text_audio", "Text + Audio"
        SCENARIO = "scenario", "Scenario"

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="stimuli",
    )

    title = models.CharField(
        max_length=200,
    )

    stimulus_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.TEXT,
    )

    content = models.TextField(
        blank=True,
        help_text="Reading passage, notice, scenario, transcript, etc.",
    )

    audio_file = models.FileField(
        upload_to="question_bank/audio/",
        blank=True,
        null=True,
    )

    image_file = models.FileField(
        upload_to="question_bank/images/",
        blank=True,
        null=True,
    )

    transcript = models.TextField(
        blank=True,
        help_text=(
            "Optional audio transcript for administration/grading. "
            "Not automatically shown to students."
        ),
    )

    source_notes = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title


class Question(models.Model):

    class Skill(models.TextChoices):
        READING = "reading", "Reading"
        LISTENING = "listening", "Listening"
        WRITING = "writing", "Writing"
        SPEAKING = "speaking", "Speaking"
        INTERVIEW = "interview", "Interview"

    class Type(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Single Choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple Choice"
        SHORT_ANSWER = "short_answer", "Short Answer"
        GAP_FILL = "gap_fill", "Gap Fill"
        ORDERING = "ordering", "Ordering"
        LONG_TEXT = "long_text", "Long Written Response"
        RECORDED_RESPONSE = "recorded_response", "Recorded Response"
        READ_ALOUD = "read_aloud", "Read Aloud"
        INTERVIEW_RESPONSE = "interview_response", "Interview Response"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class CEFR(models.TextChoices):
        A1 = "A1", "A1"
        A2 = "A2", "A2"
        B1 = "B1", "B1"
        B2 = "B2", "B2"
        C1 = "C1", "C1"
        C2 = "C2", "C2"

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    stimulus = models.ForeignKey(
        Stimulus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )

    title = models.CharField(
        max_length=200,
        help_text="Internal/admin title for identifying the question.",
    )

    skill = models.CharField(
        max_length=20,
        choices=Skill.choices,
    )

    question_type = models.CharField(
        max_length=30,
        choices=Type.choices,
    )

    prompt_text = models.TextField(
        blank=True,
        help_text="The actual question or instruction.",
    )

    prompt_audio = models.FileField(
        upload_to="question_bank/question_audio/",
        blank=True,
        null=True,
    )

    prompt_image = models.FileField(
        upload_to="question_bank/question_images/",
        blank=True,
        null=True,
    )

    show_prompt_text = models.BooleanField(
        default=True,
        help_text=(
            "Disable this when the question should be heard "
            "but not displayed to the student."
        ),
    )

    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )

    cefr_level = models.CharField(
        max_length=2,
        choices=CEFR.choices,
        blank=True,
    )

    default_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    automatic_marking = models.BooleanField(
        default=False,
    )

    ai_grading_required = models.BooleanField(
        default=False,
    )

    manual_review_allowed = models.BooleanField(
        default=True,
    )

    preparation_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional override of the Test Part preparation timer.",
    )

    response_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional override of the Test Part response timer.",
    )

    min_word_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    max_word_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    explanation = models.TextField(
        blank=True,
        help_text="Optional answer explanation visible after grading.",
    )

    evaluator_notes = models.TextField(
        blank=True,
        help_text="Private notes/rubric guidance for evaluators.",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["program", "skill", "id"]

    def __str__(self):
        return self.title


class QuestionOption(models.Model):
    """
    Options for single-choice and multiple-choice questions.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )

    text = models.TextField()

    is_correct = models.BooleanField(
        default=False,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=["question", "order"],
                name="unique_option_order_per_question",
            )
        ]

    def __str__(self):
        return self.text[:80]


class AcceptableAnswer(models.Model):
    """
    Accepted answers for short answer / gap-fill questions.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="acceptable_answers",
    )

    answer_text = models.CharField(
        max_length=500,
    )

    case_sensitive = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return self.answer_text


class OrderingItem(models.Model):
    """
    Items used in ordering/rearrangement questions.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="ordering_items",
    )

    text = models.TextField()

    correct_position = models.PositiveIntegerField()

    class Meta:
        ordering = ["correct_position"]

        constraints = [
            models.UniqueConstraint(
                fields=["question", "correct_position"],
                name="unique_ordering_position_per_question",
            )
        ]

    def __str__(self):
        return f"{self.correct_position}. {self.text[:60]}"


class PartQuestion(models.Model):
    """
    Connects Question Bank questions to a specific test part.

    This lets one Question Bank item be reused in multiple mock tests.
    """

    part = models.ForeignKey(
        TestPart,
        on_delete=models.CASCADE,
        related_name="question_assignments",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="part_assignments",
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    points_override = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    is_required = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=["part", "question"],
                name="unique_question_per_part",
            ),
            models.UniqueConstraint(
                fields=["part", "order"],
                name="unique_question_order_per_part",
            ),
        ]

    def __str__(self):
        return f"{self.part} - {self.question}"
