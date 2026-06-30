from .models import Notificacion


def notificaciones_no_leidas(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "notif_no_leidas": Notificacion.objects.filter(
            usuario=request.user, leida=False
        ).count()
    }
