from pathlib import Path

from django.conf import settings
from django.db import models

from assessments.models import MockTest, TestPart
from question_bank.models import Question


def response_audio_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower() or ".webm"
    attempt = instance.attempt_question.attempt
    return (
        f"responses/user_{attempt.user_id}/attempt_{attempt.id}/"
        f"question_{instance.attempt_question_id}{suffix}"
    )


class TestAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        GRADING = "grading", "Grading"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="test_attempts",
    )
    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    overall_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["mock_test", "status"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.mock_test} - {self.started_at:%Y-%m-%d %H:%M}"


class AttemptQuestion(models.Model):
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="attempt_questions",
    )
    part = models.ForeignKey(
        TestPart,
        on_delete=models.PROTECT,
        related_name="attempt_questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="attempt_questions",
    )
    order = models.PositiveIntegerField()
    points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "order"],
                name="unique_attempt_question_order",
            ),
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_question_per_attempt",
            ),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - Q{self.order}"


class StudentResponse(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTO_GRADED = "auto_graded", "Auto graded"
        AI_QUEUED = "ai_queued", "AI queued"
        AI_GRADED = "ai_graded", "AI graded"
        REVIEWED = "reviewed", "Reviewed"

    attempt_question = models.OneToOneField(
        AttemptQuestion,
        on_delete=models.CASCADE,
        related_name="response",
    )
    text_response = models.TextField(blank=True)
    answer_data = models.JSONField(default=dict, blank=True)
    audio_response = models.FileField(
        upload_to=response_audio_upload_to,
        null=True,
        blank=True,
    )
    duration_seconds = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(null=True, blank=True)
    auto_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    ai_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    evaluator_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    final_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    feedback = models.TextField(blank=True)
    ai_feedback = models.JSONField(default=dict, blank=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_responses",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Response to {self.attempt_question}"
