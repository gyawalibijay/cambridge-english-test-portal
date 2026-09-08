from __future__ import annotations

from django.apps import apps
from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html


def _model(label):
    try:
        return apps.get_model(label)
    except LookupError:
        return None


def _fields(model):
    if model is None:
        return set()
    return {f.name for f in model._meta.get_fields()}


def _existing(model, candidates):
    names = _fields(model)
    return tuple(name for name in candidates if name and name in names)


def _first(model, candidates):
    names = _fields(model)
    for name in candidates:
        if name in names:
            return name
    return None


def _safe_reverse(name, args=()):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return "#"


def _crud_html(obj, review=False):
    opts = obj._meta
    change = _safe_reverse(
        f"admin:{opts.app_label}_{opts.model_name}_change",
        (obj.pk,),
    )
    delete = _safe_reverse(
        f"admin:{opts.app_label}_{opts.model_name}_delete",
        (obj.pk,),
    )

    view = f"{change}?view=1" if change != "#" else "#"
    edit_label = "Review" if review else "Edit"

    return format_html(
        '<div class="b1-crud-actions">'
        '<a class="b1-crud-view" href="{}">View</a>'
        '<a class="b1-crud-edit" href="{}">{}</a>'
        '<a class="b1-crud-delete" href="{}">Delete</a>'
        '</div>',
        view,
        change,
        edit_label,
        delete,
    )


def _repair_admin_list_config(model_admin):
    """
    Keep Django admin list configuration valid after V33.8.1 changes columns.

    We intentionally disable inline changelist editing and linked columns for
    enhanced modules because explicit View/Edit/Delete actions are safer and
    clearer. This also prevents admin.E111/E122/E124 conflicts left behind by
    older ModelAdmin definitions when list_display is changed.
    """
    display = tuple(getattr(model_admin, "list_display", ()) or ())
    model_admin.list_editable = ()
    model_admin.list_display_links = None

    # Remove invalid ordering fields that no longer exist in list_display only
    # when ordering explicitly refers to a callable/admin column. Database model
    # field ordering remains untouched.
    return display


def _install_row_actions(model, model_admin, review=False):
    cls = model_admin.__class__

    def b1_manage(self, obj):
        return _crud_html(obj, review=review)

    b1_manage.short_description = "Manage"
    b1_manage.admin_order_field = None
    setattr(cls, "b1_manage", b1_manage)

    display = list(getattr(model_admin, "list_display", ()) or ())
    display = [x for x in display if x != "b1_manage"]
    display.append("b1_manage")
    model_admin.list_display = tuple(display)

    model_admin.list_per_page = 30
    model_admin.actions_on_top = True
    model_admin.actions_on_bottom = False
    model_admin.save_on_top = True
    model_admin.show_full_result_count = False
    _repair_admin_list_config(model_admin)


def _set_compact(model, model_admin, columns, filters=(), search=()):
    methods = [
        name for name in getattr(model_admin, "list_display", ())
        if isinstance(name, str) and name.startswith("b1_") and name != "b1_manage"
    ]

    display = list(_existing(model, columns))
    for method in methods:
        if method not in display:
            display.append(method)

    if "b1_manage" not in display:
        display.append("b1_manage")

    if display:
        model_admin.list_display = tuple(display)

    valid_filters = []
    for item in filters:
        if isinstance(item, str):
            if item in _fields(model):
                valid_filters.append(item)
        else:
            valid_filters.append(item)
    if valid_filters:
        model_admin.list_filter = tuple(valid_filters)

    current_search = list(getattr(model_admin, "search_fields", ()) or ())
    for item in search:
        if item in _fields(model) and item not in current_search:
            current_search.append(item)
    if current_search:
        model_admin.search_fields = tuple(current_search)

    _repair_admin_list_config(model_admin)


