#!/bin/bash
set -e

echo "==> Waiting for database..."
python - <<'EOF'
import os, sys, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "cheguia.settings.dev"))
import django
django.setup()
from django.db import connections
from django.db.utils import OperationalError

for attempt in range(1, 31):
    try:
        connections["default"].ensure_connection()
        print("    Database is ready.")
        break
    except OperationalError:
        print(f"    Attempt {attempt}/30 — retrying in 2s...")
        time.sleep(2)
else:
    print("    Database unavailable after 60 seconds. Exiting.")
    sys.exit(1)
EOF

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Starting application..."
exec "$@"
