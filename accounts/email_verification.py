import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailVerificationOTP


def masked_email(email):
    email = (email or "").strip()
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)

    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[:2] + "*" * min(
            6,
            max(1, len(local) - 2),
        )

    return f"{masked_local}@{domain}"


def _client_ip(request):
    if request is None:
        return None

    forwarded = request.META.get(
        "HTTP_X_FORWARDED_FOR",
        "",
    )

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


@transaction.atomic
def send_verification_otp(user, request=None):
    now = timezone.now()

    expiry_minutes = int(
        getattr(settings, "EMAIL_OTP_EXPIRY_MINUTES", 10)
    )
    resend_seconds = int(
        getattr(settings, "EMAIL_OTP_RESEND_SECONDS", 60)
    )
    max_per_hour = int(
        getattr(settings, "EMAIL_OTP_MAX_PER_HOUR", 5)
    )

    last = (
        EmailVerificationOTP.objects
        .filter(user=user)
        .order_by("-created_at")
        .first()
    )

    if last:
        elapsed = (now - last.created_at).total_seconds()

        if elapsed < resend_seconds:
            return {
                "ok": False,
                "reason": "cooldown",
                "retry_after": max(
                    1,
                    int(resend_seconds - elapsed),
                ),
            }

    recent_count = (
        EmailVerificationOTP.objects
        .filter(
            user=user,
            created_at__gte=now - timedelta(hours=1),
        )
        .count()
    )

    if recent_count >= max_per_hour:
        return {
            "ok": False,
            "reason": "hourly_limit",
        }

    EmailVerificationOTP.objects.filter(
        user=user,
        used_at__isnull=True,
    ).update(used_at=now)

    code = f"{secrets.randbelow(1_000_000):06d}"

    otp = EmailVerificationOTP.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=now + timedelta(
            minutes=expiry_minutes
        ),
        requested_ip=_client_ip(request),
    )

    context = {
        "student_name": user.first_name or "Student",
        "student_email": user.email,
        "code": code,
        "expiry_minutes": expiry_minutes,
        "app_name": "Upskill Practice",
        "company_name": "Surakshya Technologies",
    }

    subject = "Your Upskill Practice verification code"

    plain = (
        f"Hello {context['student_name']},\n\n"
        f"Your Upskill Practice verification code is: {code}\n\n"
        f"This code expires in {expiry_minutes} minutes.\n"
        "Do not share this code with anyone.\n\n"
        "Upskill Practice\n"
        "Surakshya Technologies"
    )

    html = render_to_string(
        "emails/otp_verification.html",
        context,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(
        html,
        "text/html",
    )

    try:
        sent = message.send(
            fail_silently=False
        )

        if sent != 1:
            raise RuntimeError(
                "Email backend did not confirm OTP delivery."
            )
    except Exception:
        otp.used_at = timezone.now()
        otp.save(
            update_fields=["used_at"]
        )
        raise

    return {
        "ok": True,
        "otp_id": otp.pk,
    }


@transaction.atomic
def verify_email_otp(user, code):
    now = timezone.now()
    max_attempts = int(
        getattr(
            settings,
            "EMAIL_OTP_MAX_ATTEMPTS",
            5,
        )
    )

    otp = (
        EmailVerificationOTP.objects
        .select_for_update()
        .filter(
            user=user,
            used_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp:
        return {
            "ok": False,
            "reason": "missing",
        }

    if otp.expires_at <= now:
        otp.used_at = now
        otp.save(
            update_fields=["used_at"]
        )
        return {
            "ok": False,
            "reason": "expired",
        }

    if otp.attempts >= max_attempts:
        otp.used_at = now
        otp.save(
            update_fields=["used_at"]
        )
        return {
            "ok": False,
            "reason": "too_many_attempts",
        }

    if not check_password(
        str(code).strip(),
        otp.code_hash,
    ):
        otp.attempts += 1
        fields = ["attempts"]

        if otp.attempts >= max_attempts:
            otp.used_at = now
            fields.append("used_at")

        otp.save(
            update_fields=fields
        )

        return {
            "ok": False,
            "reason": "invalid",
            "attempts_left": max(
                0,
                max_attempts - otp.attempts,
            ),
        }

    otp.used_at = now
    otp.save(
        update_fields=["used_at"]
    )

    return {
        "ok": True,
    }
