from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from assessments.models import Program


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required
def dashboard(request):
    programs = (
        Program.objects
        .filter(is_active=True)
        .prefetch_related("mock_tests")
        .order_by("sort_order", "name")
    )

    program_data = []
    for program in programs:
        program_data.append({
            "program": program,
            "published_tests": program.mock_tests.filter(is_published=True).count(),
        })

    return render(request, "core/dashboard.html", {"program_data": program_data})


def public_landing(request):
    from django.shortcuts import redirect, render

    if request.user.is_authenticated:
        return redirect("dashboard")

    return render(request, "core/landing.html")

# === CAMBRIDGE DESIGN PACK DASHBOARD OVERRIDE ===
@login_required
def dashboard(request):
    from attempts.models import StudentResponse, TestAttempt
    from assessments.models import MockTest, Program

    programs = Program.objects.filter(is_active=True).order_by("sort_order", "name")

    skill_specs = [
        ("speaking", "Speaking", 5, 12, ["cambridge-speaking-practice-1"]),
        ("listening", "Listening", 5, 25, ["cambridge-listening-practice-1"]),
        ("reading", "Reading", 5, 25, ["cambridge-reading-practice-1", "cambridge-reading-source-samples"]),
        ("writing", "Writing", 2, 30, ["cambridge-writing-practice-1", "cambridge-writing-source-samples"]),
    ]

    skill_cards = []

    for key, title, parts, minutes, candidates in skill_specs:
        test = None
        for slug in candidates:
            test = MockTest.objects.filter(slug=slug, is_published=True).first()
            if test:
                break

        latest = None
        attempt_count = 0
        completed = False
        in_progress = False

        if test:
            attempts = TestAttempt.objects.filter(user=request.user, mock_test=test)
            attempt_count = attempts.count()
            latest = attempts.order_by("-started_at").first()

            if latest:
                in_progress = latest.status == TestAttempt.Status.IN_PROGRESS
                completed = latest.status in {
                    TestAttempt.Status.SUBMITTED,
                    TestAttempt.Status.GRADING,
                    TestAttempt.Status.COMPLETED,
                }

        skill_cards.append({
            "key": key,
            "title": title,
            "parts": parts,
            "minutes": minutes,
            "test": test,
            "latest": latest,
            "attempt_count": attempt_count,
            "completed": completed,
            "in_progress": in_progress,
        })

    all_attempts = TestAttempt.objects.filter(user=request.user).select_related(
        "mock_test", "mock_test__program"
    ).order_by("-started_at")

    completed_sections = sum(1 for card in skill_cards if card["completed"])
    progress_percent = int(completed_sections / 4 * 100)

    recent_attempts = list(all_attempts[:5])

    total_responses = StudentResponse.objects.filter(
        attempt_question__attempt__user=request.user
    ).count()

    return render(
        request,
        "core/dashboard.html",
        {
            "programs": programs,
            "skill_cards": skill_cards,
            "completed_sections": completed_sections,
            "progress_percent": progress_percent,
            "total_attempts": all_attempts.count(),
            "total_responses": total_responses,
            "recent_attempts": recent_attempts,
        },
    )
