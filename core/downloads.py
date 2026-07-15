"""Utilidades para nombres de archivos de descarga.

Genera nombres distintivos (con los filtros aplicados y la fecha) para que
exportaciones repetidas no se sobrescriban ni se confundan entre sí.
"""

from datetime import date


def nombre_descarga(base, extra=None, ext="xlsx"):
    """Arma un nombre de archivo distintivo: `base[_extra]_YYYY-MM-DD.ext`.

    - `base`: prefijo temático (p. ej. "comprobantes", "conciliaciones").
    - `extra`: lista de fragmentos ya legibles (p. ej. ["subida-12"], ["2026-07-01_a_2026-07-15"]).
    - `ext`: extensión sin punto.
    """
    partes = [base]
    for fragmento in (extra or []):
        frag = str(fragmento).strip()
        if frag:
            partes.append(frag)
    partes.append(date.today().isoformat())
    return "_".join(partes) + f".{ext}"
