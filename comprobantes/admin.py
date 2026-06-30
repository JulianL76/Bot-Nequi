from django.contrib import admin
from unfold.admin import ModelAdmin

from accounts.utils import get_negocio

from .models import Comprobante, LoteCarga, Notificacion, Ruta


@admin.register(Ruta)
class RutaAdmin(ModelAdmin):
    list_display = ("numero", "nombre", "activa", "creado_en")
    list_filter = ("activa",)
    search_fields = ("numero", "nombre")
    exclude = ("negocio",)  # un solo negocio: se asigna automáticamente

    def save_model(self, request, obj, form, change):
        if not obj.negocio_id:
            obj.negocio = get_negocio(request.user)
        super().save_model(request, obj, form, change)


@admin.register(LoteCarga)
class LoteCargaAdmin(ModelAdmin):
    list_display = ("id", "creado_por", "estado", "procesadas", "total",
                    "exitosas", "fallidas", "duplicadas", "creado_en")
    list_filter = ("estado",)
    date_hierarchy = "creado_en"


@admin.register(Comprobante)
class ComprobanteAdmin(ModelAdmin):
    list_display = ("id", "de", "valor", "ref", "fecha", "fecha_dt", "ruta",
                    "origen", "fuente_ia", "estado", "creado_en")
    list_filter = ("origen", "fuente_ia", "estado", "ruta", "fecha_dt")
    search_fields = ("de", "ref")
    date_hierarchy = "creado_en"
    autocomplete_fields = ("ruta",)


@admin.register(Notificacion)
class NotificacionAdmin(ModelAdmin):
    list_display = ("titulo", "usuario", "leida", "creado_en")
    list_filter = ("leida",)
    search_fields = ("titulo", "usuario__username")
