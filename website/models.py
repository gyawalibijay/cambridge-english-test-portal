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


class PublicSiteSettings(models.Model):
    """Editable public-site copy and branding (single row)."""

    site_name = models.CharField(max_length=90, default="Upskill")
    brand_tagline = models.CharField(
        max_length=120,
        default="English Test Preparation",
    )
    logo = models.FileField(
        upload_to="website/branding/",
        blank=True,
        null=True,
        help_text="Upload PNG, WebP or SVG. A text logo is used when empty.",
    )
    mascot_image = models.ImageField(
        upload_to="website/branding/",
        blank=True,
        null=True,
        help_text=(
            "Optional homepage/program mascot image. A bundled mascot is used "
            "when this is empty."
        ),
    )
    mascot_alt_text = models.CharField(
        max_length=160,
        default="Upskill student preparation guide",
    )
    show_mascot = models.BooleanField(
        default=True,
        help_text="Show the mascot on the public home and program landing pages.",
    )
    announcement_text = models.CharField(
        max_length=180,
        default="Cambridge English • IELTS • UK Interview",
    )
    hero_eyebrow = models.CharField(
        max_length=140,
        default="ONE PORTAL. THREE ENGLISH GOALS.",
    )
    hero_title = models.CharField(
        max_length=150,
        default="Choose your English test.",
    )
    hero_highlight = models.CharField(
        max_length=150,
        default="Practise with confidence.",
    )
    hero_description = models.TextField(
        default=(
            "Cambridge English, IELTS and UK Interview preparation with focused "
            "practice, mock tests and clear progress."
        )
    )
    primary_cta_label = models.CharField(
        max_length=60,
        default="Create free account",
    )
    primary_cta_url = models.CharField(max_length=300, default="/signup/")
    secondary_cta_label = models.CharField(
        max_length=60,
        default="Explore programs",
    )
    secondary_cta_url = models.CharField(max_length=300, default="#programs")
    trust_note = models.CharField(
        max_length=180,
        default="Independent practice portal with admin-managed learning content",
    )
    whatsapp_number = models.CharField(
        max_length=30,
        blank=True,
        help_text="Include country code, for example 97798XXXXXXXX.",
    )
    whatsapp_label = models.CharField(
        max_length=80,
        default="24/7 Student Support",
    )
    whatsapp_message = models.CharField(
        max_length=220,
        default="Hello, I need help choosing an English preparation program.",
    )
    footer_text = models.CharField(
        max_length=220,
        default="Focused preparation for English tests and UK student interviews.",
    )
    seo_title = models.CharField(
        max_length=180,
        default=(
            "Upskill English Test Preparation | Cambridge, IELTS & UK Interview"
        ),
    )
    seo_description = models.CharField(
        max_length=320,
        default=(
            "Prepare online for Cambridge English, IELTS Academic and General "
            "Training, and UK student interviews with realistic practice, mock "
            "tests, learning materials and progress tracking."
        ),
    )
    seo_keywords = models.TextField(
        default=(
            "Cambridge English practice test online, Cambridge English mock test, "
            "CEFR B1 speaking practice, IELTS preparation Nepal, IELTS Academic "
            "mock test, IELTS General Training practice, IELTS online practice, "
            "UK student interview preparation, UK visa interview practice, "
            "English mock test online, English test preparation Nepal"
        )
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Public site settings"
        verbose_name_plural = "Public site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Public site settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PublicProgramLanding(models.Model):
    class ProgramKey(models.TextChoices):
        CAMBRIDGE = "cambridge-english", "Cambridge English"
        IELTS = "ielts", "IELTS"
        UK_INTERVIEW = "uk-interview", "UK Interview"

    class StatusTone(models.TextChoices):
        LIVE = "live", "Live / available"
        SOON = "soon", "Coming soon"
        INFO = "info", "Information"

    program_key = models.SlugField(
        max_length=40,
        unique=True,
        choices=ProgramKey.choices,
    )
    name = models.CharField(max_length=90)
    short_label = models.CharField(max_length=40)
    card_kicker = models.CharField(max_length=90)
    card_title = models.CharField(max_length=120)
    card_summary = models.CharField(max_length=260)
    card_image = models.FileField(
        upload_to="website/programs/cards/",
        blank=True,
        null=True,
    )
    card_image_alt = models.CharField(max_length=160, blank=True)
    cursor_label = models.CharField(max_length=40, default="Explore")
    status_label = models.CharField(max_length=40, default="Explore")
    status_tone = models.CharField(
        max_length=12,
        choices=StatusTone.choices,
        default=StatusTone.INFO,
    )
    hero_eyebrow = models.CharField(max_length=120)
    hero_title = models.CharField(max_length=180)
    hero_description = models.TextField()
    hero_image = models.FileField(
        upload_to="website/programs/heroes/",
        blank=True,
        null=True,
    )
    hero_image_alt = models.CharField(max_length=160, blank=True)
    audience_title = models.CharField(max_length=100, default="Who this is for")
    audience_text = models.TextField()
    format_title = models.CharField(max_length=100, default="What you will practise")
    format_text = models.TextField()
    benefit_one_title = models.CharField(max_length=90)
    benefit_one_text = models.CharField(max_length=220)
    benefit_two_title = models.CharField(max_length=90)
    benefit_two_text = models.CharField(max_length=220)
    benefit_three_title = models.CharField(max_length=90)
    benefit_three_text = models.CharField(max_length=220)
    primary_cta_label = models.CharField(max_length=60, default="Start preparing")
    primary_cta_url = models.CharField(max_length=300, default="/signup/")
    secondary_cta_label = models.CharField(max_length=60, default="Ask a question")
    secondary_cta_url = models.CharField(max_length=300, default="/contact/")
    seo_title = models.CharField(max_length=180)
    seo_description = models.CharField(max_length=320)
    seo_keywords = models.TextField()
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Public program landing page"
        verbose_name_plural = "Public program landing pages"

    def __str__(self):
        return self.name
