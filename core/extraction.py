"""Extracción de datos de comprobantes Nequi con IA (Groq + fallback Gemini).

Extraído de bot.py sin cambios de comportamiento. Se exponen tanto la versión
async (usada por el bot de Telegram) como un wrapper síncrono `analizar_comprobante_sync`
pensado para workers de cola (Celery/RQ) que no corren en un event loop.
"""

import asyncio
import base64
import io
import json
import logging
import re
import time

from PIL import Image, ImageOps
from groq import Groq
from google import genai as google_genai

import os

from . import config
from .quota import get_preferred_ia, increment_quota

# Lado mayor al que se reduce la imagen antes de mandarla a la IA.
#
# Medido contra la API real (gemini-2.5-flash): el prompt cuesta 261 tokens
# tanto con 449x1024 como con 702x1600 o 3000x4000 — el tamaño NO cambia el
# costo, Gemini escala por su cuenta. Achicar de más solo quitaba píxeles al
# número de referencia, que es texto chico y es justo lo que se lee mal.
#
# Con 1600 las capturas típicas de WhatsApp (702x1600) pasan intactas, y una
# foto cruda de cámara sigue acotada para no inflar el payload.
IMAGEN_MAX_PX = int(os.getenv("IMAGEN_MAX_PX", "1600"))

logger = logging.getLogger(__name__)

# timeout corto y max_retries=0: ante 429/red mala, fallar al instante y caer a
# Gemini, en vez de que el SDK espere el Retry-After de Groq (~45s) reintentando.
groq_client = Groq(api_key=config.GROQ_KEY, timeout=25.0, max_retries=0) if config.GROQ_KEY else None
if not groq_client:
    logger.error("❌ No se encontró GROQ_API_KEY en el entorno")

# timeout=25s: sin esto el SDK puede colgarse indefinidamente si la red/API
# no responde, dejando el worker "esperando a la IA" para siempre.
gemini_client = google_genai.Client(
    api_key=config.GEMINI_KEY,
    http_options=google_genai.types.HttpOptions(timeout=25_000),
) if config.GEMINI_KEY else None
if gemini_client:
    logger.info("✅ Gemini configurado como fallback")

# Enfriamiento de Groq: tras un 429, las próximas N llamadas van directo a Gemini
# (sin reintentar Groq) para no esperar otro 429. Estado en memoria del proceso.
GROQ_COOLDOWN_TRAS_429 = 20
_groq_cooldown = 0

# Throttle propio de Groq: intervalo mínimo entre llamadas basado en su RPM.
# Usa el 90 % del límite real para dejar margen (30 RPM → ~2.2 s entre llamadas).
# Esto es INDEPENDIENTE de PAUSA_ENTRE_IMAGENES, que controla la velocidad global.
_GROQ_MIN_INTERVAL = 60.0 / (config.GROQ_RPM * 0.9)   # ~2.22 s
_groq_last_call: float = 0.0


_PROMPT = ('JSON solo, sin texto extra:\n'
           '{"de":"remitente o Corresponsal","para":"destinatario o titular",'
           '"num":"numero Nequi destino solo digitos","valor":"$X.XXX",'
           '"fecha":"DD de Mes AAAA","hora":"H:MM am/pm","ref":"numero",'
           '"tipo":"voucher|nequi|otro"}\n'
           '"para": en comprobante Nequi el destinatario ("Para"); en voucher de corresponsal '
           '(Redeban/Wompi/recarga) el "TITULAR".\n'
           '"num": el número Nequi de destino (p. ej. "Número Nequi 300 594 1334" o "RECARGA NEQU" '
           'al número 3005941334); solo dígitos.\n'
           '"ref": en voucher de corresponsal (Redeban/Wompi) es el número de '
           'APROBACIÓN (etiqueta "APRO" o "Aprobación"), normalmente 6 dígitos — '
           'NO uses RRN, RECIBO, C.UNICO, TER ni el número Producto/Nequi, son '
           'otros campos del mismo recibo. En comprobante Nequi es el número de '
           'referencia/autorización (suele empezar por una letra, p. ej. "S...", "M...").\n'
           'Transcribe cada dígito exactamente como aparece, sin redondear ni adivinar; '
           'no agregues ni quites dígitos. Si algún dígito no es legible con certeza, '
           'usa "No encontrada" en vez de adivinar.\n'
           '"tipo": "voucher" si es tirilla de corresponsal fisico (Redeban, Wompi, "RECARGA NEQU"); '
           '"nequi" si es comprobante/transferencia Nequi; "otro" si no se reconoce.\n'
           'Dato ausente: "No encontrada".')


def _resize_image(path: str, max_px: int = None) -> str:
    max_px = max_px or IMAGEN_MAX_PX
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _parse_json_response(text: str):
    if not text:
        raise ValueError(f"Respuesta de IA vacía (text={text!r})")
    clean = text.strip().replace('```json', '').replace('```', '').strip()
    return json.loads(clean)


def _aplicar_reglas(datos: dict) -> dict:
    """Regla de negocio: si la referencia es "No encontrada" o empieza por 'S'
    (depósitos por corresponsal, sin remitente), el contacto es "Corresponsal".

    Replica el comportamiento del bot original (bot.py:396-397).
    """
    if not isinstance(datos, dict):
        return datos
    ref = str(datos.get("ref", "")).strip().upper()
    if ref == "NO ENCONTRADA" or ref.startswith("S"):
        datos["de"] = "Corresponsal"
    return datos


def _resize_image_pil(path: str, max_px: int = None) -> "Image.Image":
    """Igual que _resize_image pero devuelve un PIL Image (para Gemini)."""
    max_px = max_px or IMAGEN_MAX_PX
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        return img.copy()


