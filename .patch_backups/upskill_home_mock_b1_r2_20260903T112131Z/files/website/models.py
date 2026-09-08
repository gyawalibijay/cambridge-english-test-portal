from django.db import models


class PublicInquiry(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    class ProgramInterest(models.TextChoices):
        GENERAL = "general", "General enquiry"
        CAMBRIDGE = "cambridge", "Cambridge / General English"
        IELTS_ACADEMIC = "ielts_academic", "IELTS Academic"
        IELTS_GENERAL = "ielts_general", "IELTS General Training"
        UKVI = "ukvi", "UK Student / UKVI Interview"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    program_interest = models.CharField(
        max_length=32,
        choices=ProgramInterest.choices,
        default=ProgramInterest.GENERAL,
    )
    subject = models.CharField(max_length=180)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.subject}"
