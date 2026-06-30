"""Genera los iconos PNG de la PWA (192 y 512) con Pillow."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

VIOLETA = (124, 58, 237, 255)


def _fuente(size):
    for ruta in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, size)
    return ImageFont.load_default()


class Command(BaseCommand):
    help = "Genera static/icons/icon-192.png y icon-512.png para la PWA."

    def handle(self, *args, **options):
        destino = os.path.join(settings.BASE_DIR, "static", "icons")
        os.makedirs(destino, exist_ok=True)

        for size in (192, 512):
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            radio = int(size * 0.22)
            d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radio, fill=VIOLETA)
            txt = "$"
            font = _fuente(int(size * 0.6))
            l, t, r, b = d.textbbox((0, 0), txt, font=font)
            d.text(((size - (r - l)) / 2 - l, (size - (b - t)) / 2 - t),
                   txt, font=font, fill=(255, 255, 255, 255))
            ruta = os.path.join(destino, f"icon-{size}.png")
            img.save(ruta, "PNG")
            self.stdout.write(self.style.SUCCESS(f"Generado {ruta}"))
