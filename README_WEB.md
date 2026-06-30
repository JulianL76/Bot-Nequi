# Gestor Nequi — Plataforma web

Evolución del bot de Telegram a una plataforma web con base de datos propia,
cuentas de usuario, roles, dashboard y subida masiva de comprobantes. La web y
el bot **comparten la misma base de datos y la misma lógica de extracción de IA**
(paquete `core/`).

## Arquitectura

- `core/` — núcleo compartido: extracción con Groq/Gemini (`extraction.py`),
  parsing de montos (`parsing.py`), cuota (`quota.py`). Sin Django ni Telegram.
- `webapp/` — proyecto Django (settings, urls, Celery).
- `accounts/` — auth, registro, `Negocio`, `PerfilUsuario` (rol + `telegram_id`).
- `comprobantes/` — `Comprobante`, `LoteCarga`, `Notificacion`, subida masiva,
  tarea Celery `procesar_lote`, y el bot (`management/commands/runbot.py`).
- `dashboard/` — métricas, gráficas y exportación a Excel.

## Requisitos

```bash
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y completa las claves (Telegram, Groq, Gemini).

## Puesta en marcha (desarrollo)

```bash
python manage.py migrate
python manage.py createsuperuser        # acceso al admin (Unfold)
python manage.py runserver              # web en http://127.0.0.1:8000
```

### Worker de la cola (procesamiento por lotes)

La subida masiva se procesa en segundo plano en lotes de `BATCH_SIZE` (def. 30).

- **Con Redis** (recomendado; en Windows vía WSL/Docker/Memurai):
  ```bash
  celery -A webapp worker -l info --pool=solo
  ```
- **Sin Redis** (todo en línea, sin worker): en `.env` pon
  `CELERY_TASK_ALWAYS_EAGER=True`.

### Bot de Telegram (misma BD que la web)

```bash
python manage.py runbot
```

Cada usuario de Telegram obtiene automáticamente su `Negocio`. Para unificar la
cuenta web con la de Telegram, asigna el `telegram_id` en el `PerfilUsuario`
desde el admin (así también llegan las notificaciones de fin de lote por Telegram).

## Migrar datos legados

Si tienes `listas_nequi.json` del bot original:

```bash
python manage.py import_json
```

## Producción

Cambiar `DATABASES` a PostgreSQL (ya instalado), `DJANGO_DEBUG=False`,
`collectstatic`, servir con Gunicorn + Nginx y usar Redis real para Celery.

## Frontend (CSS build — Tailwind + DaisyUI)

El CSS se **compila** (ya no se usa el CDN de Tailwind). Design system en
`docs/design-system.md`.

- Fuente: `static_src/app.css` + `tailwind.config.js` (tema DaisyUI `nequi`, violeta/slate).
- Salida servida: `static/css/app.css` (la carga `base.html`).

```bash
npm install          # una vez
npm run build:css    # compila a static/css/app.css (--minify)
npm run watch:css    # recompila al guardar (durante desarrollo)
```

> Importante: al **añadir clases Tailwind nuevas** en los templates hay que
> recompilar (`build:css`) o tener `watch:css` corriendo; si no, las clases
> nuevas no estarán en `app.css`. `node_modules/` está en `.gitignore`;
> `static/css/app.css` sí se versiona para que `runserver` funcione sin build.
