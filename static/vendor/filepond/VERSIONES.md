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

Licencia MIT (cada archivo conserva su cabecera).

## Por qué NO están los plugins de imagen

`filepond-plugin-image-resize` y `filepond-plugin-image-transform` se quitaron a
propósito. Redimensionaban cada foto en el navegador antes de subirla, y eso daba
dos problemas con las imágenes reales de este negocio (capturas de WhatsApp, unos
702x1600 y 79 KB):

1. **Imágenes totalmente negras.** El plugin dibuja sobre un canvas que arranca
   transparente; si `drawImage` falla (pasa en Android), el canvas queda vacío y
   al codificarlo a JPEG sale negro. Verificado en Chrome: canvas sin fondo -> JPEG
   -> rgb(0,0,0).
2. **No ahorraba nada y perdía calidad.** Bajar 702x1600 a 1024 de lado ("contain")
   deja 449x1024: un 36% menos de resolución para leer la referencia, reencodando
   un JPEG que WhatsApp ya había comprimido. El peso pasaba de 79 KB a ~40 KB.

Las imágenes se suben tal cual y el servidor ya las redimensiona a 1024 px antes
de mandarlas a la IA (`core/extraction.py::_resize_image`). Si alguna vez se
reactivan, hay que pasar `imageTransformCanvasBackgroundColor: '#ffffff'`.

## Cómo actualizarlos

```bash
cd static/vendor/filepond
V=4.32.12
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond@$V/dist/filepond.min.css"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond@$V/dist/filepond.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-file-validate-type@1.2.9/dist/filepond-plugin-file-validate-type.min.js"
curl -sSfL -O "https://cdn.jsdelivr.net/npm/filepond-plugin-file-validate-size@2.2.8/dist/filepond-plugin-file-validate-size.min.js"
```

Después actualizá la tabla de arriba y corré `python manage.py collectstatic`
(en producción lo hace el `Dockerfile` al construir la imagen).
