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


def push_activo() -> bool:
    """¿Están configuradas las llaves VAPID? Sin ellas el push queda apagado."""
    from django.conf import settings

    return bool(getattr(settings, "VAPID_PUBLIC_KEY", "")
                and getattr(settings, "VAPID_PRIVATE_KEY", ""))


def notificar_push(usuario, titulo, mensaje="", url="/"):
    """Envía una notificación del sistema a todos los dispositivos del usuario.

    Llega aunque la app esté cerrada: el navegador despierta al service worker
    (ver templates/pwa/sw.js). Complementa a `notificar_inapp` y
    `notificar_telegram`; si algo falla, no interrumpe el flujo que la llamó.

    Devuelve cuántos dispositivos recibieron la notificación.
    """
    from django.conf import settings

    from .models import SuscripcionPush

    if not push_activo():
        return 0

    subs = list(SuscripcionPush.objects.filter(usuario=usuario))
    if not subs:
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush no está instalado; no se envían notificaciones push.")
        return 0

    correo = getattr(settings, "VAPID_ADMIN_EMAIL", "") or "admin@example.com"
    carga = json.dumps({"titulo": titulo, "mensaje": mensaje, "url": url})
    enviadas = 0
    muertas = []

    for sub in subs:
        try:
            webpush(
                subscription_info=sub.como_dict(),
                data=carga,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{correo}"},
                timeout=10,
            )
            enviadas += 1
        except WebPushException as e:
            # 404/410 = el navegador desinstaló la app o limpió los datos: la
            # suscripción ya no existe y hay que borrarla para no reintentarla.
            codigo = getattr(e.response, "status_code", None)
            if codigo in (404, 410):
                muertas.append(sub.pk)
            else:
                logger.warning(f"Push falló ({codigo}) para {usuario}: {e}")
        except Exception as e:
            logger.warning(f"Push falló para {usuario}: {e}")

    if muertas:
        SuscripcionPush.objects.filter(pk__in=muertas).delete()
        logger.info(f"Borradas {len(muertas)} suscripción(es) push vencidas.")

    return enviadas
