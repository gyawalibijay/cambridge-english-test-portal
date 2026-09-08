from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ProgramEntitlement, Purchase


def has_program_access(user, program):
    if not getattr(user, "is_authenticated", False):
        return False

    if (
        user.is_superuser
        or user.is_staff
        or getattr(user, "role", "") in {"admin", "evaluator"}
    ):
        return True

    entitlement = (
        ProgramEntitlement.objects
        .filter(
            user=user,
            program=program,
            is_active=True,
        )
        .order_by("-created_at")
        .first()
    )

    return bool(
        entitlement
        and entitlement.valid_now
    )


@transaction.atomic
def approve_purchase(purchase, reviewer=None):
    if purchase.status == Purchase.Status.APPROVED:
        return purchase

    now = timezone.now()

    purchase.status = Purchase.Status.APPROVED
    purchase.reviewed_by = reviewer
    purchase.reviewed_at = now
    purchase.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )

    access_days = purchase.package.access_days

    for program in purchase.package.programs.all():
        entitlement, _ = ProgramEntitlement.objects.get_or_create(
            user=purchase.user,
            program=program,
            defaults={
                "source_purchase": purchase,
                "starts_at": now,
                "granted_by": reviewer,
            },
        )

        entitlement.is_active = True
        entitlement.source_purchase = purchase
        entitlement.starts_at = now
        entitlement.granted_by = reviewer

        if access_days:
            entitlement.expires_at = now + timedelta(
                days=access_days
            )
        else:
            entitlement.expires_at = None

        entitlement.save()

    return purchase
