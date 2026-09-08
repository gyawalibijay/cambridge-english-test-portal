from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from assessments.models import MockTest
from attempts.models import TestAttempt
from commerce.models import AccessPackage, ProgramEntitlement, Purchase
from commerce.services import approve_purchase

from .forms import CourseForm, CourseMaterialForm, TestMaterialForm
from .models import Course, CourseMaterial, TestMaterial
from .permissions import (
    allowed_programs,
    is_management_user,
    require_management_user,
    require_program_access,
)

User = get_user_model()


def _guard(request):
    require_management_user(request.user)


def _program_ids(user):
    return list(
        allowed_programs(user)
        .values_list("id", flat=True)
    )


def _purchase_is_manageable(user, purchase):
    if user.is_superuser:
        return True

    allowed_ids = set(_program_ids(user))
    package_ids = set(
        purchase.package.programs
        .values_list("id", flat=True)
    )

    return bool(
        package_ids
        and package_ids.issubset(
            allowed_ids
        )
    )


def dashboard(request):
    _guard(request)

    programs = allowed_programs(
        request.user
    ).order_by(
        "sort_order",
        "name",
    )

    program_ids = list(
        programs.values_list(
            "id",
            flat=True,
        )
    )

    if request.user.is_superuser:
        purchases = Purchase.objects.all()
        courses = Course.objects.all()
        materials = CourseMaterial.objects.all()
        test_materials = TestMaterial.objects.all()
        attempts = TestAttempt.objects.all()
        entitlements = ProgramEntitlement.objects.filter(
            is_active=True
        )
    else:
        purchases = (
            Purchase.objects
            .filter(
                package__programs__id__in=program_ids
            )
            .distinct()
        )
        courses = Course.objects.filter(
            program_id__in=program_ids
        )
        materials = CourseMaterial.objects.filter(
            course__program_id__in=program_ids
        )
        test_materials = TestMaterial.objects.filter(
            program_id__in=program_ids
        )
        attempts = TestAttempt.objects.filter(
            mock_test__program_id__in=program_ids
        )
        entitlements = ProgramEntitlement.objects.filter(
            program_id__in=program_ids,
            is_active=True,
        )

    recent_purchases = (
        purchases
        .select_related(
            "user",
            "package",
        )
        .order_by("-created_at")[:7]
    )

    recent_courses = (
        courses
        .select_related(
            "program",
            "created_by",
        )
        .order_by("-updated_at")[:6]
    )

    program_cards = []

    for program in programs:
        program_cards.append({
            "program": program,
            "courses": courses.filter(
                program=program
            ).count(),
            "test_materials": test_materials.filter(
                program=program
            ).count(),
            "attempts": attempts.filter(
                mock_test__program=program
            ).count(),
            "students": entitlements.filter(
                program=program
            ).values("user_id").distinct().count(),
        })

    context = {
        "programs": programs,
        "program_cards": program_cards,
        "pending_purchases": purchases.filter(
            status=Purchase.Status.PENDING
        ).count(),
        "purchase_count": purchases.count(),
        "course_count": courses.count(),
        "material_count": materials.count(),
        "test_material_count": test_materials.count(),
        "attempt_count": attempts.count(),
        "student_count": entitlements.values(
            "user_id"
        ).distinct().count(),
        "recent_purchases": recent_purchases,
        "recent_courses": recent_courses,
    }

    return render(
        request,
        "academy/management/dashboard.html",
        context,
    )


