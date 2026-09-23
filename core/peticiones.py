"""Lectura uniforme de los datos de un POST.

Las vistas se escribieron contra `request.POST`, que Django solo rellena con
formularios. Inertia envía JSON, así que sin esto cada vista tendría que
ramificar entre los dos formatos.

`datos_post(request)` devuelve un objeto con la misma interfaz mínima de
`request.POST` (`get` y `getlist`) sin importar cómo llegó la petición, de modo
que el cuerpo de la vista no cambia.
"""

import json


class _DatosJSON:
    """Imita `QueryDict` sobre un cuerpo JSON."""

    def __init__(self, datos):
        self._datos = datos if isinstance(datos, dict) else {}

    def get(self, clave, defecto=None):
        valor = self._datos.get(clave, defecto)
        # Un campo repetido en JSON llega como lista; `get` devuelve el último,
        # igual que hace QueryDict.
        if isinstance(valor, list):
            return valor[-1] if valor else defecto
        if valor is None:
            return defecto
        return valor if isinstance(valor, str) else str(valor)

    def getlist(self, clave):
        valor = self._datos.get(clave)
        if valor is None:
            return []
        if isinstance(valor, list):
            return [str(v) for v in valor]
        return [str(valor)]

    def __contains__(self, clave):
        return clave in self._datos

    def __bool__(self):
        return bool(self._datos)


def datos_post(request):
    """Datos del POST, venga como formulario o como JSON."""
    tipo = (request.content_type or "").lower()
    if "application/json" in tipo:
        try:
            return _DatosJSON(json.loads(request.body or b"{}"))
        except ValueError:
            return _DatosJSON({})
    return request.POST
