from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0003_public_site_mascot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="publicsitesettings",
            name="announcement_text",
            field=models.CharField(
                default="Cambridge English • IELTS • UK Interview",
                max_length=180,
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="hero_description",
            field=models.TextField(
                default=(
                    "Cambridge English, IELTS and UK Interview preparation with "
                    "focused practice, mock tests and clear progress."
                )
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="hero_eyebrow",
            field=models.CharField(
                default="ONE PORTAL. THREE ENGLISH GOALS.",
                max_length=140,
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="hero_highlight",
            field=models.CharField(
                default="Practise with confidence.",
                max_length=150,
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="hero_title",
            field=models.CharField(
                default="Choose your English test.",
                max_length=150,
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="seo_description",
            field=models.CharField(
                default=(
                    "Prepare online for Cambridge English, IELTS Academic and "
                    "General Training, and UK student interviews with realistic "
                    "practice, mock tests, learning materials and progress tracking."
                ),
                max_length=320,
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="seo_keywords",
            field=models.TextField(
                default=(
                    "Cambridge English practice test online, Cambridge English "
                    "mock test, CEFR B1 speaking practice, IELTS preparation Nepal, "
                    "IELTS Academic mock test, IELTS General Training practice, "
                    "IELTS online practice, UK student interview preparation, "
                    "UK visa interview practice, English mock test online, "
                    "English test preparation Nepal"
                )
            ),
        ),
        migrations.AlterField(
            model_name="publicsitesettings",
            name="seo_title",
            field=models.CharField(
                default=(
                    "Upskill English Test Preparation | Cambridge, IELTS & UK Interview"
                ),
                max_length=180,
            ),
        ),
    ]
