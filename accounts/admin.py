from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Negocio, PerfilUsuario


@admin.register(Negocio)
class NegocioAdmin(ModelAdmin):
    list_display = ("nombre", "titular_nequi", "numero_nequi", "creado_en")
    list_editable = ("titular_nequi", "numero_nequi")
    search_fields = ("nombre", "titular_nequi", "numero_nequi")


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(ModelAdmin):
    list_display = ("user", "negocio", "rol", "telegram_id")
    list_filter = ("rol", "negocio")
    search_fields = ("user__username", "telegram_id")
    autocomplete_fields = ("user", "negocio")
    exclude = ("es_especial",)
