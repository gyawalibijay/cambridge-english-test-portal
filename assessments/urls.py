from django.urls import include, path

from . import views

app_name = "assessments"

urlpatterns = [
    # Dedicated Reading practice; other skills keep their current routes.
    path("", include("assessments.reading_reference_urls")),
    path(
        "cambridge/",
        views.cambridge_dashboard,
        name="cambridge_dashboard",
    ),
    path("program/<slug:code>/", views.program_detail, name="program_detail"),
    path("test/<slug:slug>/", views.test_detail, name="test_detail"),
    path("test/<slug:slug>/start/", views.start_test, name="start_test"),
]
