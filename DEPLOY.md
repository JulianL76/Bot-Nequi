# Despliegue en VPS (Google Cloud e2-micro, 1 GB)

Stack en Docker: **Caddy** (HTTPS auto) → **gunicorn** (web) + **celery** (worker) + **redis**,
con **SQLite (WAL)** en un volumen. Sin nginx. IA por API (Groq/Gemini), nada de torch/OCR.

## 0. Requisitos en Google Cloud
- VM Compute Engine (e2-micro sirve). Ubuntu 22.04/24.04.
- **Firewall:** permitir tráfico HTTP (80) y HTTPS (443) a la VM.
  Consola → VPC network → Firewall, o marca "Allow HTTP/HTTPS" al crear la VM.
- Anota la **IP externa** de la VM (mejor si es **estática**: VPC → IP addresses → reservar).

## 1. Swap (importante en 1 GB)
Evita que el kernel mate procesos (OOM) en los picos:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h   # verifica que aparezca el swap
```

## 2. Instalar Docker
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# cierra sesión y vuelve a entrar (o: newgrp docker)
```

Las variables (`${VAR}`) del `docker-compose.yml` **no** vienen de un `env_file` — el archivo
`.env.prod` con los secretos está en `.gitignore` a propósito (no se sube al repo), así que Git
nunca lo clona. Hay dos formas de dárselas al stack según cómo despliegues: **A) por SSH con el
CLI** (usando `--env-file`) o **B) desde Portainer** (pegándolas en su UI). Elige una.

## 3. Traer el código
```bash
git clone <URL-de-tu-repo> gestor-nequi
cd gestor-nequi
git checkout feat/webapp-conciliaciones   # o la rama/tag que despliegues
```

## 4. Configurar variables
```bash
cp .env.prod.example .env.prod
nano .env.prod
```
Rellena en `.env.prod`:
- `DOMAIN` y `DJANGO_CSRF_TRUSTED_ORIGINS`: tu IP con **nip.io** y guiones.
  IP `34.120.45.67` → `34-120-45-67.nip.io`.
  (Alternativa nombre bonito: crea uno gratis en https://duckdns.org y úsalo aquí.)
- `DJANGO_SECRET_KEY`: genera una →
  `python3 -c "import secrets;print(secrets.token_urlsafe(50))"`
- `DJANGO_ALLOWED_HOSTS`: incluye tu dominio (deja también `web,localhost`).
- `GROQ_API_KEY` y `GEMINI_API_KEY`.

## 5. Levantar
```bash
docker compose --env-file .env.prod up -d --build
```
`--env-file` es obligatorio: sin él, `${DOMAIN}`, `${DJANGO_SECRET_KEY}`, etc. quedan vacíos.
Primer arranque: Caddy pide el certificado a Let's Encrypt (unos segundos). Debe verse
`certificate obtained successfully` en `docker compose logs caddy`.

## 6. Migraciones + superusuario
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Listo: entra a **https://TU-DOMINIO.nip.io** con HTTPS válido.

## Operación diaria
```bash
docker compose ps                 # estado
docker compose logs -f web        # logs de la web
docker compose logs -f worker     # logs del procesamiento (celery)
docker compose restart worker     # reiniciar tras cambios en tasks/IA
docker stats                      # uso de RAM/CPU (vigilar en 1 GB)
```

### Actualizar a una versión nueva
```bash
git pull
docker compose --env-file .env.prod up -d --build   # reconstruye y reemplaza sin perder datos
docker compose exec web python manage.py migrate
```

## Método B: desplegar desde Portainer (Git)

Si administras la VM con Portainer (Stacks → Add stack → **Repository**), no hay acceso a un
`.env.prod` local: las variables se pegan directamente en la UI de Portainer.

1. **Build method**: `Repository`.
2. **Repository URL**: la URL de tu repo, p. ej. `https://github.com/tu-usuario/Bot-Nequi`.
3. **Repository reference**: `refs/heads/feat/webapp-conciliaciones` (o la rama que despliegues;
   con `refs/heads/<rama>`, no solo el nombre).
4. **Compose path**: `docker-compose.yml` (ya es el valor por defecto).
5. **Authentication**: actívalo solo si el repo es privado (usuario + token de GitHub).
6. Baja hasta **Environment variables** (debajo de "GitOps updates") y agrega, una por una
   (botón "+ add environment variable"), las mismas claves de `.env.prod.example`:

   | name | value |
   |---|---|
   | `DOMAIN` | `34-120-45-67.nip.io` (tu IP con nip.io, o tu dominio de DuckDNS) |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://34-120-45-67.nip.io` |
   | `DJANGO_SECRET_KEY` | genera una con `python3 -c "import secrets;print(secrets.token_urlsafe(50))"` |
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_ALLOWED_HOSTS` | `34-120-45-67.nip.io,web,localhost` |
   | `GROQ_API_KEY` | tu clave de Groq |
   | `GEMINI_API_KEY` | tu clave de Gemini |

7. **Deploy the stack**. Portainer clona el repo, construye la imagen (`build: .` en el compose)
   y levanta los 4 servicios.
8. Migraciones + superusuario: Portainer → Containers → el contenedor `..._web_1` → **Console**
   → `/bin/sh` → Connect, y ahí:
   ```sh
   python manage.py migrate
   python manage.py createsuperuser
   ```
   (o desde tu propia terminal si tienes el cliente Docker apuntando a esa VM:
   `docker exec -it <nombre_del_contenedor_web> python manage.py migrate`).
9. Para actualizar después de un `git push`: Stacks → tu stack → **Pull and redeploy** (o activa
   **GitOps updates** para que Portainer lo haga solo cada cierto intervalo).

Nota: como el `docker-compose.yml` no expone puertos de `web` (solo Caddy publica 80/443), no
hace falta tocar nada de "Access control" de Portainer para la web en sí — solo asegúrate de que
el firewall de la VM permita 80/443 (paso 0).

### Backup (SQLite + imágenes)
Los datos viven en volúmenes Docker (`app-data`, `media`). Copia caliente segura:
```bash
docker compose exec web sh -c "sqlite3 /data/db.sqlite3 '.backup /data/backup.sqlite3'"
docker compose cp web:/data/backup.sqlite3 ./backup-$(date +%F).sqlite3
# imágenes:
docker run --rm -v gestor-nequi_media:/m -v $PWD:/out alpine tar czf /out/media-$(date +%F).tar.gz -C /m .
```

## Notas de recursos (1 GB)
- Uso típico ~350–550 MB (web ~200, worker ~200, redis ~30, caddy ~20) + swap de colchón.
- Mantén **gunicorn workers=2** y **celery concurrency=1** (ya configurado). No los subas.
- Subir 900 imágenes de golpe funciona, pero en 0.25–2 vCPU compartido va lento: mejor en
  tandas de ~150. El progreso se ve en el detalle del lote (pausar/continuar disponible).
- `docker system prune -f` de vez en cuando para liberar imágenes viejas.
