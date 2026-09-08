from django import forms


class EmailOTPForm(forms.Form):
    code = forms.CharField(
        min_length=6,
        max_length=6,
        label="Verification code",
        widget=forms.TextInput(attrs={
            "id": "id_code",
            "class": "pv2-input otp-hidden-code",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "maxlength": "6",
        }),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()

        if not code.isdigit():
            raise forms.ValidationError(
                "Enter the 6-digit code from your email."
            )

        return code


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "pv2-input",
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )
