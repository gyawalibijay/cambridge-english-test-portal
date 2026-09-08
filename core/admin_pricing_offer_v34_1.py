from __future__ import annotations

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.pricing_offer_config_v34_1 import (
    load_offer_config,
    public_offer,
    reset_offer,
    save_offer_config,
)


def pricing_offer_control(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()

        if action == "reset5":
            reset_offer(5)
            messages.success(request, "Offer restarted for 5 days.")

        elif action == "disable":
            cfg = load_offer_config()
            cfg["enabled"] = False
            save_offer_config(cfg)
            messages.success(request, "Offer timer disabled.")

        elif action == "enable":
            cfg = load_offer_config()
            cfg["enabled"] = True
            save_offer_config(cfg)
            messages.success(request, "Offer timer enabled.")

        else:
            raw = (request.POST.get("ends_at") or "").strip()
            end = parse_datetime(raw)

            if end is None:
                messages.error(request, "Please choose a valid offer deadline.")
                return HttpResponseRedirect(reverse("admin:b1_pricing_offer_control"))

            if timezone.is_naive(end):
                end = timezone.make_aware(end, timezone.get_current_timezone())

            cfg = load_offer_config()
            cfg["enabled"] = request.POST.get("enabled") == "on"
            cfg["label"] = (request.POST.get("label") or "LIMITED TIME OFFER").strip()
            cfg["ends_at"] = end.isoformat()
            save_offer_config(cfg)
            messages.success(request, "Pricing offer updated.")

        return HttpResponseRedirect(reverse("admin:b1_pricing_offer_control"))

    cfg = load_offer_config()
    offer = public_offer()
    end = parse_datetime(cfg["ends_at"])

    if end and timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())

    context = {
        **admin.site.each_context(request),
        "title": "Landing Pricing Offer",
        "config": cfg,
        "offer": offer,
        "ends_input": timezone.localtime(end).strftime("%Y-%m-%dT%H:%M") if end else "",
        "opts": None,
        "has_permission": True,
    }

    return TemplateResponse(
        request,
        "admin/pricing_offer_control_v34_1.html",
        context,
    )


if not getattr(admin.site, "_b1_pricing_offer_v341_hooked", False):
    previous_get_urls = admin.site.get_urls

    def get_urls():
        previous = previous_get_urls()
        custom = [
            path(
                "pricing-offer-control/",
                admin.site.admin_view(pricing_offer_control),
                name="b1_pricing_offer_control",
            ),
        ]
        return custom + previous

    admin.site.get_urls = get_urls
    admin.site._b1_pricing_offer_v341_hooked = True
