"""Helpers de acceso: perfil, negocio y restricción por rol."""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import PerfilUsuario


def get_perfil(user) -> PerfilUsuario | None:
    if not user.is_authenticated:
        return None
    return PerfilUsuario.objects.filter(user=user).select_related("negocio").first()


def get_negocio(user):
    perfil = get_perfil(user)
    return perfil.negocio if perfil else None


def admin_required(view_func):
    """Permite el acceso solo a usuarios con rol admin de su negocio."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        perfil = get_perfil(request.user)
        if not perfil or not perfil.es_admin:
            raise PermissionDenied("Requiere rol de administrador.")
        return view_func(request, *args, **kwargs)

    return _wrapped
