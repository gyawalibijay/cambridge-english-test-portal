from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import PublicInquiryForm


def about(request):
    return render(
        request,
        "website/about.html",
    )


def how_it_works(request):
    return render(
        request,
        "website/how_it_works.html",
    )


def faq(request):
    return render(
        request,
        "website/faq.html",
    )


def contact(request):
    form = PublicInquiryForm(
        request.POST or None
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        form.save()

        messages.success(
            request,
            "Thank you. Your enquiry has been submitted.",
        )

        return redirect(
            "website:contact"
        )

    return render(
        request,
        "website/contact.html",
        {
            "form": form,
        },
    )


def terms(request):
    return render(
        request,
        "website/terms.html",
    )


def privacy(request):
    return render(
        request,
        "website/privacy.html",
    )
