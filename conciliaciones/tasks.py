"""Tarea Celery: concilia un lote de imágenes contra los comprobantes registrados.

Por cada imagen subida (asociada a una ruta) se extrae ref/monto/fecha con la IA
y se busca el comprobante correspondiente:
  - filtro por día (fecha parseada) para acotar la búsqueda,
  - regla autoritativa: referencia + monto.
Resultados: OK (confirma el comprobante y le asigna la ruta), Pendiente (ref igual
pero monto distinto) o No está (ref inexistente). Procesa por chunks con back-off.
"""

import logging
import time

from celery import shared_task
from django.utils import timezone

from accounts.utils import get_perfil
from comprobantes.models import Comprobante
from comprobantes.notifications import notificar_inapp, notificar_telegram
from comprobantes.tasks import BACKOFF_429, PAUSA_ENTRE_IMAGENES, PAUSA_ENTRE_LOTES, _chunks
from core.extraction import analizar_comprobante_sync
from core.parsing import (limpiar_monto, nombres_coinciden, numeros_coinciden,
                           parse_fecha, parse_hora, refs_coinciden)
from django.conf import settings

from .models import Conciliacion, LoteConciliacion

logger = logging.getLogger(__name__)


def _marcar_revision(item: Conciliacion, motivo: str) -> str:
    item.resultado = Conciliacion.REVISION
    item.motivo_revision = motivo
    item.save()
    return "revision"


def _comp_candidato(item: Conciliacion):
    """Devuelve el Comprobante candidato (sin confirmar) según el tipo del item.

    - nequi con ref reconocible (empieza por "M" o "S") → por esa referencia (mismo día).
    - voucher, o nequi sin ref reconocible (se da por no encontrada) → por
      monto + fecha + HORA (para no confundir pagos del mismo monto/día).
    """
    base = Comprobante.objects.filter(negocio=item.negocio)
    if item.fecha_dt:
        base = base.filter(fecha_dt=item.fecha_dt)

    # Preferir el original (es_duplicado=False) y, dentro, el más antiguo.
    orden = ("es_duplicado", "creado_en", "id")

    ref = (item.ref or "").strip()
    ref_reconocible = ref.upper().startswith(("M", "S"))

    if item.tipo == Conciliacion.TIPO_NEQUI and ref and ref.lower() != "no encontrada" and ref_reconocible:
        return base.filter(ref=ref).order_by(*orden).first()

    # Voucher, o Nequi con una referencia que no empieza por M/S (no es una
    # referencia Nequi reconocible, se da por no encontrada): monto+fecha+hora.
    qs = base.filter(valor=item.valor)
    if item.tipo == Conciliacion.TIPO_VOUCHER:
        # Un voucher (corresponsal) NO debe casar con una transferencia Nequi:
        # esas tienen referencia que empieza por "M". Se excluyen para no robarles
        # su comprobante a los ítems Nequi.
        qs = qs.exclude(ref__istartswith="M")
    # La hora distingue pagos iguales del mismo día; debe coincidir.
    t = parse_hora(item.hora)
    if t:
        qs = qs.filter(hora=t.strftime("%H:%M"))
    return qs.order_by(*orden).first()


def _detectar_duplicado(item: Conciliacion, comp: Comprobante) -> str:
    """Devuelve el texto de aviso si el pago (comprobante) ya está conciliado, o ''."""
    # Ya confirmado por una ruta en OTRA conciliación.
    prev = (Conciliacion.objects
            .filter(comprobante=comp, resultado=Conciliacion.OK)
            .exclude(lote_id=item.lote_id)
            .select_related("lote", "lote__ruta")
            .order_by("creado_en").first())
    if prev:
        ruta_txt = (f"Ruta {prev.lote.ruta.numero}"
                    if prev.lote and prev.lote.ruta else "sin ruta")
        return f"Ya confirmado en conciliación #{prev.lote_id} · {ruta_txt}"

    # Repetido dentro de la MISMA conciliación.
    mismo = (Conciliacion.objects
             .filter(lote_id=item.lote_id, comprobante=comp, resultado=Conciliacion.OK)
             .exclude(pk=item.pk).exists())
    if mismo:
        return "Repetido en esta conciliación"
    return ""


