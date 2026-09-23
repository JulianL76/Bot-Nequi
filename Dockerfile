# Imagen única para web (gunicorn) y worker (celery). Solo deps web, sin torch/ocr.

# ---------------------------------------------------------------------------
# Etapa 1: frontend (Vite + Tailwind)
# ---------------------------------------------------------------------------
# Compila static/dist/ dentro de la imagen para no versionar el build. Tailwind
# escanea frontend/ (los componentes .jsx) y templates/ (la plantilla raíz de
# Inertia) — ver los @source de frontend/styles/app.css.
FROM node:22-slim AS frontend

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY vite.config.js ./
COPY frontend/ ./frontend/
COPY templates/ ./templates/

RUN npm run build

# ---------------------------------------------------------------------------
# Etapa 2: aplicación
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=webapp.settings \
    DJANGO_VITE_DEV=False

WORKDIR /app

# Dependencias del sistema mínimas (Pillow trae wheels; no hace falta compilar).
# curl para el healthcheck del compose; sqlite3 para el backup en caliente
# (`.backup`) que documenta DEPLOY.md, que sin él no se podía ejecutar.
RUN apt-get update && apt-get install -y --no-install-recommends curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-web.txt .
RUN pip install -r requirements-web.txt

COPY . .

# El bundle compilado en la etapa anterior (con su manifest.json).
COPY --from=frontend /build/static/dist/ ./static/dist/

# Recolecta static (WhiteNoise los comprime). No necesita BD.
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# gunicorn por defecto; el worker sobreescribe 'command' en docker-compose.
EXPOSE 8000
CMD ["gunicorn", "webapp.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300"]
