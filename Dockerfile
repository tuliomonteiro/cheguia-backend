FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# libpq-dev + gcc needed to compile psycopg2 on some platforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Collect static files at build time (fails gracefully if env vars aren't set)
RUN SECRET_KEY=build-placeholder DB_USER=none OPENAI_API_KEY=none \
    python manage.py collectstatic --noinput --settings=cheguia.settings.prod \
    || true

# Run as non-root
RUN adduser --disabled-password --no-create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "cheguia.wsgi:application"]
