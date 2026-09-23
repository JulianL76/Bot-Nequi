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

## Frontend (React + Inertia + Vite)

Django **no renderiza HTML de páginas**: cada vista devuelve props y la
pantalla es un componente de React. El puente es [Inertia](https://inertiajs.com),
así que no hay API REST que mantener aparte — las vistas siguen siendo vistas de
Django, con sus sesiones, permisos y `messages`.

```
frontend/
  app.jsx            punto de entrada: monta Inertia y resuelve las páginas
  Layout.jsx         armazón (barra lateral, topbar, barra inferior, toasts)
  Pages/             una carpeta por app de Django; el nombre es el que manda la vista
    Dashboard/Home.jsx        ← inertia_render(request, "Dashboard/Home", props=...)
    Comprobantes/Lista.jsx
    Conciliaciones/Panel.jsx
  components/        piezas con lógica: tabla, gráficas, visor, paleta, subida
  ui/                kit de interfaz sobre el design system (Button, Card, Dialog…)
  lib/               formato, rutas, selección persistente, sondeo de progreso
  styles/            tokens + componentes en CSS
```

```bash
npm install     # una vez
npm run dev     # servidor de Vite con HMR (junto a manage.py runserver)
npm run build   # compila static/dist/ + manifest.json
```

### Cómo se conecta una pantalla nueva

1. La vista devuelve props en vez de renderizar:
   `return inertia_render(request, "Comprobantes/Lista", props={...})`
2. Se crea `frontend/Pages/Comprobantes/Lista.jsx`; recibe esas props.
3. Nada más: el `resolve` de `app.jsx` encuentra el archivo por su nombre.

Los formularios y acciones usan `useForm`/`router` de Inertia, que envían JSON.
Las vistas lo leen con `core.peticiones.datos_post()`, que acepta tanto
formulario como JSON — por eso siguen funcionando los envíos sin JavaScript.

### Props compartidas

`webapp/inertia_shared.py` inyecta en **todas** las páginas: el usuario, el
contador de avisos, los `messages` de Django (que el front convierte en toasts)
y **las URLs resueltas con `reverse`**, para que el JavaScript nunca escriba una
ruta a mano.

### Detalles que conviene saber

- **En desarrollo** (`DJANGO_DEBUG=True`) Django apunta al servidor de Vite en
  `localhost:5173`. Para trabajar contra el bundle compilado: `DJANGO_VITE_DEV=False`
  y `npm run build`.
- **En producción** el `Dockerfile` compila el frontend en una etapa con Node y
  copia `static/dist/`; por eso ese directorio **no** se versiona. Sin Docker,
  corre `npm run build` antes de `collectstatic`.
- **Cada página es un trozo aparte** (el `import.meta.glob` no es `eager`): el
  armazón pesa ~155 kB comprimidos y cada pantalla añade entre 2 y 45 kB.
- **Tailwind 4 se configura en CSS**, no en `tailwind.config.js` (ya no existe).
  Lo que escanea son los `@source` de `frontend/styles/app.css`.
- **El motor de subida de FilePond** (`static/vendor/filepond/motor-subida.js`)
  es JavaScript clásico a propósito: está afinado para subir cientos de fotos
  desde un celular con red inestable. React solo lo monta y le pasa la config.

Design system en `docs/design-system.md`.
