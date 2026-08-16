# FilePond (auto-hospedado)

Estos archivos se sirven desde el propio servidor en vez de un CDN. Motivo: al
navegar con `hx-boost` los `<script src>` externos cargan de forma asíncrona, así
que con el CDN lento se veía el selector de archivos nativo del navegador antes
de que FilePond lo reemplazara — y si el CDN estaba bloqueado, no cargaba nunca.

Los usa `templates/comprobantes/_filepond_head.html`.

## Versiones fijadas

| Archivo | Paquete npm | Versión |
|---|---|---|
| `filepond.min.css` | `filepond` | 4.32.12 |
| `filepond.min.js` | `filepond` | 4.32.12 |
| `filepond-plugin-file-validate-type.min.js` | `filepond-plugin-file-validate-type` | 1.2.9 |
| `filepond-plugin-file-validate-size.min.js` | `filepond-plugin-file-validate-size` | 2.2.8 |
| `filepond-plugin-image-resize.min.js` | `filepond-plugin-image-resize` | 2.0.10 |
| `filepond-plugin-image-transform.min.js` | `filepond-plugin-image-transform` | 3.8.8 |

Licencia MIT (cada archivo conserva su cabecera).

## Cómo actualizarlos

```bash
cd static/vendor/filepond
V=4.32.12
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond@$V/dist/filepond.min.css"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond@$V/dist/filepond.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-file-validate-type@1.2.9/dist/filepond-plugin-file-validate-type.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-file-validate-size@2.2.8/dist/filepond-plugin-file-validate-size.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-image-resize@2.0.10/dist/filepond-plugin-image-resize.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-image-transform@3.8.8/dist/filepond-plugin-image-transform.min.js"
```

Después actualizá la tabla de arriba y corré `python manage.py collectstatic`
(en producción lo hace el `Dockerfile` al construir la imagen).
