import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_invoice_numbers(apps, schema_editor):
    Purchase = apps.get_model("commerce", "Purchase")
    for purchase in Purchase.objects.filter(invoice_number__isnull=True).order_by("pk"):
        purchase.invoice_number = f"UP-LEGACY-{purchase.pk:08d}"
        purchase.save(update_fields=["invoice_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentDestination",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("method", models.CharField(choices=[("esewa", "eSewa"), ("khalti", "Khalti"), ("bank", "Bank transfer"), ("qr", "QR payment"), ("other", "Other")], max_length=24)),
                ("bank_name", models.CharField(blank=True, max_length=120)),
                ("account_name", models.CharField(blank=True, max_length=140)),
                ("account_number", models.CharField(blank=True, help_text="Bank account number, wallet ID, phone number, or payment identifier.", max_length=140)),
                ("instructions", models.TextField(blank=True)),
                ("qr_image", models.ImageField(blank=True, null=True, upload_to="payments/qr/")),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "title"]},
        ),
        migrations.AddField(
            model_name="purchase",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="purchase",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="purchase",
            name="status",
            field=models.CharField(choices=[("initiated", "Invoice generated"), ("pending", "Pending verification"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], db_index=True, default="initiated", max_length=24),
        ),
        migrations.AlterField(
            model_name="purchase",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("esewa", "eSewa"), ("khalti", "Khalti"), ("bank", "Bank transfer"), ("qr", "QR payment"), ("cash", "Cash / office payment"), ("other", "Other")], default="", max_length=24),
        ),
        migrations.AlterField(
            model_name="accesspackage",
            name="payment_instructions",
            field=models.TextField(blank=True, default="Use one of the payment methods shown on the invoice page. Enter the generated invoice number exactly in the payment remarks, note, message, or reference field, then submit the transaction reference or receipt for verification."),
        ),
        migrations.RunPython(backfill_invoice_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="purchase",
            name="invoice_number",
            field=models.CharField(db_index=True, max_length=32, unique=True),
        ),
    ]
