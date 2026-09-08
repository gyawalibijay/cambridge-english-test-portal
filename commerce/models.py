import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from assessments.models import Program


class AccessPackage(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    programs = models.ManyToManyField(
        Program,
        related_name="access_packages",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000,
    )
    currency = models.CharField(
        max_length=8,
        default="NPR",
    )
    access_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for lifetime access.",
    )
    payment_instructions = models.TextField(
        blank=True,
        default=(
            "Use one of the payment methods shown on the invoice page. "
            "Enter the generated invoice number exactly in the payment remarks, "
            "note, message, or reference field, then submit the transaction reference "
            "or receipt for verification."
        ),
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class PaymentDestination(models.Model):
    class Method(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        BANK = "bank", "Bank transfer"
        QR = "qr", "QR payment"
        OTHER = "other", "Other"

    title = models.CharField(max_length=120)
    method = models.CharField(max_length=24, choices=Method.choices)
    bank_name = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=140, blank=True)
    account_number = models.CharField(
        max_length=140,
        blank=True,
        help_text="Bank account number, wallet ID, phone number, or payment identifier.",
    )
    instructions = models.TextField(blank=True)
    qr_image = models.ImageField(
        upload_to="payments/qr/",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class Purchase(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Invoice generated"
        PENDING = "pending", "Pending verification"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        BANK = "bank", "Bank transfer"
        QR = "qr", "QR payment"
        CASH = "cash", "Cash / office payment"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="program_purchases",
    )
    package = models.ForeignKey(
        AccessPackage,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    invoice_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(
        max_length=8,
        default="NPR",
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=24,
        choices=PaymentMethod.choices,
        blank=True,
        default="",
    )
    transaction_reference = models.CharField(
        max_length=120,
        blank=True,
    )
    receipt = models.FileField(
        upload_to="payments/receipts/%Y/%m/",
        blank=True,
        null=True,
    )
    student_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_program_purchases",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def make_invoice_number(cls):
        # Student-facing invoice/reference: exactly five numeric digits.
        # Existing historic invoices remain valid; this only affects new invoices.
        for _ in range(500):
            candidate = f"{secrets.randbelow(90000) + 10000:05d}"
            if not cls.objects.filter(invoice_number=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate a unique 5-digit invoice number.")

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.make_invoice_number()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.user} - {self.package} - {self.status}"


class ProgramEntitlement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="program_entitlements",
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    source_purchase = models.ForeignKey(
        Purchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entitlements",
    )
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_program_entitlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "program"],
                name="unique_user_program_entitlement",
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.program}"

    @property
    def valid_now(self):
        if not self.is_active:
            return False

        if self.expires_at and self.expires_at <= timezone.now():
            return False

        return True
