from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


def portal_logout(request):
    """
    Compatibility logout endpoint.

    New UI uses POST. GET remains accepted so older templates/bookmarks
    do not fail with Django 5's HTTP 405 behavior.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been signed out.")

    return redirect("/login/?logged_out=1")
