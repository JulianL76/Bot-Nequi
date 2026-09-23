"""Props que toda página de Inertia recibe sin pedirlas.

El armazón de React (barra lateral, topbar, avisos) necesita los mismos datos
en cada pantalla. En vez de repetirlos en las veinte vistas, se comparten aquí
una sola vez.

Las URLs también viajan desde acá a propósito: son el reverse de Django, así
que el front nunca escribe rutas a mano y un cambio en `urls.py` no deja
enlaces rotos en el JavaScript.
"""

from django.contrib.messages import get_messages
from django.urls import reverse
from inertia import share

from comprobantes.models import Notificacion

# Nombre de ruta -> clave con la que el front la pide. Solo las de navegación:
# las que reciben argumentos se construyen en el componente que las usa.
RUTAS_NAVEGACION = {
    "inicio": "dashboard:home",
    "pendientes": "dashboard:pendientes",
    "comprobantes": "comprobantes:lista",
    "subir": "comprobantes:subir",
    "subidas": "comprobantes:lotes",
    "enProceso": "comprobantes:en_proceso",
    "importar": "comprobantes:importar",
    "exportarComprobantes": "comprobantes:exportar_lista",
    "accionesLote": "comprobantes:acciones_lote",
    "conciliar": "conciliaciones:conciliar",
    "conciliaciones": "conciliaciones:lista",
    "panel": "conciliaciones:panel",
    "exportarPanel": "conciliaciones:exportar_panel",
    "rutas": "comprobantes:rutas",
    "notificaciones": "comprobantes:notificaciones",
    "admin": "admin:index",
    "salir": "logout",
    "entrar": "login",
    "registro": "registro",
}

_TONO_MENSAJE = {"error": "error", "warning": "warning", "success": "success", "info": "info"}


class InertiaSharedMiddleware:
    """Comparte usuario, avisos y URLs con cada respuesta de Inertia."""

    def __init__(self, get_response):
        self.get_response = get_response
        # El reverse no cambia durante el proceso: se resuelve una vez.
        self._urls = {clave: reverse(nombre) for clave, nombre in RUTAS_NAVEGACION.items()}

    def __call__(self, request):
        usuario = getattr(request, "user", None)

        share(
            request,
            urls=self._urls,
            auth={
                "usuario": {
                    "nombre": usuario.get_username(),
                    "esAdmin": usuario.is_superuser,
                    "iniciales": usuario.get_username()[:2].upper(),
                }
                if usuario and usuario.is_authenticated
                else None,
            },
            # Contador de avisos: se calcula perezosamente para no golpear la
            # base en cada petición que no lo necesite (descargas, JSON…).
            avisos=lambda: (
                Notificacion.objects.filter(usuario=usuario, leida=False).count()
                if usuario and usuario.is_authenticated
                else 0
            ),
            # `flash` se consume al leerlo: los mensajes de Django son de un
            # solo uso, y aquí se convierten en toasts del front.
            flash=lambda: [
                {"texto": str(m), "tono": _TONO_MENSAJE.get(m.level_tag, "info")}
                for m in get_messages(request)
            ],
        )

        return self.get_response(request)
