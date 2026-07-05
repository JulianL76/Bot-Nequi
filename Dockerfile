# Imagen única para web (gunicorn) y worker (celery). Solo deps web, sin torch/ocr.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=webapp.settings

WORKDIR /app

# Dependencias del sistema mínimas (Pillow trae wheels; no hace falta compilar).
# curl para el healthcheck del compose.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-web.txt .
RUN pip install -r requirements-web.txt

COPY . .

# Recolecta static (WhiteNoise los comprime). No necesita BD.
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# gunicorn por defecto; el worker sobreescribe 'command' en docker-compose.
EXPOSE 8000
CMD ["gunicorn", "webapp.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