def validar_y_emparejar(item: Conciliacion, lote: LoteConciliacion) -> str:
    """Valida (tipo/titular/legibilidad) y empareja usando los datos YA guardados.

    No llama a la IA: sirve para el flujo automático y para reprocesar tras un ajuste.
    Devuelve 'ok' | 'pendiente' | 'no_esta' | 'revision' | 'duplicado'.
    """
    item.aviso = ""
    item.motivo_revision = ""
    tipo = (item.tipo or "").strip().lower()
    para = (item.para or "").strip()
    titular = (item.negocio.titular_nequi or "").strip()
    numero = (item.negocio.numero_nequi or "").strip()

    # 1. Detección / legibilidad.
    if tipo not in (Conciliacion.TIPO_VOUCHER, Conciliacion.TIPO_NEQUI):
        return _marcar_revision(item, "No se pudo identificar el tipo de imagen")
    if tipo == Conciliacion.TIPO_VOUCHER and (
        float(item.valor or 0) <= 0 or item.fecha_dt is None or parse_hora(item.hora) is None
    ):
        return _marcar_revision(item, "Monto, fecha u hora ilegibles en el voucher")

    # 2. Validar destinatario: por NOMBRE o por NÚMERO Nequi (el nombre a veces varía).
    nombre_ok = bool(titular) and nombres_coinciden(para, titular)
    num_ok = bool(numero) and numeros_coinciden(item.num, numero)
    if titular or numero:
        if not (nombre_ok or num_ok):
            ref_txt = titular or numero
            return _marcar_revision(item, f"El destinatario no es {ref_txt} (ni nombre ni número)")
    elif not para or para.lower() == "no encontrada":
        # Sin titular/número configurado: al menos exigir leer un destinatario.
        return _marcar_revision(item, "No se pudo leer el destinatario/titular")

    # 3. Buscar comprobante candidato.
    comp = _comp_candidato(item)
    if not comp:
        item.comprobante = None
        item.resultado = Conciliacion.NO_ESTA
        item.save()
        return "no_esta"

    # Nequi: ref encontrada pero monto distinto → discrepancia a revisar.
    if tipo == Conciliacion.TIPO_NEQUI and abs(float(comp.valor) - float(item.valor or 0)) >= 0.01:
        item.comprobante = comp
        item.resultado = Conciliacion.PENDIENTE
        item.save()
        return "pendiente"

    # Voucher: si se pudo leer el APRO (nunca trae letras, son solo los
    # últimos dígitos de la referencia Nequi real), debe ser sufijo de la
    # referencia del candidato (monto+hora iguales no bastan para confirmar
    # si el APRO no cuadra con esa referencia).
    ref_voucher = (item.ref or "").strip()
    if (tipo == Conciliacion.TIPO_VOUCHER and ref_voucher
            and ref_voucher.lower() != "no encontrada"
            and not refs_coinciden(ref_voucher, comp.ref)):
        return _marcar_revision(
            item, f"El APRO ({ref_voucher}) no coincide con la referencia del "
                  f"comprobante candidato ({comp.ref})")

    # El APRO ya validó contra la referencia real del comprobante Nequi: quedarse
    # con esa referencia completa (empieza en "S", depósito por corresponsal —
    # el APRO solo existe en vouchers físicos, nunca en transferencias "M") en
    # vez del APRO corto, para que el listado muestre la referencia real.
    if (tipo == Conciliacion.TIPO_VOUCHER and ref_voucher
            and comp.ref and comp.ref.strip().upper().startswith("S")):
        item.ref = comp.ref

    # 4. Duplicado (mismo pago ya conciliado aquí o en otra ruta).
    aviso = _detectar_duplicado(item, comp)
    if aviso:
        item.comprobante = comp
        item.aviso = aviso
        item.resultado = Conciliacion.DUPLICADO
        item.save()  # NO se re-confirma el comprobante ni se reasigna ruta.
        return "duplicado"

    # 5. OK: confirmar el comprobante y asignarle la ruta del lote.
    item.comprobante = comp
    comp.estado = Comprobante.CONFIRMADO
    comp.ruta = lote.ruta
    comp.save()
    item.resultado = Conciliacion.OK
    item.save()
    return "ok"


# Alias de compatibilidad (lo usa reprocesar_item en views.py).
emparejar_item = validar_y_emparejar


