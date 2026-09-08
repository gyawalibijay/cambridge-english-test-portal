from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

CONFIG_PATH = Path(settings.BASE_DIR) / "var" / "landing_pricing_offer.json"


def default_config():
    return {
        "enabled": True,
        "label": "LIMITED TIME OFFER",
        "ends_at": (timezone.now() + timedelta(days=5)).isoformat(),
        "updated_at": timezone.now().isoformat(),
    }


def normalise(data):
    cfg = default_config()
    if isinstance(data, dict):
        cfg.update(data)

    cfg["enabled"] = bool(cfg.get("enabled", True))
    cfg["label"] = str(cfg.get("label") or "LIMITED TIME OFFER").strip()

    end = parse_datetime(str(cfg.get("ends_at") or "").strip())
    if end is None:
        end = timezone.now() + timedelta(days=5)
    if timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())

    cfg["ends_at"] = end.isoformat()
    return cfg


def load_offer_config():
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = default_config()
    return normalise(raw)


def save_offer_config(data):
    cfg = normalise(data)
    cfg["updated_at"] = timezone.now().isoformat()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    return cfg


def reset_offer(days=5):
    cfg = load_offer_config()
    cfg["enabled"] = True
    cfg["ends_at"] = (timezone.now() + timedelta(days=int(days))).isoformat()
    return save_offer_config(cfg)


def public_offer():
    cfg = load_offer_config()
    end = parse_datetime(cfg["ends_at"])

    if end and timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())

    expired = bool(end and end <= timezone.now())

    return {
        "enabled": bool(cfg["enabled"]),
        "active": bool(cfg["enabled"]) and not expired,
        "expired": expired,
        "label": cfg["label"],
        "ends_at": end.isoformat() if end else "",
        "ends_display": timezone.localtime(end).strftime("%b %d, %Y · %I:%M %p") if end else "",
    }
