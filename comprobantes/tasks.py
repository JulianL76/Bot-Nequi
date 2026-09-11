"""Tarea Celery: procesa un lote de comprobantes en segundo plano por chunks.

Subir ~200 imágenes a la vez y procesarlas en lotes de BATCH_SIZE (def. 30)
para no saturar la IA (evitar 429 de Groq/Gemini). Al terminar notifica al
usuario in-app y por Telegram.
"""

import logging
import os
import time

from celery import shared_task
from django.conf import settings
from django.core.files import File
from django.utils import timezone

from accounts.utils import get_perfil
from core.extraction import analizar_comprobante_sync
from core.parsing import limpiar_monto

from .models import ArchivoPendiente, Comprobante, LoteCarga
from .notifications import notificar_inapp, notificar_push, notificar_telegram

logger = logging.getLogger(__name__)

# Pausa mínima de cortesía entre imágenes. El límite real de Groq (30 RPM) ya
# lo respeta el throttle interno de _analizar_con_groq (core/extraction.py),
# y Gemini en tier pago soporta muchas más RPM de las que este flujo genera,
# así que esta pausa NO es lo que evita los 429 — solo evita ráfagas bruscas.
# Configurable por entorno si hace falta ajustarla.
PAUSA_ENTRE_IMAGENES = float(os.getenv("PAUSA_ENTRE_IMAGENES", "0.3"))
PAUSA_ENTRE_LOTES = 2     # segundos entre chunks (suaviza el RPM)
BACKOFF_429 = 65          # segundos de espera ante un 429 antes de reintentar


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _procesar_archivo(arch: ArchivoPendiente, lote: LoteCarga) -> str:
    """Analiza una imagen pendiente y, si hay datos, crea el Comprobante.

    Devuelve 'ok' | 'dup' | 'fail'. El comprobante solo se crea tras un análisis
    exitoso (no se guarda nada vacío al subir). Lanza RuntimeError (429) si se
    agota la cuota.
    """
    datos, fuente = analizar_comprobante_sync(arch.imagen.path)
    if not datos:
        return "fail"

    ref = (datos.get("ref") or "").strip()
    # Duplicado dentro del negocio: ya existe un original con la misma ref.
    # El original es el MÁS ANTIGUO (por fecha de creación).
    original = None
    if ref and ref != "No encontrada":
        original = (Comprobante.objects.filter(
            negocio=lote.negocio, ref=ref, es_duplicado=False
        ).order_by("creado_en", "id").first())

    comp = Comprobante(
        negocio=lote.negocio, creado_por=lote.creado_por, lote=lote,
        de=datos.get("de", "No encontrada"),
        valor=limpiar_monto(datos.get("valor", "0")),
        valor_raw=datos.get("valor", ""),
        fecha=datos.get("fecha", ""),
        hora=datos.get("hora", ""),
        ref=ref, fuente_ia=fuente or "", origen=Comprobante.ORIGEN_WEB,
        es_duplicado=original is not None, duplicado_de=original,
    )
    # Copiar la imagen de staging al comprobante (archivo independiente).
    with open(arch.imagen.path, "rb") as fh:
        comp.imagen.save(os.path.basename(arch.imagen.name), File(fh), save=False)
    comp.save()
    return "dup" if original is not None else "ok"


@shared_task
def procesar_lote(lote_id: int):
    try:
        lote = LoteCarga.objects.get(pk=lote_id)
    except LoteCarga.DoesNotExist:
        logger.error(f"Lote {lote_id} no existe")
        return

    try:
        lote.estado = LoteCarga.PROCESANDO
        lote.save(update_fields=["estado"])
    except Exception as e:
        if type(e).__name__ == "NotUpdated":
            logger.info(f"Lote {lote_id} fue eliminado antes de procesar.")
            return
        raise

    # Solo los pendientes (fallido=False). Así el lote es reanudable tras pausar.
    archivos = list(lote.archivos.filter(fallido=False).order_by("id"))
    batch_size = getattr(settings, "BATCH_SIZE", 30)

    for chunk in _chunks(archivos, batch_size):
        for arch in chunk:
            # Pausa cooperativa: si el usuario pausó, salimos dejando lo pendiente.
            if LoteCarga.objects.filter(pk=lote_id, estado=LoteCarga.PAUSADO).exists():
                logger.info(f"Lote {lote_id} pausado; deteniendo procesamiento.")
                return

            error_msg = ""
            try:
                resultado = _procesar_archivo(arch, lote)
            except RuntimeError as e:
                # Cuota agotada (429): esperar y reintentar una vez.
                logger.warning(f"429 en lote {lote_id}: {e}. Esperando {BACKOFF_429}s")
                time.sleep(BACKOFF_429)
                try:
                    resultado = _procesar_archivo(arch, lote)
                except Exception as e2:
                    logger.error(f"Reintento falló: {e2}")
                    resultado, error_msg = "fail", str(e2)
            except Exception as e:
                logger.error(f"Error procesando archivo {arch.pk}: {e}")
                resultado, error_msg = "fail", str(e)

            if resultado == "fail" and not error_msg:
                error_msg = "La IA no pudo extraer datos de la imagen."

            lote.procesadas += 1
            if resultado == "ok":
                lote.exitosas += 1
            elif resultado == "dup":
                lote.duplicadas += 1
            else:
                lote.fallidas += 1
                
            try:
                lote.save(update_fields=["procesadas", "exitosas", "duplicadas", "fallidas"])
            except Exception as e:
                if type(e).__name__ == "NotUpdated":
                    logger.warning(f"Lote {lote_id} fue eliminado durante el procesamiento. Abortando.")
                    return
                raise

            # Si fue ok/dup, el comprobante (si hubo) ya tiene su copia → borrar staging.
            # Si falló, conservar el archivo marcado (con su error) para reprocesarlo.
            if resultado in ("ok", "dup"):
                arch.delete()
            else:
                arch.fallido = True
                arch.error = error_msg
                try:
                    arch.save(update_fields=["fallido", "error"])
                except Exception as e:
                    if type(e).__name__ == "NotUpdated":
                        pass
                    else:
                        raise

            time.sleep(PAUSA_ENTRE_IMAGENES)

        time.sleep(PAUSA_ENTRE_LOTES)

    _finalizar_lote(lote)


