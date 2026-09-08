from django.db import migrations, models


def refresh_safe_defaults(apps, schema_editor):
    Site = apps.get_model("website", "PublicSiteSettings")
    site, _ = Site.objects.get_or_create(pk=1)

    # Only replace the original generic defaults. Admin-customized copy is preserved.
    replacements = {
        "announcement_text": (
            "Cambridge-style practice, IELTS preparation and UK interview confidence",
            "Cambridge English • IELTS • UK Interview",
        ),
        "hero_eyebrow": (
            "SMARTER PREPARATION. CLEARER PROGRESS.",
            "ONE PORTAL. THREE ENGLISH GOALS.",
        ),
        "hero_title": (
            "Choose your goal.",
            "Choose your English test.",
        ),
        "hero_highlight": (
            "Prepare with confidence.",
            "Practise with confidence.",
        ),
        "hero_description": (
            "Focused English test preparation with realistic practice, clear feedback and one simple student portal.",
            "Cambridge English, IELTS and UK Interview preparation with focused practice, mock tests and clear progress.",
        ),
        "seo_title": (
            "Online English Test Preparation | Cambridge, IELTS & UK Interview",
            "Upskill English Test Preparation | Cambridge, IELTS & UK Interview",
        ),
        "seo_description": (
            "Prepare online for Cambridge-style English tests, IELTS Academic and General Training, and UK student interviews with realistic practice, mock tests and feedback.",
            "Prepare online for Cambridge English, IELTS Academic and General Training, and UK student interviews with realistic practice, mock tests, learning materials and progress tracking.",
        ),
        "seo_keywords": (
            "Cambridge English practice test, Cambridge Upskill practice, CEFR B1 speaking practice, IELTS preparation Nepal, IELTS Academic mock test, IELTS General Training practice, UK student interview preparation, English mock test online",
            "Cambridge English practice test online, Cambridge English mock test, CEFR B1 speaking practice, IELTS preparation Nepal, IELTS Academic mock test, IELTS General Training practice, IELTS online practice, UK student interview preparation, UK visa interview practice, English mock test online, English test preparation Nepal",
        ),
    }

    changed = []
    for field, (old_value, new_value) in replacements.items():
        if getattr(site, field, None) == old_value:
            setattr(site, field, new_value)
            changed.append(field)

    if changed:
        site.save(update_fields=changed + ["updated_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_public_site_editor"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicsitesettings",
            name="mascot_alt_text",
            field=models.CharField(
                default="Upskill student preparation guide",
                max_length=160,
            ),
        ),
        migrations.AddField(
            model_name="publicsitesettings",
            name="mascot_image",
            field=models.ImageField(
                blank=True,
                help_text=(
                    "Optional homepage/program mascot image. A bundled mascot is used when this is empty."
                ),
                null=True,
                upload_to="website/branding/",
            ),
        ),
        migrations.AddField(
            model_name="publicsitesettings",
            name="show_mascot",
            field=models.BooleanField(
                default=True,
                help_text="Show the mascot on the public home and program landing pages.",
            ),
        ),
        migrations.RunPython(refresh_safe_defaults, noop_reverse),
    ]
