from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import PurchaseForm
from .models import AccessPackage, PaymentDestination, ProgramEntitlement, Purchase


def _student_shell_context(request, active="access"):
    try:
        from core.final_student_views import _base_context
        return _base_context(request, active)
    except Exception:
        return {
            "active": active,
            "target_level": "B1",
            "readiness": 0,
            "display_name": request.user.first_name or request.user.username,
        }


def _package_state(user, package):
    programs = list(package.programs.all())
    now = timezone.now()

    active_program_ids = set(
        ProgramEntitlement.objects
        .filter(
            user=user,
            program__in=programs,
            is_active=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .values_list("program_id", flat=True)
    )

    has_access = bool(programs) and all(
        program.id in active_program_ids
        for program in programs
    )

    latest_purchase = (
        Purchase.objects
        .filter(user=user, package=package)
        .order_by("-created_at")
        .first()
    )

    pending_purchase = (
        Purchase.objects
        .filter(
            user=user,
            package=package,
            status=Purchase.Status.PENDING,
        )
        .order_by("-created_at")
        .first()
    )

    initiated_purchase = (
        Purchase.objects
        .filter(
            user=user,
            package=package,
            status=Purchase.Status.INITIATED,
        )
        .order_by("-created_at")
        .first()
    )

    return {
        "has_access": has_access,
        "latest_purchase": latest_purchase,
        "pending_purchase": pending_purchase,
        "initiated_purchase": initiated_purchase,
    }


@login_required
def store(request):
    # CAMBRIDGE_ONLY_ACCESS_V14_9
    packages = (
        AccessPackage.objects
        .filter(programs__code="cambridge-general")
        .distinct()
        .prefetch_related("programs")
        .order_by("sort_order", "title")
    )

    cards = []
    for package in packages:
        cards.append({
            "package": package,
            **_package_state(request.user, package),
        })

    context = _student_shell_context(request, "access")
    context.update({
        "cards": cards,
        "locked_program": request.GET.get("locked", ""),
        "recent_purchases": (
            Purchase.objects
            .filter(
                user=request.user,
                package__programs__code="cambridge-general",
            )
            .distinct()
            .select_related("package")
            .order_by("-created_at")[:8]
        ),
    })

    return render(request, "commerce/store.html", context)


@login_required
def purchase_package(request, slug):
    # CAMBRIDGE_ONLY_ACCESS_V14_9
    package = get_object_or_404(
        AccessPackage.objects.prefetch_related("programs").filter(programs__code="cambridge-general").distinct(),
        slug=slug,
        is_active=True,
    )

    state = _package_state(request.user, package)

    if state["has_access"]:
        messages.info(request, "You already have active access to this package.")
        return redirect("commerce:store")

    if state["pending_purchase"]:
        messages.info(request, "Your payment is already waiting for verification.")
        return redirect(
            "commerce:purchase_status",
            invoice_number=state["pending_purchase"].invoice_number,
        )

    purchase = state["initiated_purchase"]

    # SIMPLE_5_DIGIT_INVOICE_V12
    # Shorten only an old invoice that is still completely unpaid/unsubmitted.
    # Pending/approved/rejected payment references are never changed.
    if purchase is not None:
        current_invoice = str(purchase.invoice_number or "")
        can_safely_refresh = (
            purchase.status == Purchase.Status.INITIATED
            and purchase.submitted_at is None
            and not purchase.transaction_reference
            and not purchase.receipt
        )
        if can_safely_refresh and (len(current_invoice) != 5 or not current_invoice.isdigit()):
            purchase.invoice_number = Purchase.make_invoice_number()
            purchase.save(update_fields=["invoice_number", "updated_at"])

    if purchase is None:
        purchase = Purchase.objects.create(
            user=request.user,
            package=package,
            amount=package.price,
            currency=package.currency,
            status=Purchase.Status.INITIATED,
            payment_method="",
        )

    form = PurchaseForm(
        request.POST or None,
        request.FILES or None,
        instance=purchase,
    )

    if request.method == "POST" and form.is_valid():
        purchase = form.save(commit=False)
        purchase.user = request.user
        purchase.package = package
        purchase.amount = package.price
        purchase.currency = package.currency
        purchase.status = Purchase.Status.PENDING
        purchase.submitted_at = timezone.now()
        purchase.save()

        messages.success(
            request,
            "Payment submitted. Your course access will activate after verification.",
        )
        return redirect(
            "commerce:purchase_status",
            invoice_number=purchase.invoice_number,
        )

    destinations = PaymentDestination.objects.filter(is_active=True).order_by(
        "sort_order", "title"
    )

    context = _student_shell_context(request, "access")
    context.update({
        "package": package,
        "purchase": purchase,
        "invoice_number": purchase.invoice_number,
        "payment_destinations": destinations,
        "form": form,
    })
    return render(request, "commerce/purchase.html", context)


@login_required
def purchase_status(request, invoice_number):
    purchase = get_object_or_404(
        Purchase.objects.select_related("package", "reviewed_by"),
        user=request.user,
        invoice_number=invoice_number,
    )

    context = _student_shell_context(request, "access")
    context["purchase"] = purchase
    return render(request, "commerce/purchase_status.html", context)
