from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from commerce.services import has_program_access

from .models import Course


@login_required
def course_library(request):
    courses = (
        Course.objects
        .filter(is_published=True)
        .select_related("program")
        .prefetch_related("materials")
        .order_by(
            "program__sort_order",
            "sort_order",
            "title",
        )
    )

    visible = [
        course
        for course in courses
        if has_program_access(
            request.user,
            course.program,
        )
    ]

    return render(
        request,
        "academy/course_library.html",
        {
            "courses": visible,
        },
    )


@login_required
def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related(
            "program"
        ).prefetch_related(
            "materials"
        ),
        slug=slug,
        is_published=True,
    )

    if not has_program_access(
        request.user,
        course.program,
    ):
        from django.shortcuts import redirect

        return redirect(
            "/store/?locked="
            + course.program.code
        )

    materials = (
        course.materials
        .filter(is_published=True)
        .order_by(
            "sort_order",
            "title",
        )
    )

    return render(
        request,
        "academy/course_detail.html",
        {
            "course": course,
            "materials": materials,
        },
    )
