from __future__ import annotations
from pathlib import Path
import os
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import NoReverseMatch, path, reverse
from django.utils.html import format_html


def _model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _field_names(model):
    return {f.name for f in model._meta.get_fields()} if model else set()


def _first_field(model, candidates):
    names = _field_names(model)
    return next((x for x in candidates if x in names), None)


def _existing(model, candidates):
    names = _field_names(model)
    return tuple(x for x in candidates if x and x in names)


def _admin_url(model, action="changelist"):
    if model is None:
        return "#"
    try:
        o = model._meta
        return reverse(f"admin:{o.app_label}_{o.model_name}_{action}")
    except NoReverseMatch:
        return "#"


def _change_url(obj):
    try:
        o = obj._meta
        return reverse(f"admin:{o.app_label}_{o.model_name}_change", args=(obj.pk,))
    except Exception:
        return "#"


def _safe_count(model):
    try:
        return model._default_manager.count() if model else 0
    except Exception:
        return 0


def _status_field(model):
    return _first_field(model, ("status", "verification_status", "payment_status", "approval_status", "state"))


def _status_counts(model):
    field = _status_field(model)
    result = {"field": field, "pending": 0, "approved": 0, "rejected": 0, "other": 0}
    if not model or not field:
        return result
    try:
        for value in model._default_manager.values_list(field, flat=True):
            text = str(value or "").strip().lower()
            if any(k in text for k in ("pending", "review", "invoice", "verify", "submitted")):
                result["pending"] += 1
            elif any(k in text for k in ("approve", "active", "paid", "complete", "success", "verified")):
                result["approved"] += 1
            elif any(k in text for k in ("reject", "declin", "fail", "cancel", "expired")):
                result["rejected"] += 1
            else:
                result["other"] += 1
    except Exception:
        pass
    return result


def _media_summary():
    root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    count = total = 0
    kinds = {"audio": 0, "video": 0, "image": 0, "document": 0, "other": 0}
    if not root.exists() or not root.is_dir():
        return {"count": 0, "size": "0 MB", "kinds": kinds, "root": str(root)}
    audio = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".webm"}
    video = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
    image = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"}
    document = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".csv", ".zip"}
    for base, _, files in os.walk(root):
        for filename in files:
            count += 1
            p = Path(base) / filename
            try: total += p.stat().st_size
            except OSError: pass
            ext = p.suffix.lower()
            if ext in audio: kinds["audio"] += 1
            elif ext in video: kinds["video"] += 1
            elif ext in image: kinds["image"] += 1
            elif ext in document: kinds["document"] += 1
            else: kinds["other"] += 1
    mb = total / (1024 * 1024)
    size = f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb:.1f} MB"
    return {"count": count, "size": size, "kinds": kinds, "root": str(root)}


def _recent_pending_purchases(Purchase, limit=8):
    if Purchase is None: return []
    field = _status_field(Purchase)
    qs = Purchase._default_manager.all()
    if field:
        try:
            qs = qs.filter(Q(**{f"{field}__icontains": "pending"}) | Q(**{f"{field}__icontains": "invoice"}) | Q(**{f"{field}__icontains": "verify"}) | Q(**{f"{field}__icontains": "review"}))
        except Exception:
            pass
    order = _first_field(Purchase, ("created_at", "submitted_at", "updated_at"))
    try: qs = qs.order_by(f"-{order}") if order else qs.order_by("-pk")
    except Exception: pass
    return [{"label": str(obj), "status": str(getattr(obj, field, "")) if field else "", "url": _change_url(obj)} for obj in qs[:limit]]


