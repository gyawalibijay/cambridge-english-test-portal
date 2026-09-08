from django import forms

from .models import PublicInquiry


class PublicInquiryForm(forms.ModelForm):
    class Meta:
        model = PublicInquiry
        fields = [
            "name",
            "email",
            "phone",
            "program_interest",
            "subject",
            "message",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "pv2-input",
                    "placeholder": "Your full name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "pv2-input",
                    "placeholder": "you@example.com",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "pv2-input",
                    "placeholder": "Phone number (optional)",
                }
            ),
            "program_interest": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "pv2-input",
                    "placeholder": "How can we help?",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 7,
                    "placeholder": "Write your message...",
                }
            ),
        }