async def _analizar_con_gemini(path: str):
    def _call():
        # Imagen redimensionada a 1024 px (igual que Groq): balance entre tokens
        # y legibilidad del número de referencia (texto pequeño en el recibo).
        # 768px dejaba dígitos ambiguos y causaba referencias con un dígito de
        # más o de menos; 1024 da más margen sin disparar demasiado el costo.
        pil_img = _resize_image_pil(path)
        response = gemini_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[_PROMPT, pil_img],
            config={
                # Limitar output igual que Groq (max_tokens=200). El JSON de
                # respuesta ocupa ~150 tokens; 400 da margen extra por si
                # el thinking_budget=0 no elimina del todo tokens internos.
                "max_output_tokens": 400,
                # Forzar JSON puro: evita que Gemini envuelva con ```json```
                # y ahorra tokens de markdown en cada respuesta.
                "response_mime_type": "application/json",
                # gemini-2.5-flash piensa por defecto y esos tokens de
                # razonamiento consumen el mismo presupuesto de
                # max_output_tokens, dejando a veces la respuesta final
                # vacía (response.text == "" o None). No se necesita
                # razonamiento para esta extracción simple.
                "thinking_config": {"thinking_budget": 0},
            },
        )
        return _aplicar_reglas(_parse_json_response(response.text))
    logger.info("Usando Gemini como fallback")
    return await asyncio.to_thread(_call)


async def _analizar_con_groq(path):
    global _groq_last_call
    # Throttle Groq-specific: esperar el tiempo necesario para no superar su RPM.
    ahora = time.monotonic()
    espera = _GROQ_MIN_INTERVAL - (ahora - _groq_last_call)
    if espera > 0:
        logger.debug(f"Groq throttle: esperando {espera:.2f}s")
        await asyncio.sleep(espera)
    _groq_last_call = time.monotonic()

    image_data = await asyncio.to_thread(_resize_image, path)
    msgs = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
        {"type": "text", "text": _PROMPT}
    ]}]
    response = await asyncio.to_thread(
        groq_client.chat.completions.create,
        model=config.GROQ_MODEL, messages=msgs, max_tokens=200, temperature=0
    )
    tokens_usados = getattr(response.usage, "total_tokens", 0) or 0
    increment_quota(tokens_usados)
    return _aplicar_reglas(_parse_json_response(response.choices[0].message.content))


async def analizar_comprobante(path):
    """Analiza un comprobante y devuelve (dict_datos, nombre_ia) o (None, None).

    Puede lanzar RuntimeError con mensajes "GROQ_429:<wait>" o "ALL_429:<wait>"
    cuando se agota la cuota, para que el llamador aplique back-off.
    """
    global _groq_cooldown
    try:
        preferida = get_preferred_ia()
        en_enfriamiento = _groq_cooldown > 0 and gemini_client is not None

        # Gemini directo: por preferencia del usuario o porque Groq está en enfriamiento.
        if (preferida == "gemini" or en_enfriamiento) and gemini_client:
            if en_enfriamiento:
                _groq_cooldown -= 1
            try:
                return await _analizar_con_gemini(path), "Gemini"
            except Exception as gem_err:
                logger.warning(f"Gemini falló, intentando Groq: {gem_err}")
                if not groq_client:
                    return None, None
                try:
                    return await _analizar_con_groq(path), "Groq"
                except Exception as e:
                    logger.error(f"Groq también falló: {e}")
                    return None, None

        # Preferida = groq (comportamiento por defecto)
        last_err = None
        try:
            return await _analizar_con_groq(path), "Groq"
        except Exception as e:
            last_err = e
            # 429 de Groq → saltar Groq las próximas N llamadas (ir directo a Gemini).
            if "429" in str(e):
                _groq_cooldown = GROQ_COOLDOWN_TRAS_429
                logger.info(f"Groq 429: usando Gemini directo las próximas "
                            f"{GROQ_COOLDOWN_TRAS_429} imágenes.")

        # Groq falló con 429 — intentar Gemini como fallback
        if last_err and "429" in str(last_err) and gemini_client:
            try:
                return await _analizar_con_gemini(path), "Gemini"
            except Exception as gem_err:
                gem_str = str(gem_err)
                logger.warning(f"Gemini también falló: {gem_err}")
                if "429" in gem_str:
                    m = re.search(r'retry in ([0-9hms. ]+)', gem_str)
                    gem_wait = m.group(1).strip() if m else None
                    groq_m = re.search(r'try again in ([0-9hms. ]+)', str(last_err))
                    wait = gem_wait or (groq_m.group(1).strip() if groq_m else "unos minutos")
                    raise RuntimeError(f"ALL_429:{wait}")
        err = str(last_err) if last_err else ""
        if "429" in err:
            m = re.search(r'try again in ([0-9hms. ]+)', err)
            wait = m.group(1).strip() if m else "unos minutos"
            raise RuntimeError(f"GROQ_429:{wait}")
        # Error de conexión u otro (no 429): intentar Gemini como respaldo.
        if last_err and gemini_client:
            try:
                logger.warning(f"Groq falló ({last_err}); usando Gemini")
                return await _analizar_con_gemini(path), "Gemini"
            except Exception as gem_err:
                logger.warning(f"Gemini también falló: {gem_err}")
        if last_err:
            logger.error(f"Error en análisis: {last_err}")
        return None, None
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        return None, None


def analizar_comprobante_sync(path):
    """Wrapper síncrono de `analizar_comprobante` para workers de cola.

    Crea un event loop propio. Propaga RuntimeError de cuota (GROQ_429/ALL_429).
    """
    return asyncio.run(analizar_comprobante(path))