@staff_member_required
def operations_center(request):
    Purchase = _model("commerce", "Purchase")
    AccessPackage = _model("commerce", "AccessPackage")
    ProgramEntitlement = _model("commerce", "ProgramEntitlement")
    PaymentDestination = _model("commerce", "PaymentDestination")
    StudentProfile = _model("accounts", "StudentProfile")
    User = _model("auth", "User")
    Attempt = _model("attempts", "TestAttempt")
    purchase_status = _status_counts(Purchase)
    media = _media_summary()
    cards = [
        {"label":"Students","value":_safe_count(StudentProfile),"note":"Student profiles","icon":"S","url":_admin_url(StudentProfile),"tone":"blue"},
        {"label":"Purchases","value":_safe_count(Purchase),"note":"Payment records","icon":"₨","url":_admin_url(Purchase),"tone":"navy"},
        {"label":"Needs Review","value":purchase_status["pending"],"note":"Pending / verification","icon":"!","url":_admin_url(Purchase),"tone":"red" if purchase_status["pending"] else "green"},
        {"label":"Access Packages","value":_safe_count(AccessPackage),"note":"Available plans","icon":"A","url":_admin_url(AccessPackage),"tone":"purple"},
        {"label":"Entitlements","value":_safe_count(ProgramEntitlement),"note":"Program access records","icon":"E","url":_admin_url(ProgramEntitlement),"tone":"teal"},
        {"label":"Media Files","value":media["count"],"note":media["size"],"icon":"▣","url":"/admin/media-center/","tone":"gold"},
    ]
    workflow = [
        {"title":"Review incoming payment","detail":"Open Purchases and verify invoice/payment information before granting access.","url":_admin_url(Purchase),"action":"Open purchases"},
        {"title":"Check student access","detail":"Use Student Profiles and Program Entitlements when a learner cannot access the expected program.","url":_admin_url(StudentProfile),"action":"Open students"},
        {"title":"Manage pricing / access plan","detail":"Access Packages control plan records. Verify the student-facing Store page after any pricing change.","url":_admin_url(AccessPackage),"action":"Open packages"},
        {"title":"Audit uploaded files","detail":"Use Media Center to preview stored media and confirm frontend references.","url":"/admin/media-center/","action":"Open Media Center"},
    ]
    context = admin.site.each_context(request)
    context.update({
        "title":"Operations Center","cards":cards,"workflow":workflow,"purchase_status":purchase_status,
        "pending_purchases":_recent_pending_purchases(Purchase),"media":media,
        "urls":{"purchases":_admin_url(Purchase),"students":_admin_url(StudentProfile),"packages":_admin_url(AccessPackage),"entitlements":_admin_url(ProgramEntitlement),"destinations":_admin_url(PaymentDestination),"attempts":_admin_url(Attempt),"users":_admin_url(User)},
        "recent_admin":LogEntry.objects.select_related("content_type","user").order_by("-action_time")[:10],
    })
    return render(request, "admin/operations_center.html", context)


def _status_badge_value(value):
    text = str(value or "").strip(); lower = text.lower()
    if any(x in lower for x in ("approve","active","paid","complete","success","verified")): cls="is-approved"
    elif any(x in lower for x in ("reject","declin","fail","cancel","expired")): cls="is-rejected"
    elif any(x in lower for x in ("pending","review","invoice","verify","submitted")): cls="is-pending"
    else: cls="is-neutral"
    return format_html('<span class="b1-ops-status {}">{}</span>', cls, text or "—")



def _repair_list_display_config(ma):
    """
    Keep Django's changelist configuration internally consistent after
    Part 3 changes list_display.

    The old PurchaseAdmin can define list_display_links entries such as
    'student_identity'. Once list_display is replaced, Django raises admin.E111
    if one of those links is no longer in list_display. We retain valid links
    and safely choose a replacement only when necessary.
    """
    display = tuple(getattr(ma, "list_display", ()) or ())
    editable = set(getattr(ma, "list_editable", ()) or ())
    links = getattr(ma, "list_display_links", ())

    # list_display_links=None is a deliberate Django setting: keep it.
    if links is None:
        return

    valid = tuple(
        item for item in (links or ())
        if item in display and item not in editable
    )

    if valid:
        ma.list_display_links = valid
        return

    # Pick a real displayed field/method that is not list-editable.
    candidates = [
        item for item in display
        if isinstance(item, str)
        and item not in editable
        and item not in {"b1_payment_status", "b1_payment_amount"}
    ]
    ma.list_display_links = (candidates[0],) if candidates else None


