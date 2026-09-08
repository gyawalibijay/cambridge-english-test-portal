from django.core.exceptions import PermissionDenied

from assessments.models import Program
from commerce.models import ProgramEntitlement


def is_management_user(user):
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or getattr(user, "role", "") == "admin"
        )
    )


def allowed_programs(user):
    if not is_management_user(user):
        return Program.objects.none()

    if user.is_superuser:
        return Program.objects.all()

    program_ids = (
        ProgramEntitlement.objects
        .filter(
            user=user,
            is_active=True,
        )
        .values_list(
            "program_id",
            flat=True,
        )
    )

    return Program.objects.filter(
        id__in=program_ids
    )


def require_management_user(user):
    if not is_management_user(user):
        raise PermissionDenied(
            "Management access required."
        )


def require_program_access(user, program):
    require_management_user(user)

    if user.is_superuser:
        return

    if not allowed_programs(user).filter(
        pk=program.pk
    ).exists():
        raise PermissionDenied(
            "You do not have management access "
            "to this test system."
        )
