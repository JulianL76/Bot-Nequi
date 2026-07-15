"""Utilidades de parsing y formato de montos/duplicados/fechas.

Extraído de bot.py; añade parseo robusto de la fecha/hora que devuelve la IA,
que varía según el banco (Nequi vs Bancolombia).
"""

import re
import unicodedata
from datetime import date, datetime, time

# Mapa de meses (sin acentos, minúscula). Incluye nombres completos y abreviaturas
# (es/en), porque los vouchers de corresponsal imprimen el mes abreviado ("jun", "ene").
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    # Abreviaturas (3-4 letras) ES/EN.
    "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5,
    "jun": 6, "jul": 7, "ago": 8, "aug": 8, "sep": 9, "sept": 9, "set": 9,
    "oct": 10, "nov": 11, "dic": 12, "dec": 12,
}


def _sin_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _norm_nombre(s: str) -> str:
    """Normaliza un nombre para comparar: sin acentos, mayúsculas, espacios colapsados."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", _sin_acentos(str(s)).upper()).strip()


def nombres_coinciden(a, b) -> bool:
    """Compara dos nombres de forma tolerante (acentos, mayúsculas, espacios).

    Coinciden si son iguales o si uno contiene al otro (p. ej. "KAREN ACUNA"
    dentro de "KAREN ACUNA RECARGA"). Si alguno está vacío, devuelve False.
    """
    na, nb = _norm_nombre(a), _norm_nombre(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def numeros_coinciden(a, b) -> bool:
    """Compara dos números telefónicos por sus dígitos (ignora espacios, +57, etc.).

    Coinciden si los últimos 10 dígitos son iguales. Requiere al menos 7 dígitos.
    """
    da = re.sub(r"\D", "", str(a or ""))
    db = re.sub(r"\D", "", str(b or ""))
    if len(da) < 7 or len(db) < 7:
        return False
    return da[-10:] == db[-10:]


def refs_coinciden(ref_voucher, ref_comprobante) -> bool:
    """Compara el APRO de un voucher de corresponsal contra la referencia del
    comprobante Nequi correspondiente (empieza en "S", más larga).

    Los corresponsales (Redeban/Wompi) no emiten una referencia propia: su
    número de APROBACIÓN son los últimos dígitos de la referencia Nequi real.
    Ese APRO normalmente tiene 6 dígitos, pero el voucher a veces lo imprime
    con el/los cero(s) a la izquierda recortados (p. ej. "S65012577" → APRO
    impreso "12577", no "012577"), así que se compara por SUFIJO en vez de
    exigir un slice fijo de 6: coinciden si la referencia del comprobante
    termina exactamente en los dígitos del APRO. Requiere al menos 4 dígitos
    en el APRO para evitar coincidencias por casualidad con muy pocos dígitos.
    """
    dv = re.sub(r"\D", "", str(ref_voucher or ""))
    dc = re.sub(r"\D", "", str(ref_comprobante or ""))
    if len(dv) < 4 or len(dc) < len(dv):
        return False
    return dc.endswith(dv)


def parse_fecha(fecha_str):
    """Convierte la fecha de texto de la IA a `datetime.date`, o None.

    Tolera los formatos reales que varían por banco:
      - Nequi:       "26 de mayo de 2026"  (DD de MES de AAAA)
      - Bancolombia: "26 de mayo 2026"     (DD de MES AAAA, sin el segundo "de")
    Mes en may/min y con/sin acentos. Estrategia por regex (día, mes, año),
    ignorando los "de", para no pelear con `strptime`.
    """
    if not fecha_str or not isinstance(fecha_str, str):
        return None
    txt = _sin_acentos(fecha_str).lower().strip()
    if not txt or "no encontrada" in txt:
        return None
    # Año = primer número de 4 dígitos; día = primer número de 1-2 dígitos.
    anio_m = re.search(r"\b(\d{4})\b", txt)
    dia_m = re.search(r"\b(\d{1,2})\b", txt)
    if not anio_m or not dia_m:
        return None
    # Mes = el primer nombre de mes conocido que aparezca en el texto.
    mes = next((num for nombre, num in _MESES.items()
                if re.search(r"\b" + nombre + r"\b", txt)), None)
    if not mes:
        return None
    try:
        return date(int(anio_m.group(1)), mes, int(dia_m.group(1)))
    except ValueError:
        return None


def parse_hora(hora_str):
    """Convierte la hora de texto a `datetime.time` (24h), o None.

    Maneja los dos formatos reales:
      - Nequi:       "05:43 p. m."  (12h con puntos/espacios am/pm)
      - Bancolombia: "17:32:00"     (24h con segundos)
    """
    if not hora_str or not isinstance(hora_str, str):
        return None
    clean = re.sub(r"p\.?\s*m\.?", "PM", hora_str, flags=re.IGNORECASE)
    clean = re.sub(r"a\.?\s*m\.?", "AM", clean, flags=re.IGNORECASE).strip()
    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(clean, fmt).time()
        except ValueError:
            continue
    return None


def parse_fecha_hora(fecha_str, hora_str=None):
    """Combina fecha + hora en un `datetime` (o None si la fecha no parsea)."""
    d = parse_fecha(fecha_str)
    if not d:
        return None
    t = parse_hora(hora_str) if hora_str else None
    return datetime.combine(d, t or time(0, 0))


def limpiar_monto(valor_str) -> float:
    """Convierte un monto a float, tolerando formato colombiano y anglosajón.

    Ej.: "$1.234,50" (CO) y "$1,234.50" (US) → 1234.5; "$100.000" → 100000.
    Detecta cuál separador es el decimal (el último que aparezca), evitando que
    un monto en formato gringo ("100,000.00") se interprete como 100.
    """
    s = re.sub(r"[^\d.,]", "", str(valor_str))
    if not s:
        return 0.0
    try:
        if "." in s and "," in s:
            # El último separador es el decimal; el otro es de miles.
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            ent, _, dec = s.rpartition(",")
            s = f"{ent}.{dec}" if len(dec) in (1, 2) else s.replace(",", "")
        elif "." in s:
            ent, _, dec = s.rpartition(".")
            # Si tras el punto hay 1-2 dígitos es decimal; si hay 3 es de miles.
            if len(dec) not in (1, 2):
                s = s.replace(".", "")
        return float(s)
    except Exception:
        return 0.0


def buscar_duplicado(user_list, ref):
    """Retorna (idx_1based, item) si la referencia ya existe, sino None.

    `user_list` es una lista de dicts con clave 'ref'.
    """
    if not ref or ref == "No encontrada":
        return None
    for idx, item in enumerate(user_list, 1):
        if item.get('ref', '') == ref:
            return (idx, item)
    return None


def fmt_total(user_list) -> str:
    """Suma los montos de la lista y los formatea como moneda colombiana."""
    total = sum(limpiar_monto(it['valor']) for it in user_list)
    return f"${total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
