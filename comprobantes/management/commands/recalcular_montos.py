"""Recalcula el campo `valor` de los comprobantes a partir de `valor_raw`.

Corrige montos mal guardados por la versión anterior de limpiar_monto (que no
entendía el formato anglosajón, p. ej. "$100,000.00" → 100 en vez de 100000).
"""

from django.core.management.base import BaseCommand

from comprobantes.models import Comprobante
from core.parsing import limpiar_monto


class Command(BaseCommand):
    help = "Recalcula `valor` desde `valor_raw` con la función de limpieza corregida."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Muestra los cambios sin guardarlos.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        corregidos = 0
        for comp in Comprobante.objects.exclude(valor_raw="").iterator():
            nuevo = limpiar_monto(comp.valor_raw)
            if nuevo and abs(float(comp.valor) - nuevo) > 0.001:
                self.stdout.write(
                    f"#{comp.pk}  {comp.valor_raw!r}:  {comp.valor} -> {nuevo}"
                )
                if not dry:
                    Comprobante.objects.filter(pk=comp.pk).update(valor=nuevo)
                corregidos += 1
        accion = "Se corregirían" if dry else "Corregidos"
        self.stdout.write(self.style.SUCCESS(f"{accion} {corregidos} comprobante(s)."))
