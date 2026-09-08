from django.urls import path

from . import views

app_name = "commerce"

urlpatterns = [
    path("", views.store, name="store"),
    path(
        "<slug:slug>/purchase/",
        views.purchase_package,
        name="purchase_package",
    ),
    path(
        "invoice/<str:invoice_number>/",
        views.purchase_status,
        name="purchase_status",
    ),
]
