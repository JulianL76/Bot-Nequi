from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Negocio, PerfilUsuario

# Django registra User y Group con sus propias clases admin, que no heredan de
# Unfold: por eso su changelist perdía la barra de acciones y el botón "Añadir".
# Se reemplazan por versiones basadas en ModelAdmin de Unfold.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


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
