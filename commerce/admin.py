from pathlib import Path

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import AccessPackage, PaymentDestination, ProgramEntitlement, Purchase
from .services import approve_purchase


STATUS_STYLE = {
    Purchase.Status.INITIATED: ("#475467", "#f2f4f7", "Invoice generated"),
    Purchase.Status.PENDING: ("#b54708", "#fffaeb", "Pending verification"),
    Purchase.Status.APPROVED: ("#067647", "#ecfdf3", "Approved"),
    Purchase.Status.REJECTED: ("#b42318", "#fef3f2", "Rejected"),
    Purchase.Status.CANCELLED: ("#475467", "#f2f4f7", "Cancelled"),
}


class PurchaseReviewForm(forms.ModelForm):
    class Decision:
        KEEP = ""
        APPROVE = "approve"
        REJECT = "reject"

    verification_decision = forms.ChoiceField(
        required=False,
        label="Verification decision",
        choices=(
            (Decision.KEEP, "No decision / save admin note only"),
            (Decision.APPROVE, "Approve payment and grant course access"),
            (Decision.REJECT, "Reject payment"),
        ),
        help_text=(
            "Approval always goes through the entitlement service so course access "
            "is granted correctly. Status is intentionally not directly editable."
        ),
    )

    class Meta:
        model = Purchase
        exclude = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "admin_note" in self.fields:
            self.fields["admin_note"].label = "Admin verification note"
            self.fields["admin_note"].help_text = (
                "Add your internal verification note. A rejection requires a reason."
            )
            self.fields["admin_note"].widget.attrs.update({"rows": 4})

        if (
            self.instance
            and self.instance.pk
            and self.instance.status != Purchase.Status.PENDING
        ):
            self.fields["verification_decision"].choices = (
                (self.Decision.KEEP, "No action available — payment is not pending"),
            )
            self.fields["verification_decision"].help_text = (
                "Only payments with Pending verification status can be approved or rejected."
            )

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get("verification_decision")
        admin_note = (cleaned.get("admin_note") or "").strip()

        if decision == self.Decision.REJECT and not admin_note:
            self.add_error(
                "admin_note",
                "Add a short reason before rejecting a student's payment.",
            )

        return cleaned


