from django.urls import path
from . import views, full_mock_v35_part3

app_name = "grading"
urlpatterns = [
    path("full-mocks/", full_mock_v35_part3.queue, name="full_mock_queue"),
    path("full-mocks/<int:attempt_id>/", full_mock_v35_part3.attempt_detail, name="full_mock_attempt"),
    path("reviews/", views.review_queue, name="review_queue"),
    path("reviews/<int:response_id>/", views.review_response, name="review_response"),
    path("reviews/<int:response_id>/save/", views.save_review, name="save_review"),
]
