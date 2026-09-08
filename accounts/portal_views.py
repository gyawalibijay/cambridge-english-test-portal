from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .portal_forms import StudentSignupForm
from .profile_forms_v3 import StudentProfileSettingsForm


def signup_view(request):
    from django.contrib import messages
    from django.shortcuts import redirect, render

    from .email_verification import send_verification_otp
    from .models import StudentProfile
    from .portal_forms import StudentSignupForm

    if request.user.is_authenticated:
        return redirect("dashboard")

    form = StudentSignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.is_active = False
        user.save(update_fields=["is_active"])

        profile, _ = StudentProfile.objects.get_or_create(
            user=user
        )

        if hasattr(profile, "email_verified_at"):
            profile.email_verified_at = None
            profile.save()

        request.session[
            "pending_email_verification_user_id"
        ] = user.pk

        try:
            result = send_verification_otp(
                user,
                request=request,
            )

            if result.get("ok"):
                messages.success(
                    request,
                    "We sent a 6-digit verification code to your email.",
                )
            elif result.get("reason") == "cooldown":
                messages.info(
                    request,
                    "A verification code was already requested. Please check your inbox.",
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not send signup OTP for user %s",
                user.pk,
            )
            messages.error(
                request,
                "Your account was created, but the verification email could not be sent. Use Resend code to try again.",
            )

        return redirect("verify_email")

    return render(
        request,
        "registration/signup.html",
        {"form": form},
    )


@login_required
def profile_view(request):
    from .models import StudentProfile

    profile, _ = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":
        form = StudentProfileSettingsForm(
            request.POST,
            request.FILES,
            user=request.user,
        )

        if form.is_valid():
            profile = form.save_for_user(
                request.user
            )

            messages.success(
                request,
                "Your profile and settings have been updated.",
            )

            return redirect("profile")
    else:
        form = StudentProfileSettingsForm.from_user(
            request.user
        )

    certificate_ready = bool(
        profile.profile_photo
        and (
            profile.certificate_name
            or request.user.get_full_name()
        )
    )

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "profile": profile,
            "certificate_ready": certificate_ready,
        },
    )


def _pending_verification_user(request):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    user_id = request.session.get(
        "pending_email_verification_user_id"
    )

    if not user_id:
        return None

    return User.objects.filter(
        pk=user_id
    ).first()


def verify_email_view(request):
    from django.contrib import messages
    from django.contrib.auth import login
    from django.shortcuts import redirect, render
    from django.utils import timezone

    from .email_verification import masked_email, verify_email_otp
    from .models import StudentProfile
    from .otp_forms import EmailOTPForm

    if request.user.is_authenticated:
        return redirect("dashboard")

    user = _pending_verification_user(
        request
    )

    if not user:
        messages.info(
            request,
            "Enter your email to request a new verification code.",
        )
        return redirect(
            "resend_verification"
        )

    if user.is_active:
        messages.info(
            request,
            "This email is already verified. Please sign in.",
        )
        return redirect("login")

    form = EmailOTPForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():
        result = verify_email_otp(
            user,
            form.cleaned_data["code"],
        )

        if result.get("ok"):
            user.is_active = True
            user.save(
                update_fields=["is_active"]
            )

            profile, _ = StudentProfile.objects.get_or_create(
                user=user
            )

            if hasattr(
                profile,
                "email_verified_at",
            ):
                profile.email_verified_at = timezone.now()
                profile.save()

            request.session.pop(
                "pending_email_verification_user_id",
                None,
            )

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            messages.success(
                request,
                "Email verified successfully. Welcome to Upskill Practice.",
            )

            return redirect(
                "dashboard"
            )

        reason = result.get("reason")

        if reason == "expired":
            form.add_error(
                "code",
                "This code has expired. Request a new code.",
            )
        elif reason == "too_many_attempts":
            form.add_error(
                "code",
                "Too many incorrect attempts. Request a new code.",
            )
        elif reason == "missing":
            form.add_error(
                "code",
                "No active verification code was found. Request a new code.",
            )
        else:
            left = result.get(
                "attempts_left"
            )
            message = "That code is incorrect."

            if left is not None:
                message += (
                    f" {left} attempt(s) remaining."
                )

            form.add_error(
                "code",
                message,
            )

    return render(
        request,
        "registration/verify_email.html",
        {
            "form": form,
            "masked_email": masked_email(
                user.email
            ),
            "pending_user": user,
        },
    )


