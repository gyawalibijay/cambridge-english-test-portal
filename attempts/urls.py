from django.urls import path
from . import views, full_mock_v35_part2
from . import full_mock_part_flow_v40_5

app_name = "attempts"

urlpatterns = [
    # B1_FULL_MOCK_PART2_V35_1
    path("attempt/<int:attempt_id>/section/", full_mock_part_flow_v40_5.overview, name="full_mock_section"),
    path("attempt/<int:attempt_id>/section-timer/", full_mock_part_flow_v40_5.timer_json, name="full_mock_timer"),
    # B1_FULL_MOCK_PART_SELECTOR_ROUTES_V40_5
    path("attempt/<int:attempt_id>/mock/", full_mock_part_flow_v40_5.overview, name="full_mock_overview"),
    path("attempt/<int:attempt_id>/", views.dispatch, name="dispatch"),
    path("attempt/<int:attempt_id>/speaking/", views.speaking_runner, name="speaking_runner"),
    path("attempt/<int:attempt_id>/objective/", views.objective_runner, name="objective_runner"),
    path("attempt/<int:attempt_id>/writing/", views.writing_runner, name="writing_runner"),
    path(
        "attempt/<int:attempt_id>/question/<int:question_id>/submit-speaking/",
        views.submit_speaking_response,
        name="submit_speaking_response",
    ),
    path(
        "attempt/<int:attempt_id>/question/<int:question_id>/submit-objective/",
        views.submit_objective_response,
        name="submit_objective_response",
    ),
    path(
        "attempt/<int:attempt_id>/question/<int:question_id>/submit-writing/",
        views.submit_writing_response,
        name="submit_writing_response",
    ),
    path("attempt/<int:attempt_id>/complete/", views.complete, name="complete"),

    # === B1_FULL_MOCK_EXACT_PART_ROUTES_V40_8_3 START ===
    path(
        "attempt/<int:attempt_id>/mock/<str:skill>/",
        full_mock_part_flow_v40_5.skill_parts,
        name="full_mock_parts",
    ),
    path(
        "attempt/<int:attempt_id>/mock/<str:skill>/part/<int:part_no>/start/",
        full_mock_part_flow_v40_5.start_part,
        name="full_mock_part_start",
    ),
    # === B1_FULL_MOCK_EXACT_PART_ROUTES_V40_8_3 END ===
]