def _conciliar_item(item: Conciliacion, lote: LoteConciliacion) -> str:
    """Procesa una imagen: extrae datos con la IA y valida+empareja.

    Lanza RuntimeError (GROQ_429/ALL_429) si se agota la cuota.
    """
    datos, _fuente = analizar_comprobante_sync(item.imagen.path)
    if not datos:
        return _marcar_revision(item, "No se pudo leer la imagen")

    item.de = datos.get("de", "")
    item.para = datos.get("para", "") or ""
    item.num = (datos.get("num", "") or "").strip()
    item.tipo = (datos.get("tipo", "") or "").strip().lower()
    item.valor = limpiar_monto(datos.get("valor", "0"))
    item.valor_raw = datos.get("valor", "")
    item.fecha = datos.get("fecha", "")
    item.fecha_dt = parse_fecha(item.fecha)
    hora_raw = datos.get("hora", "")
    t = parse_hora(hora_raw)
    item.hora = t.strftime("%H:%M") if t else hora_raw
    item.ref = (datos.get("ref") or "").strip()

    return validar_y_emparejar(item, lote)


@shared_task
def procesar_conciliacion(lote_id: int):
    try:
        lote = LoteConciliacion.objects.get(pk=lote_id)
    except LoteConciliacion.DoesNotExist:
        logger.error(f"Lote de conciliación {lote_id} no existe")
        return

    lote.estado = LoteConciliacion.PROCESANDO
    lote.save(update_fields=["estado"])

    # Solo los pendientes (sin resultado). Así el lote es reanudable tras pausar.
    items = list(lote.items.filter(resultado__isnull=True).order_by("id"))
    batch_size = getattr(settings, "BATCH_SIZE", 30)

    for chunk in _chunks(items, batch_size):
        for item in chunk:
            # Pausa cooperativa: si el usuario pausó, salimos dejando lo pendiente.
            if LoteConciliacion.objects.filter(pk=lote_id, estado=LoteConciliacion.PAUSADO).exists():
                logger.info(f"Conciliación {lote_id} pausada; deteniendo.")
                return
            try:
                resultado = _conciliar_item(item, lote)
            except RuntimeError as e:
                logger.warning(f"429 en conciliación {lote_id}: {e}. Esperando {BACKOFF_429}s")
                time.sleep(BACKOFF_429)
                try:
                    resultado = _conciliar_item(item, lote)
                except Exception as e2:
                    logger.error(f"Reintento falló: {e2}")
                    item.resultado = Conciliacion.NO_ESTA
                    item.save()
                    resultado = "no_esta"
            except Exception as e:
                logger.error(f"Error conciliando item {item.pk}: {e}")
                item.resultado = Conciliacion.NO_ESTA
                item.save()
                resultado = "no_esta"

            lote.procesadas += 1
            if resultado == "ok":
                lote.ok += 1
            elif resultado == "pendiente":
                lote.pendientes += 1
            elif resultado == "revision":
                lote.revision += 1
            elif resultado == "duplicado":
                lote.duplicados += 1
            else:
                lote.no_esta += 1
            lote.save(update_fields=["procesadas", "ok", "pendientes", "no_esta",
                                     "revision", "duplicados"])
            time.sleep(PAUSA_ENTRE_IMAGENES)

        time.sleep(PAUSA_ENTRE_LOTES)

    # Si quedaron pendientes (p. ej. se pausó antes de llegar a ellos), no completar.
    if lote.items.filter(resultado__isnull=True).exists():
        lote.estado = LoteConciliacion.PAUSADO
        lote.save(update_fields=["estado"])
        return

    lote.estado = LoteConciliacion.COMPLETADO
    lote.terminado_en = timezone.now()
    lote.save(update_fields=["estado", "terminado_en"])

    _notificar_fin(lote)


def _notificar_fin(lote: LoteConciliacion):
    ruta_txt = f"Ruta {lote.ruta.numero}" if lote.ruta else "sin ruta"
    titulo = f"Conciliación #{lote.pk} terminada ({ruta_txt})"
    mensaje = (f"Total: {lote.total} · OK: {lote.ok} · "
               f"Pendientes: {lote.pendientes} · No está: {lote.no_esta} · "
               f"Revisión: {lote.revision} · Duplicados: {lote.duplicados}")
    if lote.creado_por:
        notificar_inapp(lote.creado_por, titulo, mensaje)
        perfil = get_perfil(lote.creado_por)
        if perfil and perfil.telegram_id:
            notificar_telegram(perfil.telegram_id, f"✅ <b>{titulo}</b>\n{mensaje}")