def _configure_question_bank():
    Question = _model("question_bank.Question")
    if Question and Question in admin.site._registry:
        ma = admin.site._registry[Question]
        _install_row_actions(Question, ma)
        _set_compact(
            Question,
            ma,
            (
                "title",
                "program",
                "skill",
                "question_type",
                "part",
                "is_active",
            ),
            filters=("program", "skill", "question_type"),
            search=("title", "prompt", "prompt_text"),
        )

    Stimulus = _model("question_bank.Stimulus")
    if Stimulus and Stimulus in admin.site._registry:
        ma = admin.site._registry[Stimulus]
        _install_row_actions(Stimulus, ma)
        _set_compact(
            Stimulus,
            ma,
            (
                "title",
                "program",
                "skill",
                "stimulus_type",
                "is_active",
            ),
            filters=("program", "skill", "stimulus_type"),
            search=("title", "text", "content"),
        )


def _configure_academy():
    CourseMaterial = _model("academy.CourseMaterial")
    if CourseMaterial and CourseMaterial in admin.site._registry:
        ma = admin.site._registry[CourseMaterial]
        _install_row_actions(CourseMaterial, ma)
        _set_compact(
            CourseMaterial,
            ma,
            (
                "title",
                "course",
                "skill",
                "material_type",
                "is_published",
                "updated_at",
            ),
            filters=("course", "skill", "material_type", "is_published"),
            search=("title", "description"),
        )

    TestMaterial = _model("academy.TestMaterial")
    if TestMaterial and TestMaterial in admin.site._registry:
        ma = admin.site._registry[TestMaterial]
        _install_row_actions(TestMaterial, ma)
        _set_compact(
            TestMaterial,
            ma,
            (
                "title",
                "program",
                "skill",
                "is_published",
                "is_question_bank_ready",
                "updated_at",
            ),
            filters=("program", "skill", "is_published", "is_question_bank_ready"),
            search=("title", "instructions", "prompt_text"),
        )


def _configure_assessments():
    specs = {
        "assessments.MockTest": {
            "columns": (
                "title",
                "program",
                "skill",
                "duration_minutes",
                "is_published",
                "updated_at",
            ),
            "filters": ("program", "skill", "is_published"),
            "search": ("title",),
        },
        "assessments.TestSection": {
            "columns": (
                "mock_test",
                "title",
                "skill",
                "order",
                "duration_minutes",
            ),
            "filters": ("skill", "mock_test"),
            "search": ("title",),
        },
        "assessments.TestPart": {
            "columns": (
                "section",
                "title",
                "order",
                "prep_seconds",
                "response_seconds",
            ),
            "filters": ("section",),
            "search": ("title",),
        },
    }

    for label, spec in specs.items():
        model = _model(label)
        if model and model in admin.site._registry:
            ma = admin.site._registry[model]
            _install_row_actions(model, ma)
            _set_compact(
                model,
                ma,
                spec["columns"],
                spec["filters"],
                spec["search"],
            )


def _configure_accounts():
    StudentProfile = _model("accounts.StudentProfile")
    if StudentProfile and StudentProfile in admin.site._registry:
        ma = admin.site._registry[StudentProfile]
        _install_row_actions(StudentProfile, ma)

        relation = _first(StudentProfile, ("user", "student", "account"))
        level = _first(StudentProfile, ("target_level", "level", "current_level"))
        phone = _first(StudentProfile, ("phone", "phone_number", "mobile"))
        created = _first(StudentProfile, ("created_at", "joined_at", "updated_at"))

        _set_compact(
            StudentProfile,
            ma,
            tuple(x for x in (relation, level, phone, created) if x),
            filters=tuple(x for x in (level, created) if x),
            search=tuple(x for x in (phone,) if x),
        )


