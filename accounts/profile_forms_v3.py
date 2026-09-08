from django import forms
from django.db import transaction

from .models import StudentProfile

BASE = {
    "class": "pv2-input",
}


class StudentProfileSettingsForm(forms.Form):
    first_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "First name",
            "autocomplete": "given-name",
        }),
    )
    last_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "Last name",
            "autocomplete": "family-name",
        }),
    )
    certificate_name = forms.CharField(
        required=False,
        max_length=160,
        label="Certificate name",
        help_text=(
            "Use the exact name you want printed on certificates later. "
            "You can change it before certificate generation."
        ),
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "Full name for future certificates",
        }),
    )
    profile_photo = forms.ImageField(
        required=False,
        label="Profile photo",
        help_text=(
            "JPG, PNG or WEBP. Maximum 5 MB. "
            "This photo can later be reused for certificate generation."
        ),
        widget=forms.ClearableFileInput(attrs={
            "class": "pv2-input profile-photo-input",
            "accept": "image/jpeg,image/png,image/webp",
        }),
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            **BASE,
            "type": "date",
        }),
    )
    gender = forms.ChoiceField(
        required=False,
        choices=[("", "Prefer not to specify")] + list(StudentProfile.Gender.choices),
        widget=forms.Select(attrs=BASE),
    )
    phone_number = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "+977...",
            "autocomplete": "tel",
        }),
    )
    country = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "Country",
            "autocomplete": "country-name",
        }),
    )
    city_address = forms.CharField(
        required=False,
        max_length=180,
        label="City / address",
        widget=forms.TextInput(attrs={
            **BASE,
            "placeholder": "City / address",
            "autocomplete": "street-address",
        }),
    )
    preferred_language = forms.ChoiceField(
        choices=[
            ("english", "English"),
            ("nepali", "Nepali"),
        ],
        label="Communication language",
        widget=forms.Select(attrs=BASE),
    )
    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="Email notifications",
    )
    result_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="Result notifications",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    @classmethod
    def from_user(cls, user, *args, **kwargs):
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        initial = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "certificate_name": (
                profile.certificate_name
                or user.get_full_name()
                or user.username
            ),
            "date_of_birth": profile.date_of_birth,
            "gender": profile.gender,
            "phone_number": profile.phone_number,
            "country": profile.country,
            "city_address": profile.city_address,
            "preferred_language": profile.preferred_language,
            "email_notifications": profile.email_notifications,
            "result_notifications": profile.result_notifications,
        }

        supplied = kwargs.pop("initial", {})
        initial.update(supplied)

        return cls(
            *args,
            user=user,
            initial=initial,
            **kwargs,
        )

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")

        if not photo:
            return photo

        max_size = 5 * 1024 * 1024

        if photo.size > max_size:
            raise forms.ValidationError(
                "Profile photo must be 5 MB or smaller."
            )

        allowed_content_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        content_type = getattr(photo, "content_type", "")

        if content_type not in allowed_content_types:
            raise forms.ValidationError(
                "Please upload a JPG, PNG or WEBP image."
            )

        return photo

    @transaction.atomic
    def save_for_user(self, user):
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.save(update_fields=[
            "first_name",
            "last_name",
        ])

        profile.certificate_name = (
            self.cleaned_data.get("certificate_name", "").strip()
        )
        profile.date_of_birth = self.cleaned_data.get("date_of_birth")
        profile.gender = self.cleaned_data.get("gender", "")
        profile.phone_number = (
            self.cleaned_data.get("phone_number", "").strip()
        )
        profile.country = (
            self.cleaned_data.get("country", "").strip()
        )
        profile.city_address = (
            self.cleaned_data.get("city_address", "").strip()
        )
        profile.preferred_language = (
            self.cleaned_data.get("preferred_language")
            or "english"
        )
        profile.email_notifications = bool(
            self.cleaned_data.get("email_notifications")
        )
        profile.result_notifications = bool(
            self.cleaned_data.get("result_notifications")
        )

        photo = self.cleaned_data.get("profile_photo")

        if photo:
            profile.profile_photo = photo

        profile.save()

        return profile
