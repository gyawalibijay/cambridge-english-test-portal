#!/bin/bash

set -e

echo "======================================"
echo "Unified English Portal - Step 8 Setup"
echo "======================================"

cd ~/unified-english-portal
source .venv/bin/activate

echo ""
echo "[1/6] Creating Django apps..."

for app in accounts assessments question_bank attempts grading results
do
    if [ ! -d "$app" ]; then
        python manage.py startapp "$app"
        echo "Created: $app"
    else
        echo "Already exists: $app"
    fi
done


echo ""
echo "[2/6] Creating custom User model..."

cat > accounts/models.py <<'PYTHON'
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        EVALUATOR = "evaluator", "Evaluator"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return self.get_full_name() or self.username
PYTHON


echo ""
echo "[3/6] Configuring Django Admin..."

cat > accounts/admin.py <<'PYTHON'
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    fieldsets = UserAdmin.fieldsets + (
        (
            "Portal Role",
            {
                "fields": ("role",),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Portal Role",
            {
                "fields": ("role",),
            },
        ),
    )
PYTHON


echo ""
echo "[4/6] Updating settings.py..."

python <<'PYTHON'
from pathlib import Path

settings_file = Path("config/settings.py")
text = settings_file.read_text()

apps = [
    "accounts",
    "assessments",
    "question_bank",
    "attempts",
    "grading",
    "results",
]

lines = text.splitlines()

try:
    static_index = next(
        i for i, line in enumerate(lines)
        if '"django.contrib.staticfiles"' in line
        or "'django.contrib.staticfiles'" in line
    )
except StopIteration:
    raise SystemExit("Could not find django.contrib.staticfiles in settings.py")

insert_at = static_index + 1

for app in apps:
    double = f'    "{app}",'
    single = f"    '{app}',"

    if not any(
        double.strip() == line.strip()
        or single.strip() == line.strip()
        for line in lines
    ):
        lines.insert(insert_at, double)
        insert_at += 1

text = "\n".join(lines) + "\n"

if "AUTH_USER_MODEL" not in text:
    text += '\nAUTH_USER_MODEL = "accounts.User"\n'

settings_file.write_text(text)

print("settings.py updated successfully.")
PYTHON


echo ""
echo "[5/6] Resetting empty development database..."

rm -f db.sqlite3

for app in accounts assessments question_bank attempts grading results
do
    if [ -d "$app/migrations" ]; then
        find "$app/migrations" -mindepth 1 ! -name "__init__.py" -exec rm -rf {} +
    fi
done


echo ""
echo "[6/6] Creating database migrations..."

python manage.py makemigrations accounts
python manage.py migrate

echo ""
echo "Running Django system check..."

python manage.py check

echo ""
echo "Checking accounts migration..."

python manage.py showmigrations accounts

echo ""
echo "======================================"
echo "STEP 8 COMPLETED SUCCESSFULLY"
echo "======================================"
echo ""
echo "Created architecture:"
echo ""
echo "accounts       -> Users and roles"
echo "assessments    -> Tests and programs"
echo "question_bank  -> Questions"
echo "attempts       -> Student answers"
echo "grading        -> Automatic/AI grading"
echo "results        -> Scores and reports"
echo ""