def _configure_commerce():
    Purchase = _model("commerce.Purchase")
    if Purchase and Purchase in admin.site._registry:
        ma = admin.site._registry[Purchase]
        _install_row_actions(Purchase, ma, review=True)

        person = _first(Purchase, ("user", "student", "student_profile", "customer"))
        invoice = _first(Purchase, ("invoice_number", "invoice_no", "reference", "transaction_id"))
        amount = _first(Purchase, ("amount", "total_amount", "payable_amount", "price", "amount_paid"))
        status = _first(Purchase, ("status", "verification_status", "payment_status", "approval_status"))
        package = _first(Purchase, ("package", "access_package"))
        created = _first(Purchase, ("created_at", "submitted_at", "updated_at"))

        columns = tuple(x for x in (person, invoice, package, amount, status, created) if x)

        # Keep Part 3 status/amount display helpers if installed.
        if hasattr(ma.__class__, "b1_payment_amount") and "b1_payment_amount" not in columns:
            columns = tuple(
                "b1_payment_amount" if x == amount else x
                for x in columns
            )
        if hasattr(ma.__class__, "b1_payment_status") and "b1_payment_status" not in columns:
            columns = tuple(
                "b1_payment_status" if x == status else x
                for x in columns
            )

        display = list(columns)
        if "b1_manage" not in display:
            display.append("b1_manage")
        ma.list_display = tuple(display)

        ma.list_filter = tuple(x for x in (status, package, created) if x)
        ma.list_per_page = 30
        ma.save_on_top = True
        ma.show_full_result_count = False
        _repair_admin_list_config(ma)

    specs = {
        "commerce.AccessPackage": (
            ("title", "name", "program", "price", "offer_price", "days", "is_active", "active"),
            ("program", "is_active", "active"),
        ),
        "commerce.ProgramEntitlement": (
            ("user", "student", "student_profile", "program", "is_active", "active", "expires_at", "end_date"),
            ("program", "is_active", "active"),
        ),
        "commerce.PaymentDestination": (
            ("title", "name", "payment_type", "bank_name", "is_active", "active"),
            ("payment_type", "is_active", "active"),
        ),
    }

    for label, (columns, filters) in specs.items():
        model = _model(label)
        if model and model in admin.site._registry:
            ma = admin.site._registry[model]
            _install_row_actions(model, ma)

            unique_columns = []
            field_names = _fields(model)
            for name in columns:
                if name in field_names and name not in unique_columns:
                    unique_columns.append(name)

            valid_filters = []
            for name in filters:
                if name in field_names and name not in valid_filters:
                    valid_filters.append(name)

            display = unique_columns[:6]
            display.append("b1_manage")
            ma.list_display = tuple(display)
            if valid_filters:
                ma.list_filter = tuple(valid_filters)
            ma.list_per_page = 30
            ma.save_on_top = True
            ma.show_full_result_count = False
            _repair_admin_list_config(ma)


def _configure_generic_registered_admins():
    # Ensure every remaining registered model has row-level View/Edit/Delete.
    for model, model_admin in list(admin.site._registry.items()):
        if model._meta.auto_created:
            continue
        if "b1_manage" not in getattr(model_admin, "list_display", ()):
            _install_row_actions(model, model_admin)


def apply_admin_crud_ux():
    # IMPORTANT:
    # This function is intentionally repeatable. The bootstrap module can be
    # imported while Django is still autodiscovering other admin.py files.
    # V33.8 incorrectly marked itself "applied" at that early point, so later
    # models such as question_bank.Question were skipped. V33.8.1 always
    # reapplies idempotently after registration is complete.
    _configure_question_bank()
    _configure_academy()
    _configure_assessments()
    _configure_accounts()
    _configure_commerce()
    _configure_generic_registered_admins()


# Do NOT apply here during module import. accounts/admin.py may be imported
# before question_bank/admin.py and other ModelAdmin registrations exist.


# Ensure enhancements are applied after all ModelAdmin registrations are complete.
if not getattr(admin.site, "_b1_crud_v3381_hooked", False):
    _previous_get_urls = admin.site.get_urls

    def _b1_crud_get_urls():
        apply_admin_crud_ux()
        return _previous_get_urls()

    admin.site.get_urls = _b1_crud_get_urls
    admin.site._b1_crud_v3381_hooked = True
