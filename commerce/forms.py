from pathlib import Path

from django import forms

from .models import PaymentDestination, Purchase


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            "payment_method",
            "transaction_reference",
            "receipt",
            "student_note",
        ]
        labels = {
            "payment_method": "How did you pay?",
            "transaction_reference": "Transaction / payment reference",
            "receipt": "Payment receipt or screenshot",
            "student_note": "Note to verification team",
        }
        widgets = {
            "payment_method": forms.Select(
                attrs={"class": "pay-input"}
            ),
            "transaction_reference": forms.TextInput(
                attrs={
                    "class": "pay-input",
                    "placeholder": "Bank / eSewa / Khalti transaction reference",
                    "autocomplete": "off",
                }
            ),
            "receipt": forms.ClearableFileInput(
                attrs={
                    "class": "pay-input pay-file",
                    "accept": ".jpg,.jpeg,.png,.pdf,.webp",
                }
            ),
            "student_note": forms.Textarea(
                attrs={
                    "class": "pay-input",
                    "rows": 4,
                    "placeholder": "Optional note about your payment",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_methods = set(
            PaymentDestination.objects
            .filter(is_active=True)
            .values_list("method", flat=True)
        )
        if active_methods:
            allowed = [
                choice
                for choice in Purchase.PaymentMethod.choices
                if choice[0] in active_methods or choice[0] == Purchase.PaymentMethod.OTHER
            ]
            self.fields["payment_method"].choices = [
                ("", "Select payment method"),
                *allowed,
            ]
        else:
            self.fields["payment_method"].choices = [
                ("", "Select payment method"),
                *Purchase.PaymentMethod.choices,
            ]

    def clean_receipt(self):
        receipt = self.cleaned_data.get("receipt")
        if not receipt:
            return receipt

        if receipt.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Receipt file must be 8 MB or smaller.")

        suffix = Path(receipt.name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".pdf", ".webp"}:
            raise forms.ValidationError("Upload a JPG, PNG, WEBP, or PDF receipt.")

        return receipt

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("payment_method"):
            self.add_error("payment_method", "Choose how you made the payment.")

        if not cleaned.get("transaction_reference") and not cleaned.get("receipt"):
            raise forms.ValidationError(
                "Enter the payment transaction reference or upload a receipt/screenshot."
            )
        return cleaned
