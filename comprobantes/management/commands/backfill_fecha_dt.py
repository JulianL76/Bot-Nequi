"""Normaliza datos derivados de comprobantes existentes: `fecha_dt` (desde el
texto `fecha`) y `hora` a formato 24h."""

from django.core.management.base import BaseCommand

from comprobantes.models import Comprobante
from core.parsing import parse_fecha, parse_hora


class Command(BaseCommand):
    help = "Rellena fecha_dt y normaliza la hora a 24h en los comprobantes existentes."

    def handle(self, *args, **options):
        actualizados = 0
        for comp in Comprobante.objects.all().iterator():
            cambios = {}
            dt = parse_fecha(comp.fecha)
            if dt != comp.fecha_dt:
                cambios["fecha_dt"] = dt
            t = parse_hora(comp.hora)
            if t:
                hora_24 = t.strftime("%H:%M")
                if hora_24 != comp.hora:
                    cambios["hora"] = hora_24
            if cambios:
                Comprobante.objects.filter(pk=comp.pk).update(**cambios)
                actualizados += 1
        self.stdout.write(self.style.SUCCESS(
            f"Comprobantes actualizados: {actualizados}."
        ))
