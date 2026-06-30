"""Envío de notificaciones in-app y por Telegram."""

import json
import logging
import urllib.parse
import urllib.request

from core import config

from .models import Notificacion

logger = logging.getLogger(__name__)


def notificar_inapp(usuario, titulo, mensaje=""):
    return Notificacion.objects.create(usuario=usuario, titulo=titulo, mensaje=mensaje)


def notificar_telegram(telegram_id, texto):
    """Envía un mensaje al usuario vía Bot API (HTTP simple, sin libs async)."""
    if not telegram_id or not config.TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": telegram_id, "text": texto, "parse_mode": "HTML",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación de Telegram: {e}")
        return False
