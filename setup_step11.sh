#!/bin/bash

set -e

echo "================================================"
echo "Unified English Portal - Step 11"
echo "Admin + Media + Secure Development Server"
echo "================================================"

PROJECT_DIR="$HOME/unified-english-portal"
CURRENT_USER="$(whoami)"

cd "$PROJECT_DIR"
source .venv/bin/activate


echo ""
echo "[1/10] Detecting Google Cloud external IP..."

EXTERNAL_IP="$(curl -s \
  -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)"

if [ -z "$EXTERNAL_IP" ]; then
    echo "ERROR: Could not detect the VM external IP."
    exit 1
fi

echo "External IP detected: $EXTERNAL_IP"


echo ""
echo "[2/10] Configuring Django static/media/security settings..."

python <<PYTHON
from pathlib import Path
import re

settings_path = Path("config/settings.py")
text = settings_path.read_text()

external_ip = "${EXTERNAL_IP}"

# Remove a previous Step 11 block if script is re-run.
start_marker = "# === STEP 11 DEVELOPMENT SERVER SETTINGS ==="
end_marker = "# === END STEP 11 DEVELOPMENT SERVER SETTINGS ==="

if start_marker in text and end_marker in text:
    before = text.split(start_marker)[0]
    after = text.split(end_marker, 1)[1]
    text = before.rstrip() + "\n" + after.lstrip()

# Replace Django's existing ALLOWED_HOSTS definition.
text = re.sub(
    r"^ALLOWED_HOSTS\s*=\s*.*$",
    f'ALLOWED_HOSTS = ["127.0.0.1", "localhost", "{external_ip}"]',
    text,
    flags=re.MULTILINE,
)

block = f'''

{start_marker}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATIC_ROOT = BASE_DIR / "staticfiles"

CSRF_TRUSTED_ORIGINS = [
    "https://{external_ip}",
]

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

{end_marker}
'''

text = text.rstrip() + block + "\n"
settings_path.write_text(text)

print("Django settings updated.")
PYTHON


echo ""
echo "[3/10] Creating media/static directories..."

mkdir -p media
mkdir -p staticfiles


echo ""
echo "[4/10] Installing Gunicorn and Nginx..."

python -m pip install gunicorn

sudo apt update
sudo apt install -y nginx openssl


echo ""
echo "[5/10] Collecting Django static files..."

python manage.py collectstatic --noinput


echo ""
echo "[6/10] Creating Gunicorn system service..."

sudo tee /etc/systemd/system/unified-english-portal.service > /dev/null <<EOF
[Unit]
Description=Unified English Mock-Test Portal
After=network.target

[Service]
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}

Environment="PATH=${PROJECT_DIR}/.venv/bin"

ExecStart=${PROJECT_DIR}/.venv/bin/gunicorn \
    config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 1 \
    --threads 2 \
    --timeout 120

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable unified-english-portal
sudo systemctl restart unified-english-portal


echo ""
echo "[7/10] Creating temporary HTTPS certificate..."

sudo mkdir -p /etc/nginx/ssl/unified-english-portal

sudo openssl req \
    -x509 \
    -nodes \
    -days 90 \
    -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/unified-english-portal/dev.key \
    -out /etc/nginx/ssl/unified-english-portal/dev.crt \
    -subj "/C=NP/ST=Bagmati/L=Kathmandu/O=Surakshya Technologies/OU=Development/CN=${EXTERNAL_IP}" \
    -addext "subjectAltName=IP:${EXTERNAL_IP}"


echo ""
echo "[8/10] Configuring Nginx..."

sudo tee /etc/nginx/sites-available/unified-english-portal > /dev/null <<EOF
server {
    listen 80;
    server_name ${EXTERNAL_IP};

    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name ${EXTERNAL_IP};

    ssl_certificate /etc/nginx/ssl/unified-english-portal/dev.crt;
    ssl_certificate_key /etc/nginx/ssl/unified-english-portal/dev.key;

    client_max_body_size 512M;
    client_body_timeout 300s;

    location /static/ {
        alias ${PROJECT_DIR}/staticfiles/;
    }

    location /media/ {
        alias ${PROJECT_DIR}/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF

sudo ln -sf \
    /etc/nginx/sites-available/unified-english-portal \
    /etc/nginx/sites-enabled/unified-english-portal

sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl restart nginx


echo ""
echo "[9/10] Running Django checks..."

python manage.py migrate
python manage.py check

echo ""
echo "Gunicorn/Django service:"
sudo systemctl --no-pager --full status unified-english-portal | head -15

echo ""
echo "Nginx service:"
sudo systemctl --no-pager --full status nginx | head -12


echo ""
echo "[10/10] Creating first Super Admin..."
echo ""

read -p "Choose admin username: " ADMIN_USERNAME
read -p "Admin email: " ADMIN_EMAIL

while true
do
    read -s -p "Choose admin password (minimum 12 characters): " ADMIN_PASSWORD
    echo ""

    if [ ${#ADMIN_PASSWORD} -lt 12 ]; then
        echo "Password is too short. Use at least 12 characters."
        continue
    fi

    read -s -p "Confirm password: " ADMIN_PASSWORD_CONFIRM
    echo ""

    if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
        echo "Passwords do not match. Try again."
        continue
    fi

    break
done

export ADMIN_USERNAME
export ADMIN_EMAIL
export ADMIN_PASSWORD

python manage.py shell <<'PYTHON'
import os
from accounts.models import User

username = os.environ["ADMIN_USERNAME"]
email = os.environ["ADMIN_EMAIL"]
password = os.environ["ADMIN_PASSWORD"]

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
    },
)

user.email = email
user.role = User.Role.ADMIN
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

if created:
    print("")
    print("Super Admin CREATED successfully.")
else:
    print("")
    print("Existing user UPDATED as Super Admin.")

print(f"Username: {user.username}")
print(f"Role: {user.role}")
print(f"Staff: {user.is_staff}")
print(f"Superuser: {user.is_superuser}")
PYTHON

unset ADMIN_PASSWORD
unset ADMIN_PASSWORD_CONFIRM


echo ""
echo "================================================"
echo "STEP 11 COMPLETED SUCCESSFULLY"
echo "================================================"

echo ""
echo "Open this URL in your browser:"
echo ""
echo "https://${EXTERNAL_IP}/admin/"
echo ""
echo "IMPORTANT:"
echo "Your browser will warn that the certificate is not trusted."
echo "This is EXPECTED because this is a temporary development certificate."
echo ""
echo "Do NOT enter real student/customer information yet."
echo ""
