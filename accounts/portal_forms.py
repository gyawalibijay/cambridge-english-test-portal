from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import StudentProfile

User = get_user_model()

BASE_INPUT = {"class": "pv2-input"}


class StudentSignupForm(forms.Form):
    first_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "First name",
            "autocomplete": "given-name",
        }),
    )
    last_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "Last name",
            "autocomplete": "family-name",
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            **BASE_INPUT,
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )
    password1 = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            **BASE_INPUT,
            "placeholder": "Create a password",
            "autocomplete": "new-password",
        }),
    )
    password2 = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            **BASE_INPUT,
            "placeholder": "Confirm password",
            "autocomplete": "new-password",
        }),
    )
    gender = forms.ChoiceField(
        required=False,
        choices=[("", "Select")] + list(StudentProfile.Gender.choices),
        widget=forms.Select(attrs=BASE_INPUT),
    )
    phone_number = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "+977...",
            "autocomplete": "tel",
        }),
    )
    country = forms.CharField(
        required=False,
        max_length=80,
        initial="Nepal",
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "Country",
            "autocomplete": "country-name",
        }),
    )
    city_address = forms.CharField(
        required=False,
        max_length=180,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "City / address",
            "autocomplete": "street-address",
        }),
    )
    agreed_terms = forms.BooleanField(
        required=True,
        label="I agree to the Terms & Privacy notice.",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    def clean(self):
        cleaned = super().clean()

        if (
            cleaned.get("password1")
            and cleaned.get("password2")
            and cleaned["password1"] != cleaned["password2"]
        ):
            self.add_error(
                "password2",
                "The two passwords do not match.",
            )

        return cleaned

    @transaction.atomic
    def save(self):
        email = self.cleaned_data["email"]

        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
        )

        if hasattr(user, "role"):
            user.role = "student"
            user.save(update_fields=["role"])

        StudentProfile.objects.create(
            user=user,
            gender=self.cleaned_data.get("gender", ""),
            phone_number=self.cleaned_data.get("phone_number", "").strip(),
            country=self.cleaned_data.get("country", "").strip() or "Nepal",
            city_address=self.cleaned_data.get("city_address", "").strip(),
            agreed_terms=True,
        )

        return user


class StudentProfileForm(forms.Form):
    first_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "First name",
        }),
    )
    last_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "Last name",
        }),
    )
    gender = forms.ChoiceField(
        required=False,
        choices=[("", "Select")] + list(StudentProfile.Gender.choices),
        widget=forms.Select(attrs=BASE_INPUT),
    )
    phone_number = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "+977...",
        }),
    )
    country = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "Country",
        }),
    )
    city_address = forms.CharField(
        required=False,
        max_length=180,
        widget=forms.TextInput(attrs={
            **BASE_INPUT,
            "placeholder": "City / address",
        }),
    )

    @classmethod
    def from_user(cls, user, *args, **kwargs):
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        initial = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "gender": profile.gender,
            "phone_number": profile.phone_number,
            "country": profile.country,
            "city_address": profile.city_address,
        }

        if "initial" in kwargs:
            initial.update(kwargs.pop("initial"))

        return cls(*args, initial=initial, **kwargs)

    @transaction.atomic
    def save_for_user(self, user):
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.save(update_fields=["first_name", "last_name"])

        profile.gender = self.cleaned_data.get("gender", "")
        profile.phone_number = self.cleaned_data.get("phone_number", "").strip()
        profile.country = self.cleaned_data.get("country", "").strip()
        profile.city_address = self.cleaned_data.get("city_address", "").strip()
        profile.save()

        return profile
