from django.db import migrations, models


def classify_existing_tests(apps, schema_editor):
    MockTest = apps.get_model("assessments", "MockTest")
    for test in MockTest.objects.all().only("id", "title", "slug"):
        value = f"{test.title} {test.slug}".lower()
        if "full mock" in value or "full-mock" in value or "full test" in value:
            MockTest.objects.filter(pk=test.pk).update(delivery_mode="full_mock")


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0002_testpart_minimum_response_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="mocktest",
            name="delivery_mode",
            field=models.CharField(
                choices=[
                    ("practice", "Section practice"),
                    ("full_mock", "Full mock test"),
                ],
                db_index=True,
                default="practice",
                help_text=(
                    "Section practice appears in Practice; full mock tests appear "
                    "in the Mock Test centre."
                ),
                max_length=20,
            ),
        ),
        migrations.RunPython(classify_existing_tests, migrations.RunPython.noop),
    ]