def resend_verification_view(request):
    from django.contrib import messages
    from django.contrib.auth import get_user_model
    from django.shortcuts import redirect, render

    from .email_verification import send_verification_otp
    from .otp_forms import ResendVerificationForm

    User = get_user_model()

    pending = _pending_verification_user(
        request
    )

    initial = {
        "email": pending.email if pending else "",
    }

    form = ResendVerificationForm(
        request.POST or None,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        email = (
            form.cleaned_data["email"]
            .strip()
            .lower()
        )

        user = (
            User.objects.filter(
                email__iexact=email
            ).first()
            or User.objects.filter(
                username__iexact=email
            ).first()
        )

        if not user:
            messages.success(
                request,
                "If an unverified account exists for that email, a new code will be sent.",
            )
            return redirect(
                "resend_verification"
            )

        if user.is_active:
            messages.info(
                request,
                "This account is already verified. You can sign in.",
            )
            return redirect("login")

        request.session[
            "pending_email_verification_user_id"
        ] = user.pk

        try:
            result = send_verification_otp(
                user,
                request=request,
            )

            if result.get("ok"):
                messages.success(
                    request,
                    "A fresh verification code has been sent.",
                )
                return redirect(
                    "verify_email"
                )

            if result.get("reason") == "cooldown":
                messages.warning(
                    request,
                    f"Please wait {result.get('retry_after', 60)} seconds before requesting another code.",
                )
            elif result.get("reason") == "hourly_limit":
                messages.warning(
                    request,
                    "Too many codes were requested. Please try again later.",
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not resend OTP for user %s",
                user.pk,
            )
            messages.error(
                request,
                "The verification email could not be sent. Please try again.",
            )

    return render(
        request,
        "registration/resend_verification.html",
        {"form": form},
    )


# B1_READY_GOOGLE_OAUTH_V33_2_START
def _google_oauth_config():
    import os
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://cambridgeupskillenglishtest.com/auth/google/callback/",
    ).strip()
    return client_id, client_secret, redirect_uri


def google_auth_start(request):
    import secrets
    from urllib.parse import urlencode
    from django.contrib import messages
    from django.shortcuts import redirect

    if request.user.is_authenticated:
        return redirect("dashboard")

    client_id, client_secret, redirect_uri = _google_oauth_config()
    flow = (request.GET.get("flow") or "login").strip().lower()
    if flow not in {"login", "signup"}:
        flow = "login"

    next_url = (request.GET.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        request.session["google_oauth_next"] = next_url
    else:
        request.session.pop("google_oauth_next", None)

    request.session["google_oauth_flow"] = flow

    if not client_id or not client_secret:
        messages.info(
            request,
            "Google sign-in is ready but still needs the Google Client ID and Client Secret in the server settings.",
        )
        return redirect("signup" if flow == "signup" else "login")

    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state

    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + query)


def google_auth_callback(request):
    import json
    import re
    import secrets
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    from django.contrib import messages
    from django.contrib.auth import get_user_model, login
    from django.shortcuts import redirect
    from django.utils import timezone

    from .models import StudentProfile

    if request.user.is_authenticated:
        return redirect("dashboard")

    expected_state = request.session.pop("google_oauth_state", "")
    returned_state = (request.GET.get("state") or "").strip()
    flow = request.session.pop("google_oauth_flow", "login")
    next_url = request.session.pop("google_oauth_next", "")

    if not expected_state or not returned_state or not secrets.compare_digest(str(expected_state), str(returned_state)):
        messages.error(request, "Google sign-in could not be verified. Please try again.")
        return redirect("signup" if flow == "signup" else "login")

    if request.GET.get("error"):
        messages.info(request, "Google sign-in was cancelled.")
        return redirect("signup" if flow == "signup" else "login")

    code = (request.GET.get("code") or "").strip()
    if not code:
        messages.error(request, "Google did not return a sign-in code. Please try again.")
        return redirect("signup" if flow == "signup" else "login")

    client_id, client_secret, redirect_uri = _google_oauth_config()
    if not client_id or not client_secret:
        messages.error(request, "Google sign-in is not configured on the server yet.")
        return redirect("signup" if flow == "signup" else "login")

    try:
        token_body = urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        token_request = Request(
            "https://oauth2.googleapis.com/token",
            data=token_body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(token_request, timeout=12) as response:
            token_data = json.loads(response.read().decode("utf-8"))

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Google token response did not include an access token.")

        userinfo_request = Request(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urlopen(userinfo_request, timeout=12) as response:
            info = json.loads(response.read().decode("utf-8"))

    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        import logging
        logging.getLogger(__name__).exception("Google OAuth exchange failed")
        messages.error(request, "Google sign-in could not be completed. Please try again.")
        return redirect("signup" if flow == "signup" else "login")

    email = (info.get("email") or "").strip().lower()
    email_verified = bool(info.get("email_verified"))
    first_name = (info.get("given_name") or "").strip()
    last_name = (info.get("family_name") or "").strip()

    if not email or not email_verified:
        messages.error(request, "Please use a Google account with a verified email address.")
        return redirect("signup" if flow == "signup" else "login")

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    created = False

    if user is None:
        base = re.sub(r"[^A-Za-z0-9._-]+", "", email.split("@", 1)[0])[:120] or "student"
        username = base
        suffix = 1
        while User.objects.filter(username__iexact=username).exists():
            suffix += 1
            username = f"{base[:110]}-{suffix}"

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        created = True
    else:
        changed = []
        if not user.is_active:
            user.is_active = True
            changed.append("is_active")
        if not user.email:
            user.email = email
            changed.append("email")
        if first_name and not user.first_name:
            user.first_name = first_name
            changed.append("first_name")
        if last_name and not user.last_name:
            user.last_name = last_name
            changed.append("last_name")
        if changed:
            user.save(update_fields=changed)

    profile, _ = StudentProfile.objects.get_or_create(user=user)
    if hasattr(profile, "email_verified_at") and not profile.email_verified_at:
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified_at", "updated_at"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    messages.success(
        request,
        "Your B1 Ready account was created with Google." if created
        else "Welcome back. You are signed in with Google.",
    )

    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("dashboard")
# B1_READY_GOOGLE_OAUTH_V33_2_END
