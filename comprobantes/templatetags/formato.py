"""Filtros de formato para plantillas."""

from django import template

from core.parsing import parse_hora

register = template.Library()


@register.filter
def hora24(value):
    """Normaliza una hora a formato 24h "HH:MM" (p. ej. "5:36 pm" → "17:36")."""
    t = parse_hora(value)
    return t.strftime("%H:%M") if t else (value or "")


@register.filter
def pesos(value):
    """Formatea un monto como moneda colombiana: 100000 → "$100.000,00".

    Reutiliza la misma convención que core.parsing.fmt_total del bot.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    return f"${v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
