from django.db import migrations


def seed_exam_access_packages(apps, schema_editor):
    Program = apps.get_model("assessments", "Program")
    AccessPackage = apps.get_model("commerce", "AccessPackage")

    program_specs = [
        ("cambridge-general", "Cambridge / General English", "Cambridge", 10),
        ("ielts-academic", "IELTS Academic", "IELTS Academic", 20),
        ("ielts-general", "IELTS General Training", "IELTS General", 21),
        ("ukvi-interview", "UK Student / UKVI Interview", "UK Interview", 30),
    ]
    programs = {}
    for code, name, short_name, sort_order in program_specs:
        program, _ = Program.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "short_name": short_name,
                "description": "",
                "is_active": True,
                "sort_order": sort_order,
            },
        )
        programs[code] = program

    default_instructions = (
        "Use one of the payment methods shown below. Enter the generated invoice number "
        "exactly in the payment remarks, note, message, or reference field. After payment, "
        "submit the transaction reference or upload your receipt for verification."
    )

    # Preserve any Cambridge package already configured by the administrator.
    cambridge = programs["cambridge-general"]
    cambridge_package = AccessPackage.objects.filter(programs=cambridge).first()
    if cambridge_package is None:
        cambridge_package = AccessPackage.objects.create(
            slug="cambridge-access",
            title="Cambridge Exam Access",
            short_description="Cambridge practice, full mock tests and learning materials.",
            description="Unlock the complete Cambridge preparation area after payment verification.",
            price=1000,
            currency="NPR",
            sort_order=10,
            is_active=True,
            payment_instructions=default_instructions,
        )
        cambridge_package.programs.add(cambridge)

    # Future programs are created as visible-but-not-purchasable packages.
    ielts_a = programs["ielts-academic"]
    ielts_g = programs["ielts-general"]
    if not AccessPackage.objects.filter(programs__in=[ielts_a, ielts_g]).exists():
        ielts = AccessPackage.objects.create(
            slug="ielts-access",
            title="IELTS Access",
            short_description="IELTS Academic and General Training access.",
            description="IELTS practice and mock-test access will be enabled when the IELTS modules are released.",
            price=1000,
            currency="NPR",
            sort_order=20,
            is_active=False,
            payment_instructions=default_instructions,
        )
        ielts.programs.add(ielts_a, ielts_g)

    ukvi = programs["ukvi-interview"]
    if not AccessPackage.objects.filter(programs=ukvi).exists():
        uk = AccessPackage.objects.create(
            slug="uk-interview-access",
            title="UK Interview Access",
            short_description="UK Student / UKVI interview preparation access.",
            description="UK interview practice will be enabled when the interview module is released.",
            price=1000,
            currency="NPR",
            sort_order=30,
            is_active=False,
            payment_instructions=default_instructions,
        )
        uk.programs.add(ukvi)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0002_payment_invoice_system"),
    ]

    operations = [
        migrations.RunPython(seed_exam_access_packages, noop),
    ]
