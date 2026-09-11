"""Comprobaciones sobre las imágenes que llegan del navegador."""

import logging

logger = logging.getLogger(__name__)

# Diferencia máxima entre el píxel más claro y el más oscuro para considerar
# que la imagen es de un solo color. Un comprobante real, por pálido que sea,
# tiene texto: su rango va de casi 0 a casi 255.
UMBRAL_UNIFORME = 8


def esta_en_blanco(archivo) -> bool:
    """¿La imagen es de un color liso (toda negra, toda blanca)?

    Pasa cuando el redimensionado del navegador falla: el canvas se queda sin
    dibujar y, al pasarlo a JPEG, sale una imagen lisa. Sin esto se guardaría
    una foto inservible que después hace fallar el análisis sin explicar por qué.

    Ante cualquier duda devuelve False: mejor dejar pasar una imagen rara que
    rechazar una buena.
    """
    try:
        from PIL import Image

        archivo.seek(0)
        with Image.open(archivo) as img:
            # A escala de grises y en chico: basta para ver si hay algún contraste.
            gris = img.convert("L")
            if max(gris.size) > 256:
                gris.thumbnail((256, 256))
            minimo, maximo = gris.getextrema()
        return (maximo - minimo) <= UMBRAL_UNIFORME
    except Exception as e:
        logger.warning(f"No se pudo revisar si la imagen está en blanco: {e}")
        return False
    finally:
        try:
            archivo.seek(0)
        except Exception:
            pass


class ImagenEnBlanco(Exception):
    """La imagen recibida es de un color liso: el navegador no la dibujó bien."""
