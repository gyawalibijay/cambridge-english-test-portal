from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        EVALUATOR = "evaluator", "Evaluator"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return self.get_full_name() or self.username


class StudentProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    gender = models.CharField(
        max_length=32,
        choices=Gender.choices,
        blank=True,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=80, blank=True, default="Nepal")
    city_address = models.CharField(max_length=180, blank=True)

    profile_photo = models.ImageField(
        upload_to="profiles/photos/%Y/%m/",
        blank=True,
        null=True,
        help_text="Student profile photo. This can later be reused for certificate generation.",
    )
    certificate_name = models.CharField(
        max_length=160,
        blank=True,
        help_text="Name exactly as the student wants it to appear on a future certificate.",
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
    )
    preferred_language = models.CharField(
        max_length=20,
        choices=[
            ("english", "English"),
            ("nepali", "Nepali"),
        ],
        default="english",
    )
    email_notifications = models.BooleanField(
        default=True,
    )
    result_notifications = models.BooleanField(
        default=True,
    )
    agreed_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    email_verified_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the student verified their login email by OTP.",
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} profile"

class EmailVerificationOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_otps",
    )
    code_hash = models.CharField(max_length=255)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(blank=True, null=True)
    requested_ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Email OTP for {self.user}"

