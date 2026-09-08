from django.urls import path

from . import views
from . import full_mock_practice_report_v40_5

app_name = "results"

urlpatterns = [
    # B1_FULL_MOCK_PRACTICE_REPORT_V40_5
    path("<int:attempt_id>/practice-mock-report/", full_mock_practice_report_v40_5.practice_report, name="full_mock_practice_report"),
    path("<int:attempt_id>/practice-mock-report/download/", full_mock_practice_report_v40_5.practice_report_download, name="full_mock_practice_report_download"),
    path("", views.results_index, name="index"),
    path("", views.results_index, name="results_index"),
    path("<int:attempt_id>/", views.attempt_report, name="attempt_report"),
    path("<int:attempt_id>/", views.attempt_report, name="report"),
    path("<int:attempt_id>/", views.attempt_report, name="detail"),
]