def _enhance_purchase_admin():
    Purchase = _model("commerce", "Purchase")
    if not Purchase: return
    ma = admin.site._registry.get(Purchase)
    if ma is None: return
    status_field = _status_field(Purchase)
    amount_field = _first_field(Purchase, ("amount","total_amount","payable_amount","price","amount_paid"))
    invoice_field = _first_field(Purchase, ("invoice_number","invoice_no","invoice","reference","transaction_id"))
    user_field = _first_field(Purchase, ("user","student","student_profile","customer"))
    cls = ma.__class__
    def b1_payment_status(self, obj):
        return _status_badge_value(getattr(obj, status_field, "")) if status_field else _status_badge_value("recorded")
    setattr(cls, "b1_payment_status", admin.display(description="Payment status")(b1_payment_status))
    def b1_payment_amount(self, obj):
        if not amount_field: return "—"
        value = getattr(obj, amount_field, None)
        return "—" if value in (None, "") else format_html('<strong class="b1-ops-amount">NPR {}</strong>', value)
    setattr(cls, "b1_payment_amount", admin.display(description="Amount")(b1_payment_amount))
    display=[]
    for x in (user_field, invoice_field):
        if x: display.append(x)
    display += ["b1_payment_amount","b1_payment_status"]
    display += list(_existing(Purchase,("package","access_package","program","created_at","updated_at")))
    ma.list_display = tuple(dict.fromkeys(display)) or ("__str__",)
    ma.list_filter = tuple(dict.fromkeys(_existing(Purchase,(status_field,"package","access_package","program","created_at","updated_at"))))
    search=list(getattr(ma,"search_fields",()))
    if invoice_field and invoice_field not in search: search.append(invoice_field)
    if user_field:
        try:
            f=Purchase._meta.get_field(user_field); related=f.related_model; names=_field_names(related)
            for sub in ("username","email","first_name","last_name"):
                lookup=f"{user_field}__{sub}"
                if sub in names and lookup not in search: search.append(lookup)
        except Exception: pass
    ma.search_fields=tuple(search); ma.list_per_page=50; ma.save_on_top=True; ma.actions_on_top=True; ma.show_full_result_count=False
    _repair_list_display_config(ma)


def _enhance_student_admin():
    StudentProfile=_model("accounts","StudentProfile")
    if not StudentProfile: return
    ma=admin.site._registry.get(StudentProfile)
    if ma is None: return
    relation=_first_field(StudentProfile,("user","student","account")); level=_first_field(StudentProfile,("target_level","level","current_level")); phone=_first_field(StudentProfile,("phone","phone_number","mobile")); created=_first_field(StudentProfile,("created_at","joined_at","updated_at"))
    display=[x for x in (relation,level,phone,created) if x]
    ma.list_display=tuple(dict.fromkeys(display)) or ("__str__",)
    ma.list_filter=tuple(dict.fromkeys([x for x in (level,created) if x]))
    search=list(getattr(ma,"search_fields",()))
    if phone and phone not in search: search.append(phone)
    if relation:
        try:
            f=StudentProfile._meta.get_field(relation); related=f.related_model; names=_field_names(related)
            for sub in ("username","email","first_name","last_name"):
                lookup=f"{relation}__{sub}"
                if sub in names and lookup not in search: search.append(lookup)
        except Exception: pass
    ma.search_fields=tuple(search); ma.list_per_page=50; ma.save_on_top=True; ma.show_full_result_count=False
    _repair_list_display_config(ma)


def _enhance_access_admins():
    for label in (("commerce","AccessPackage"),("commerce","ProgramEntitlement"),("commerce","PaymentDestination")):
        model=_model(*label)
        if not model: continue
        ma=admin.site._registry.get(model)
        if ma is None: continue
        ma.list_per_page=50; ma.save_on_top=True; ma.actions_on_top=True; ma.show_full_result_count=False
        search=list(getattr(ma,"search_fields",()))
        for field in ("name","title","slug","description"):
            if field in _field_names(model) and field not in search: search.append(field)
        ma.search_fields=tuple(search)
        filters=list(getattr(ma,"list_filter",()))
        for field in ("is_active","active","program","created_at","updated_at"):
            if field in _field_names(model) and field not in filters: filters.append(field)
        ma.list_filter=tuple(filters)
        _repair_list_display_config(ma)


def apply_operations_admin_ux():
    if getattr(admin.site,"_b1_operations_v3371_applied",False): return
    _enhance_purchase_admin(); _enhance_student_admin(); _enhance_access_admins()
    admin.site._b1_operations_v3371_applied=True

try: apply_operations_admin_ux()
except Exception: pass

if not getattr(admin.site,"_b1_operations_v3371_hooked",False):
    _previous_get_urls=admin.site.get_urls
    def _b1_operations_get_urls():
        apply_operations_admin_ux()
        return [path("operations-center/",admin.site.admin_view(operations_center),name="operations_center")] + _previous_get_urls()
    admin.site.get_urls=_b1_operations_get_urls
    admin.site._b1_operations_v3371_hooked=True
