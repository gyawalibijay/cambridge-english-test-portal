from . import extra_views
from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("privacy/", extra_views.privacy, name="privacy"),
    path("terms/", extra_views.terms, name="terms"),
    path("contact/", extra_views.contact, name="contact"),
    path("faq/", extra_views.faq, name="faq"),
    path("how-it-works/", extra_views.how_it_works, name="how_it_works"),
    path("about/", extra_views.about, name="about"),
    path("", views.home, name="home"),
    path("programs/", views.programs, name="programs"),
    path(
        "programs/<slug:code>/",
        views.program_detail,
        name="program_detail",
    ),
    path("features/", views.features, name="features"),
    path("pricing/", views.pricing, name="pricing"),
]
