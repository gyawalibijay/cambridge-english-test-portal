from django.urls import path

from . import student_views

app_name = "academy_student"

urlpatterns = [
    path(
        "",
        student_views.course_library,
        name="library",
    ),
    path(
        "<slug:slug>/",
        student_views.course_detail,
        name="course_detail",
    ),
]
