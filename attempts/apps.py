from django.apps import AppConfig


class AttemptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attempts"

    def ready(self):
        from . import score_integrity  # noqa: F401
        from . import speaking_score_v2  # noqa: F401
