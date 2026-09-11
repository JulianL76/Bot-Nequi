"""Expansión de archivos .zip subidos: saca las imágenes que traen dentro.

Sirve para cargar de golpe una carpeta de capturas ya comprimida (lo típico
al pasarlas del celular al PC). Cada imagen del zip se convierte en un archivo
pendiente más del lote, igual que si se hubiera seleccionado a mano.
"""

import logging
import os
import zipfile

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename

logger = logging.getLogger(__name__)

# Solo formatos que Pillow puede abrir después (ver core/extraction.py). Los
# .heic de iPhone NO entran: sin pillow-heif el análisis fallaría igual, así
# que es mejor descartarlos aquí y avisar cuántos se omitieron.
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

MAX_IMAGENES_ZIP = 900
MAX_BYTES_IMAGEN = 25 * 1024 * 1024
MAX_MB_ZIP = 200          # por si se usa fuera de Django (bot); settings manda


def _tope_mb() -> int:
    """Tope de tamaño del zip, de settings.MAX_ZIP_MB si Django está disponible."""
    try:
        from django.conf import settings

        return int(getattr(settings, "MAX_ZIP_MB", MAX_MB_ZIP))
    except Exception:
        return MAX_MB_ZIP


class ZipInvalido(Exception):
    """El archivo no se pudo abrir como zip."""


def es_zip(archivo) -> bool:
    """¿El archivo subido es un .zip? (por extensión o content-type)."""
    nombre = (getattr(archivo, "name", "") or "").lower()
    if nombre.endswith(".zip"):
        return True
    tipo = (getattr(archivo, "content_type", "") or "").lower()
    return tipo in {"application/zip", "application/x-zip-compressed", "multipart/x-zip"}


class ResumenZip:
    """Cuenta lo que salió del zip. Lo llena `imagenes_de_zip` al recorrerlo."""

    def __init__(self):
        self.imagenes = 0   # entradas entregadas como imagen
        self.omitidas = 0   # descartadas: formato no soportado, vacías o enormes


def imagenes_de_zip(archivo, resumen=None, max_imagenes=MAX_IMAGENES_ZIP):
    """Genera las imágenes del zip como `ContentFile`, una a una.

    Es un generador a propósito: un zip de 900 fotos no cabe en memoria, así que
    cada imagen se entrega para guardarla y se libera antes de leer la siguiente.
    El recuento final queda en `resumen` (un `ResumenZip`) al agotar el generador.
    """
    resumen = resumen if resumen is not None else ResumenZip()

    tope = _tope_mb()
    tam = getattr(archivo, "size", 0) or 0
    if tam > tope * 1024 * 1024:
        raise ZipInvalido(
            f"El .zip pesa {tam / 1024 / 1024:.0f} MB y el máximo son {tope} MB. "
            f"Dividilo en partes más chicas."
        )

    try:
        zf = zipfile.ZipFile(archivo)
    except (zipfile.BadZipFile, OSError) as e:
        raise ZipInvalido("El archivo .zip está dañado o no es un zip válido.") from e

    with zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX/"):
                continue

            # Nunca se usa la ruta que trae el zip para escribir: solo el nombre
            # base saneado. Eso descarta de raíz el "zip slip" (../../etc/passwd)
            # y los separadores de Windows.
            base = os.path.basename(info.filename.replace("\\", "/"))
            if not base or base.startswith("."):
                continue

            if os.path.splitext(base)[1].lower() not in EXTENSIONES_IMAGEN:
                resumen.omitidas += 1
                continue

            if resumen.imagenes >= max_imagenes:
                resumen.omitidas += 1
                continue

            try:
                with zf.open(info) as fh:
                    # Lectura acotada: un zip "bomba" declara poco tamaño en la
                    # cabecera y descomprime gigas. Se lee un byte de más para
                    # detectar el exceso sin cargar todo.
                    datos = fh.read(MAX_BYTES_IMAGEN + 1)
            except Exception as e:
                logger.warning(f"Entrada ilegible en el zip ({info.filename}): {e}")
                resumen.omitidas += 1
                continue

            if not datos or len(datos) > MAX_BYTES_IMAGEN:
                resumen.omitidas += 1
                continue

            try:
                nombre = get_valid_filename(base)
            except SuspiciousFileOperation:
                # Nombre que no deja nada utilizable al sanearlo.
                nombre = ""
            resumen.imagenes += 1
            yield ContentFile(datos, name=nombre or f"imagen_{resumen.imagenes}.jpg")
