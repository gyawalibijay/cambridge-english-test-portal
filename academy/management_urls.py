from django.urls import path

from . import management_views

app_name = "academy_management"

urlpatterns = [
    path("inquiries/<int:inquiry_id>/status/", management_views.public_inquiry_status, name="inquiry_status"),
    path("inquiries/", management_views.public_inquiries, name="inquiries"),
    path(
        "",
        management_views.dashboard,
        name="dashboard",
    ),
    path(
        "purchases/",
        management_views.purchases,
        name="purchases",
    ),
    path(
        "purchases/<int:purchase_id>/approve/",
        management_views.approve_purchase_view,
        name="approve_purchase",
    ),
    path(
        "purchases/<int:purchase_id>/reject/",
        management_views.reject_purchase_view,
        name="reject_purchase",
    ),
    path(
        "courses/",
        management_views.courses,
        name="courses",
    ),
    path(
        "courses/new/",
        management_views.course_create,
        name="course_create",
    ),
    path(
        "courses/<int:course_id>/edit/",
        management_views.course_edit,
        name="course_edit",
    ),
    path(
        "materials/",
        management_views.materials,
        name="materials",
    ),
    path(
        "materials/new/",
        management_views.material_create,
        name="material_create",
    ),
    path(
        "test-materials/",
        management_views.test_materials,
        name="test_materials",
    ),
    path(
        "test-materials/new/",
        management_views.test_material_create,
        name="test_material_create",
    ),
    path(
        "students/",
        management_views.students,
        name="students",
    ),
]