def purchases(request):
    _guard(request)

    qs = (
        Purchase.objects
        .select_related(
            "user",
            "package",
            "reviewed_by",
        )
        .prefetch_related(
            "package__programs"
        )
        .order_by("-created_at")
    )

    if not request.user.is_superuser:
        allowed_ids = _program_ids(
            request.user
        )

        qs = qs.filter(
            package__programs__id__in=allowed_ids
        ).distinct()

    status = request.GET.get("status")

    if status:
        qs = qs.filter(status=status)

    search = request.GET.get(
        "q",
        "",
    ).strip()

    if search:
        qs = qs.filter(
            Q(invoice_number__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__username__icontains=search)
            | Q(transaction_reference__icontains=search)
            | Q(package__title__icontains=search)
        )

    return render(
        request,
        "academy/management/purchases.html",
        {
            "purchases": qs[:200],
            "current_status": status or "",
            "search": search,
        },
    )


@require_POST
def approve_purchase_view(request, purchase_id):
    _guard(request)

    purchase = get_object_or_404(
        Purchase.objects.prefetch_related(
            "package__programs"
        ),
        pk=purchase_id,
    )

    if not _purchase_is_manageable(
        request.user,
        purchase,
    ):
        raise PermissionDenied(
            "You cannot approve this package."
        )

    approve_purchase(
        purchase,
        reviewer=request.user,
    )

    messages.success(
        request,
        f"Access approved for {purchase.user}.",
    )

    return redirect(
        "academy_management:purchases"
    )


@require_POST
def reject_purchase_view(request, purchase_id):
    _guard(request)

    purchase = get_object_or_404(
        Purchase.objects.prefetch_related(
            "package__programs"
        ),
        pk=purchase_id,
    )

    if not _purchase_is_manageable(
        request.user,
        purchase,
    ):
        raise PermissionDenied(
            "You cannot reject this package."
        )

    purchase.status = Purchase.Status.REJECTED
    purchase.reviewed_by = request.user

    from django.utils import timezone

    purchase.reviewed_at = timezone.now()
    purchase.admin_note = (
        request.POST.get(
            "admin_note",
            "",
        ).strip()
    )

    purchase.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "admin_note",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Purchase rejected.",
    )

    return redirect(
        "academy_management:purchases"
    )


def courses(request):
    _guard(request)

    qs = (
        Course.objects
        .filter(
            program__in=allowed_programs(
                request.user
            )
        )
        .select_related(
            "program",
            "created_by",
        )
        .annotate(
            material_total=Count(
                "materials"
            )
        )
        .order_by(
            "program__name",
            "sort_order",
            "title",
        )
    )

    return render(
        request,
        "academy/management/courses.html",
        {"courses": qs},
    )


def course_create(request):
    _guard(request)

    form = CourseForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)

        require_program_access(
            request.user,
            course.program,
        )

        course.created_by = request.user
        course.save()

        messages.success(
            request,
            "Course created.",
        )

        return redirect(
            "academy_management:courses"
        )

    return render(
        request,
        "academy/management/form.html",
        {
            "form": form,
            "title": "Create Course",
            "subtitle": (
                "Create a course only inside a test system "
                "your admin account is licensed to manage."
            ),
            "submit_label": "Create Course",
        },
    )


