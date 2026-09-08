from django.contrib import admin
from django.urls import include, path
from website import views as website_public_views

urlpatterns = [
    path("", website_public_views.home, name="public_home"),
    path("admin/", admin.site.urls),
    path("practice/", include("assessments.urls")),
    path("evaluation/", include("grading.urls")),
    path("results/", include("results.urls")),
    path("", include("attempts.urls")),
    path("", include("core.urls")),
]
