"""Normaliza datos derivados de comprobantes existentes: `fecha_dt` (desde el
texto `fecha`) y `hora` a formato 24h."""

from django.core.management.base import BaseCommand

from comprobantes.models import Comprobante
from conciliaciones.models import Conciliacion
from core.parsing import parse_fecha, parse_hora


class Command(BaseCommand):
    help = "Rellena fecha_dt y normaliza la hora a 24h en comprobantes y conciliaciones existentes."

    def handle(self, *args, **options):
        actualizados_comp = 0
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
                actualizados_comp += 1

        actualizados_conc = 0
        for conc in Conciliacion.objects.all().iterator():
            cambios = {}
            if conc.fecha:
                dt = parse_fecha(conc.fecha)
                if dt != conc.fecha_dt:
                    cambios["fecha_dt"] = dt
            if conc.hora:
                t = parse_hora(conc.hora)
                if t:
                    hora_24 = t.strftime("%H:%M")
                    if hora_24 != conc.hora:
                        cambios["hora"] = hora_24
            if cambios:
                Conciliacion.objects.filter(pk=conc.pk).update(**cambios)
                actualizados_conc += 1

        self.stdout.write(self.style.SUCCESS(
            f"Proceso finalizado. Comprobantes actualizados: {actualizados_comp}. Conciliaciones actualizadas: {actualizados_conc}."
        ))