@shared_task
def reprocesar_lote(lote_id: int):
    """Reintenta solo las imágenes fallidas de un lote, ajustando los contadores."""
    try:
        lote = LoteCarga.objects.get(pk=lote_id)
    except LoteCarga.DoesNotExist:
        logger.error(f"Lote {lote_id} no existe")
        return

    fallidos = list(lote.archivos.filter(fallido=True).order_by("id"))
    if not fallidos:
        return

    try:
        lote.estado = LoteCarga.PROCESANDO
        lote.save(update_fields=["estado"])
    except Exception as e:
        if type(e).__name__ == "NotUpdated":
            logger.info(f"Lote {lote_id} fue eliminado antes de reprocesar.")
            return
        raise
    batch_size = getattr(settings, "BATCH_SIZE", 30)

    for chunk in _chunks(fallidos, batch_size):
        for arch in chunk:
            error_msg = ""
            try:
                resultado = _procesar_archivo(arch, lote)
            except RuntimeError as e:
                logger.warning(f"429 al reprocesar {lote_id}: {e}. Esperando {BACKOFF_429}s")
                time.sleep(BACKOFF_429)
                try:
                    resultado = _procesar_archivo(arch, lote)
                except Exception as e2:
                    logger.error(f"Reintento falló: {e2}")
                    resultado, error_msg = "fail", str(e2)
            except Exception as e:
                logger.error(f"Error reprocesando archivo {arch.pk}: {e}")
                resultado, error_msg = "fail", str(e)

            if resultado in ("ok", "dup"):
                # Pasa de fallida a exitosa/duplicada.
                lote.fallidas = max(lote.fallidas - 1, 0)
                if resultado == "ok":
                    lote.exitosas += 1
                else:
                    lote.duplicadas += 1
                
                try:
                    lote.save(update_fields=["fallidas", "exitosas", "duplicadas"])
                except Exception as e:
                    if type(e).__name__ == "NotUpdated":
                        logger.warning(f"Lote {lote_id} fue eliminado durante el reprocesamiento. Abortando.")
                        return
                    raise
                
                arch.delete()
            else:
                # Sigue fallando: actualizar el motivo del error.
                arch.error = error_msg or "La IA no pudo extraer datos de la imagen."
                try:
                    arch.save(update_fields=["error"])
                except Exception as e:
                    if type(e).__name__ == "NotUpdated":
                        pass
                    else:
                        raise
            time.sleep(PAUSA_ENTRE_IMAGENES)
        time.sleep(PAUSA_ENTRE_LOTES)

    _finalizar_lote(lote)


def _finalizar_lote(lote: LoteCarga):
    """Fija el estado final del lote según lo que quede pendiente.

    Si aún hay imágenes sin procesar (p. ej. el lote se pausó antes de llegar a
    ellas), NO se marca como completado: queda en pausa para poder reanudar.
    """
    pendientes = lote.archivos.filter(fallido=False).count()
    if pendientes:
        lote.estado = LoteCarga.PAUSADO
        try:
            lote.save(update_fields=["estado"])
        except Exception as e:
            if type(e).__name__ == "NotUpdated":
                pass
            else:
                raise
        return

    lote.estado = LoteCarga.COMPLETADO if lote.fallidas == 0 else LoteCarga.CON_ERRORES
    lote.terminado_en = timezone.now()
    
    try:
        lote.save(update_fields=["estado", "terminado_en"])
    except Exception as e:
        if type(e).__name__ == "NotUpdated":
            return
        raise
        
    _notificar_fin(lote)


def _notificar_fin(lote: LoteCarga):
    titulo = f"Lote #{lote.pk} terminado"
    mensaje = (
        f"Total: {lote.total} · Exitosas: {lote.exitosas} · "
        f"Duplicadas: {lote.duplicadas} · Fallidas: {lote.fallidas}"
    )
    if lote.creado_por:
        notificar_inapp(lote.creado_por, titulo, mensaje)
        notificar_push(lote.creado_por, titulo, mensaje,
                       url=f"/comprobantes/lote/{lote.pk}/")
        perfil = get_perfil(lote.creado_por)
        if perfil and perfil.telegram_id:
            notificar_telegram(perfil.telegram_id, f"✅ <b>{titulo}</b>\n{mensaje}")