def course_edit(request, course_id):
    _guard(request)

    course = get_object_or_404(
        Course.objects.select_related(
            "program"
        ),
        pk=course_id,
    )

    require_program_access(
        request.user,
        course.program,
    )

    form = CourseForm(
        request.POST or None,
        request.FILES or None,
        instance=course,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        require_program_access(
            request.user,
            updated.program,
        )

        updated.save()

        messages.success(
            request,
            "Course updated.",
        )

        return redirect(
            "academy_management:courses"
        )

    return render(
        request,
        "academy/management/form.html",
        {
            "form": form,
            "title": "Edit Course",
            "subtitle": course.title,
            "submit_label": "Save Changes",
        },
    )


def materials(request):
    _guard(request)

    qs = (
        CourseMaterial.objects
        .filter(
            course__program__in=allowed_programs(
                request.user
            )
        )
        .select_related(
            "course",
            "course__program",
            "created_by",
        )
        .order_by(
            "course__program__name",
            "course__title",
            "sort_order",
            "title",
        )
    )

    return render(
        request,
        "academy/management/materials.html",
        {
            "materials": qs,
            "mode": "course",
        },
    )


def material_create(request):
    _guard(request)

    initial = {}

    if request.GET.get("course"):
        initial["course"] = request.GET[
            "course"
        ]

    form = CourseMaterialForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        material = form.save(
            commit=False
        )

        require_program_access(
            request.user,
            material.course.program,
        )

        material.created_by = request.user
        material.save()

        messages.success(
            request,
            "Course material uploaded.",
        )

        return redirect(
            "academy_management:materials"
        )

    return render(
        request,
        "academy/management/form.html",
        {
            "form": form,
            "title": "Add Course Material",
            "subtitle": (
                "Upload documents, audio, downloads, text lessons "
                "or external learning links."
            ),
            "submit_label": "Save Material",
        },
    )


def test_materials(request):
    _guard(request)

    qs = (
        TestMaterial.objects
        .filter(
            program__in=allowed_programs(
                request.user
            )
        )
        .select_related(
            "program",
            "course",
            "created_by",
        )
        .order_by(
            "program__name",
            "skill",
            "-created_at",
        )
    )

    skill = request.GET.get("skill")

    if skill:
        qs = qs.filter(skill=skill)

    return render(
        request,
        "academy/management/test_materials.html",
        {
            "materials": qs,
            "skill": skill or "",
        },
    )


def test_material_create(request):
    _guard(request)

    form = TestMaterialForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        material = form.save(
            commit=False
        )

        require_program_access(
            request.user,
            material.program,
        )

        if (
            material.course
            and material.course.program_id
            != material.program_id
        ):
            form.add_error(
                "course",
                "Course must belong to the selected test system.",
            )
        else:
            material.created_by = request.user
            material.save()

            messages.success(
                request,
                "Test material uploaded.",
            )

            return redirect(
                "academy_management:test_materials"
            )

    return render(
        request,
        "academy/management/form.html",
        {
            "form": form,
            "title": "Upload Test Material",
            "subtitle": (
                "Add Reading passages, Writing prompts or Listening "
                "audio/transcripts for a licensed test system."
            ),
            "submit_label": "Save Test Material",
        },
    )


def students(request):
    _guard(request)

    programs = allowed_programs(
        request.user
    )

    entitlements = (
        ProgramEntitlement.objects
        .filter(
            program__in=programs,
            is_active=True,
        )
        .select_related(
            "user",
            "program",
        )
        .order_by(
            "user__first_name",
            "user__email",
        )
    )

    grouped = {}

    for entitlement in entitlements:
        user = entitlement.user

        if user.id not in grouped:
            grouped[user.id] = {
                "user": user,
                "programs": [],
            }

        grouped[user.id]["programs"].append(
            entitlement.program
        )

    return render(
        request,
        "academy/management/students.html",
        {
            "student_rows": list(
                grouped.values()
            ),
        },
    )


def public_inquiries(request):
    _guard(request)

    from website.models import PublicInquiry

    qs = PublicInquiry.objects.all().order_by("-created_at")

    status = request.GET.get("status", "").strip()

    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "academy/management/inquiries.html",
        {
            "inquiries": qs[:250],
            "status": status,
        },
    )


@require_POST
def public_inquiry_status(request, inquiry_id):
    _guard(request)

    from website.models import PublicInquiry

    inquiry = get_object_or_404(
        PublicInquiry,
        pk=inquiry_id,
    )

    new_status = request.POST.get("status", "").strip()

    valid = {
        PublicInquiry.Status.NEW,
        PublicInquiry.Status.IN_PROGRESS,
        PublicInquiry.Status.CLOSED,
    }

    if new_status not in valid:
        raise PermissionDenied("Invalid enquiry status.")

    inquiry.status = new_status
    inquiry.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Enquiry status updated.",
    )

    return redirect(
        "academy_management:inquiries"
    )
