from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Conciliacion, LoteConciliacion


@admin.register(LoteConciliacion)
class LoteConciliacionAdmin(ModelAdmin):
    list_display = ("id", "ruta", "estado", "procesadas", "total",
                    "ok", "pendientes", "no_esta", "creado_en")
    list_filter = ("estado", "ruta")
    date_hierarchy = "creado_en"


@admin.register(Conciliacion)
class ConciliacionAdmin(ModelAdmin):
    list_display = ("id", "ref", "valor", "fecha_dt", "resultado", "ruta",
                    "comprobante", "creado_en")
    list_filter = ("resultado", "ruta")
    search_fields = ("ref", "de")
