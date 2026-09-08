from core import final_student_views
from assessments import skill_mock, full_mock_v35_part2
from . import logout_v2
from . import student_dashboard_v2
from accounts import portal_views as portal_account_views
from django.contrib.auth import views as auth_views
from django.urls import include, path
from . import views, staff_views

urlpatterns = [

    # === FINAL STUDENT PORTAL ROUTES START ===
    path("dashboard/", final_student_views.dashboard, name="dashboard"),
    path("practice/", final_student_views.practice_hub, name="student_practice_hub"),
    path("practice/<str:skill>/", final_student_views.practice_skill, name="student_practice_skill"),
    path("mock-tests/", full_mock_v35_part2.hub, name="student_mock_tests"),
    path("mock-tests/<slug:slug>/", full_mock_v35_part2.detail, name="student_full_mock_detail"),
    path("mock-tests/<slug:slug>/start/", full_mock_v35_part2.start, name="student_full_mock_start"),
    path("learn/", final_student_views.learn, name="student_learn"),
    path("progress/", final_student_views.progress, name="student_progress"),
    path("certificates/", final_student_views.certificates, name="student_certificates"),
    path("certificates/report/<int:attempt_id>/", final_student_views.practice_report_pdf, name="student_practice_report_pdf"),
    path("student-profile/", final_student_views.profile_summary, name="student_profile_summary"),
    # === FINAL STUDENT PORTAL ROUTES END ===

    path("resend-verification/", portal_account_views.resend_verification_view, name="resend_verification"),
    path("verify-email/", portal_account_views.verify_email_view, name="verify_email"),
    path("", include("website.urls")),
    path("logout/", logout_v2.portal_logout, name="logout"),
    path("management/", include("academy.management_urls")),
    path("courses/", include("academy.student_urls")),
    path("store/", include("commerce.urls")),
    # B1_READY_GOOGLE_OAUTH_V33_2
    path("auth/google/", portal_account_views.google_auth_start, name="google_auth_start"),
    path("auth/google/callback/", portal_account_views.google_auth_callback, name="google_auth_callback"),
    path("signup/", portal_account_views.signup_view, name="signup"),
    path("profile/", portal_account_views.profile_view, name="profile"),

    path("", views.public_landing, name="public_landing"),
    path(
        "content-studio/",
        staff_views.content_studio,
        name="content_studio",
    ),
    path("", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

]