@admin.register(AccessPackage)
class AccessPackageAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "program_names",
        "price",
        "currency",
        "access_days_display",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "currency", "programs")
    search_fields = ("title", "slug", "programs__name", "programs__code")
    filter_horizontal = ("programs",)
    list_editable = ("is_active", "sort_order")
    readonly_fields = ("created_at", "updated_at")
    save_on_top = True

    fieldsets = (
        (
            "Course access package",
            {
                "fields": (
                    "title",
                    "slug",
                    "programs",
                    "short_description",
                    "description",
                )
            },
        ),
        (
            "Price and access",
            {
                "fields": (
                    "price",
                    "currency",
                    "access_days",
                    "payment_instructions",
                )
            },
        ),
        (
            "Availability",
            {
                "fields": ("is_active", "sort_order"),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Programs")
    def program_names(self, obj):
        names = list(obj.programs.values_list("short_name", flat=True))
        names = [name for name in names if name]
        if not names:
            names = list(obj.programs.values_list("name", flat=True))
        return ", ".join(names) or "—"

    @admin.display(description="Access")
    def access_days_display(self, obj):
        return f"{obj.access_days} days" if obj.access_days else "Lifetime"


@admin.register(PaymentDestination)
class PaymentDestinationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "method",
        "bank_name",
        "account_name",
        "account_number",
        "qr_state",
        "is_active",
        "sort_order",
    )
    list_filter = ("method", "is_active")
    search_fields = (
        "title",
        "bank_name",
        "account_name",
        "account_number",
        "instructions",
    )
    list_editable = ("is_active", "sort_order")
    readonly_fields = ("qr_preview", "created_at", "updated_at")
    save_on_top = True

    fieldsets = (
        (
            "Payment option",
            {
                "fields": (
                    "title",
                    "method",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            "Account / wallet details",
            {
                "fields": (
                    "bank_name",
                    "account_name",
                    "account_number",
                    "instructions",
                )
            },
        ),
        (
            "QR payment",
            {
                "fields": ("qr_image", "qr_preview"),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="QR")
    def qr_state(self, obj):
        return "Uploaded" if obj.qr_image else "—"

    @admin.display(description="QR preview")
    def qr_preview(self, obj):
        if not obj or not obj.qr_image:
            return format_html(
                '<span style="color:#667085">No QR image uploaded.</span>'
            )
        return format_html(
            '<img src="{}" alt="Payment QR" style="width:240px;max-width:100%;'
            'height:auto;border:1px solid #d0d5dd;border-radius:12px;'
            'background:#fff;padding:8px">',
            obj.qr_image.url,
        )


@admin.action(description="Approve selected pending payments + grant access")
def approve_selected(modeladmin, request, queryset):
    approved = 0
    skipped = 0

    for purchase in queryset.select_related("package", "user"):
        if purchase.status != Purchase.Status.PENDING:
            skipped += 1
            continue
        approve_purchase(purchase, reviewer=request.user)
        approved += 1

    if approved:
        messages.success(
            request,
            f"Approved {approved} payment(s) and granted the related course access.",
        )
    if skipped:
        messages.warning(
            request,
            f"Skipped {skipped} item(s) because they were not pending verification.",
        )



@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    form = PurchaseReviewForm
    list_display = (
        "invoice_number",
        "student_identity",
        "package",
        "amount_display",
        "status_badge",
        "payment_method_display",
        "transaction_reference",
        "receipt_state",
        "submitted_at",
        "reviewed_by",
    )
    list_display_links = ("invoice_number", "student_identity")
    list_filter = (
        "status",
        "payment_method",
        "package",
        "submitted_at",
        "reviewed_at",
    )
    search_fields = (
        "invoice_number",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "transaction_reference",
        "student_note",
        "admin_note",
    )
    readonly_fields = (
        "invoice_number",
        "student_identity_detail",
        "user",
        "package",
        "amount",
        "currency",
        "status_badge",
        "payment_method",
        "transaction_reference",
        "receipt",
        "receipt_preview",
        "student_note",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
    )
    actions = (approve_selected,)
    list_select_related = ("user", "package", "reviewed_by")
    list_per_page = 50
    date_hierarchy = "submitted_at"
    save_on_top = True
    actions_on_top = True
    actions_on_bottom = False
    empty_value_display = "—"

    fieldsets = (
        (
            "Payment verification summary",
            {
                "description": (
                    "Check the invoice number, student, amount and submitted evidence. "
                    "Then choose Approve or Reject below. Approval automatically grants "
                    "the package's program access."
                ),
                "fields": (
                    "status_badge",
                    "invoice_number",
                    "student_identity_detail",
                    "user",
                    "package",
                    "amount",
                    "currency",
                ),
            },
        ),
        (
            "Student payment evidence",
            {
                "fields": (
                    "payment_method",
                    "transaction_reference",
                    "receipt",
                    "receipt_preview",
                    "student_note",
                    "submitted_at",
                )
            },
        ),
        (
            "Manual review",
            {
                "description": (
                    "Status is protected from direct editing. Use this decision field "
                    "so approval always goes through the access-granting service."
                ),
                "fields": (
                    "verification_decision",
                    "admin_note",
                )
            },
        ),
        (
            "Review audit",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        # Purchases should originate from a real student invoice/payment flow.
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep a durable payment audit trail.
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "package", "reviewed_by")
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "title": "Manual payment verification",
        }
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "title": "Review student payment",
        }
        return super().change_view(
            request,
            object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def save_model(self, request, obj, form, change):
        decision = form.cleaned_data.get("verification_decision", "")

        # Save only legitimate editable admin fields first (primarily admin_note).
        # Status is excluded from the form, so it cannot be accidentally changed.
        super().save_model(request, obj, form, change)

        if decision == PurchaseReviewForm.Decision.APPROVE:
            if obj.status == Purchase.Status.PENDING:
                approve_purchase(obj, reviewer=request.user)
                messages.success(
                    request,
                    "Payment approved. Course access was granted automatically.",
                )
            else:
                messages.warning(
                    request,
                    "Approval was not applied because this payment is not pending verification.",
                )

        elif decision == PurchaseReviewForm.Decision.REJECT:
            if obj.status == Purchase.Status.PENDING:
                obj.status = Purchase.Status.REJECTED
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
                obj.save(
                    update_fields=[
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                        "admin_note",
                        "updated_at",
                    ]
                )
                messages.success(request, "Payment rejected.")
            else:
                messages.warning(
                    request,
                    "Rejection was not applied because this payment is not pending verification.",
                )

    @admin.display(description="Student")
    def student_identity(self, obj):
        name = obj.user.get_full_name().strip() or obj.user.username
        email = obj.user.email or ""
        if email:
            return format_html(
                '<strong>{}</strong><br><span style="font-size:11px;color:#667085">{}</span>',
                name,
                email,
            )
        return name

    @admin.display(description="Student details")
    def student_identity_detail(self, obj):
        name = obj.user.get_full_name().strip() or obj.user.username
        email = obj.user.email or "No email"
        return format_html(
            '<div style="line-height:1.6"><strong>{}</strong><br>'
            '<span style="color:#667085">{}</span></div>',
            name,
            email,
        )

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return f"{obj.currency} {obj.amount:,.0f}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        fg, bg, label = STATUS_STYLE.get(
            obj.status,
            ("#475467", "#f2f4f7", obj.get_status_display()),
        )
        return format_html(
            '<span style="display:inline-block;padding:4px 9px;border-radius:999px;'
            'font-size:11px;font-weight:800;color:{};background:{}">{}</span>',
            fg,
            bg,
            label,
        )

    @admin.display(description="Method")
    def payment_method_display(self, obj):
        return obj.get_payment_method_display() if obj.payment_method else "—"

    @admin.display(description="Receipt")
    def receipt_state(self, obj):
        if obj.receipt:
            return format_html(
                '<span style="color:#067647;font-weight:700">✓ Attached</span>'
            )
        if obj.status == Purchase.Status.PENDING:
            return format_html(
                '<span style="color:#b54708;font-weight:700">No file</span>'
            )
        return "—"

    @admin.display(description="Receipt / proof preview")
    def receipt_preview(self, obj):
        if not obj or not obj.receipt:
            return format_html(
                '<span style="color:#667085">No receipt file attached.</span>'
            )

        try:
            url = obj.receipt.url
        except Exception:
            return format_html(
                '<span style="color:#b42318">Receipt exists but its storage URL is unavailable.</span>'
            )

        suffix = Path(obj.receipt.name or "").suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            return format_html(
                '<div style="max-width:700px">'
                '<a href="{}" target="_blank" rel="noopener">'
                '<img src="{}" alt="Payment receipt" style="max-width:100%;max-height:520px;'
                'object-fit:contain;border:1px solid #d0d5dd;border-radius:12px;'
                'background:#fff;padding:8px"></a>'
                '<div style="margin-top:6px"><a href="{}" target="_blank" rel="noopener">'
                'Open original receipt ↗</a></div></div>',
                url,
                url,
                url,
            )

        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'style="font-weight:700">Open payment proof ↗</a>',
            url,
        )


@admin.register(ProgramEntitlement)
class ProgramEntitlementAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "program",
        "is_active",
        "starts_at",
        "expires_at",
        "source_invoice",
        "granted_by",
    )
    list_filter = (
        "is_active",
        "program",
        "starts_at",
        "expires_at",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "program__name",
        "program__code",
        "source_purchase__invoice_number",
    )
    autocomplete_fields = ("user", "program", "source_purchase", "granted_by")
    readonly_fields = ("created_at",)
    list_select_related = (
        "user",
        "program",
        "source_purchase",
        "granted_by",
    )
    list_per_page = 50

    @admin.display(description="Invoice")
    def source_invoice(self, obj):
        return (
            obj.source_purchase.invoice_number
            if obj.source_purchase
            else "Manual grant"
        )
