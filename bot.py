import os
import re
import logging
import json
import csv
import html
import asyncio
import base64
import io
from PIL import Image
from groq import Groq
from google import genai as google_genai
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PREFERRED_IA_FILE = "preferred_ia.json"

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
if not groq_client:
    logger.error("❌ No se encontró GROQ_API_KEY en el archivo .env")

def get_preferred_ia() -> str:
    try:
        if os.path.exists(PREFERRED_IA_FILE):
            with open(PREFERRED_IA_FILE, "r") as f:
                return json.load(f).get("ia", "groq")
    except Exception:
        pass
    return "groq"

def set_preferred_ia(ia: str):
    with open(PREFERRED_IA_FILE, "w") as f:
        json.dump({"ia": ia}, f)

GEMINI_MODEL = "gemini-2.5-flash"
gemini_client = google_genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
if gemini_client:
    logger.info("✅ Gemini configurado como fallback")


# Configuración de carpetas y archivos
DATA_FILE = "listas_nequi.json"
LOG_DIR = "logs_comprobantes"
DEBUG_FILE = "debug_log.json"
QUOTA_FILE = "quota_tracker.json"
PAGE_SIZE = 5
# Límites oficiales Groq free tier para llama-4-scout-17b-16e-instruct
GROQ_RPD = 1000   # requests per day
GROQ_RPM = 30     # requests per minute
GROQ_TPD = 500000 # tokens per day

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ---------------------------------------------------------------------------
# Cuota diaria Groq
# ---------------------------------------------------------------------------

def _load_all_quota() -> dict:
    try:
        if os.path.exists(QUOTA_FILE) and os.path.getsize(QUOTA_FILE) > 0:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_all_quota(all_data: dict):
    with open(QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f)

def load_quota() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _load_all_quota().get("groq", {})
    if entry.get("date") == today:
        return {"count": entry.get("count", 0), "tokens": entry.get("tokens", 0)}
    return {"count": 0, "tokens": 0}

def increment_quota(tokens: int = 0):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_data = _load_all_quota()
    entry = all_data.get("groq", {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0, "tokens": 0}
    entry["count"] += 1
    entry["tokens"] += tokens
    all_data["groq"] = entry
    _save_all_quota(all_data)

# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def log_debug_info(user_id, response_data, image_name):
    try:
        if os.path.exists(DEBUG_FILE) and os.path.getsize(DEBUG_FILE) > 0:
            with open(DEBUG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
    except (json.JSONDecodeError, FileNotFoundError):
        logs = []
        
    logs.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": str(user_id),
        "image": image_name,
        "response": response_data
    })
    
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_data():
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

# ---------------------------------------------------------------------------
# Procesamiento con Gemini
# ---------------------------------------------------------------------------

def _resize_image(path: str, max_px: int = 768) -> str:
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

_PROMPT = ('JSON solo, sin texto extra:\n'
           '{"de":"remitente o Corresponsal","valor":"$X.XXX","fecha":"DD de Mes AAAA",'
           '"hora":"H:MM am/pm","ref":"numero"}\n'
           'Dato ausente: "No encontrada".')

def _parse_json_response(text: str):
    clean = text.strip().replace('```json', '').replace('```', '').strip()
    return json.loads(clean)

async def _analizar_con_gemini(path: str):
    def _call():
        with Image.open(path) as img:
            img = img.convert("RGB")
            pil_img = img.copy()
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL, contents=[_PROMPT, pil_img]
        )
        return _parse_json_response(response.text)
    logger.info("Usando Gemini como fallback")
    return await asyncio.to_thread(_call)

async def _analizar_con_groq(path):
    image_data = await asyncio.to_thread(_resize_image, path)
    msgs = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
        {"type": "text", "text": _PROMPT}
    ]}]
    try:
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=GROQ_MODEL, messages=msgs, max_tokens=200, temperature=0
        )
        tokens_usados = getattr(response.usage, "total_tokens", 0) or 0
        increment_quota(tokens_usados)
        return _parse_json_response(response.choices[0].message.content)
    except Exception as e:
        raise e


async def analizar_comprobante(path):
    try:
        preferida = get_preferred_ia()

        if preferida == "gemini" and gemini_client:
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
        if last_err:
            logger.error(f"Error en análisis: {last_err}")
        return None, None
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        return None, None

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def limpiar_monto(valor_str):
    try:
        limpio = valor_str.replace('$', '').strip()
        limpio = limpio.replace('.', '').replace(',', '.')
        return float(limpio)
    except:
        return 0.0

def buscar_duplicado(user_list, ref):
    """Retorna (idx_1based, item) si la referencia ya existe, sino None."""
    if not ref or ref == "No encontrada":
        return None
    for idx, item in enumerate(user_list, 1):
        if item.get('ref', '') == ref:
            return (idx, item)
    return None

def fmt_total(user_list):
    total = sum(limpiar_monto(it['valor']) for it in user_list)
    return f"${total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------------------------------------------------------------------
# Construcción de vistas
# ---------------------------------------------------------------------------

def construir_pagina_lista(user_list, page):
    """Devuelve (texto, InlineKeyboardMarkup) para la página pedida."""
    n = len(user_list)
    total_pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, n)

    texto = (f"📜 <b>Lista Nequi</b> — {n} factura{'s' if n != 1 else ''} | "
             f"<b>{html.escape(fmt_total(user_list))}</b>\n"
             f"<i>Página {page + 1} de {total_pages}</i>\n\n")

    for i in range(start, end):
        it = user_list[i]
        texto += (f"{i + 1}. 💰 <b>{html.escape(it['valor'])}</b> — 👤 {html.escape(it.get('de', 'N/A'))}\n"
                  f"   🔢 {html.escape(it.get('ref', 'N/A'))} | 📅 {html.escape(it.get('fecha', 'N/A'))}\n\n")

    # Navegación de páginas
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Anterior", callback_data=f"lista_p_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if end < n:
        nav.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"lista_p_{page + 1}"))

    botones = []
    if nav:
        botones.append(nav)
    botones.append([
        InlineKeyboardButton("📥 TXT", callback_data="download_txt"),
        InlineKeyboardButton("📊 EXCEL", callback_data="download_xlsx"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_menu_{page}"),
    ])

    return texto, InlineKeyboardMarkup(botones)


def construir_resumen_guardado(lista, num):
    """Texto de confirmación con lista parcial tras guardar."""
    MAX_VISIBLE = 8
    resumen = f"💾 <b>Guardada como factura #{num}</b>\n\n📋 <b>Facturas registradas ({num}):</b>\n"

    if num <= MAX_VISIBLE:
        visible = list(enumerate(lista, 1))
        ocultas = 0
    else:
        visible = list(enumerate(lista, 1))[-MAX_VISIBLE:]
        ocultas = num - MAX_VISIBLE

    if ocultas:
        resumen += f"  <i>... {ocultas} facturas anteriores ...</i>\n"
    for idx, it in visible:
        marca = " ◀" if idx == num else ""
        resumen += f"  {idx}. {html.escape(it.get('de', '?'))} — <b>{html.escape(it['valor'])}</b>{marca}\n"

    resumen += f"\n📊 <b>Total:</b> {html.escape(fmt_total(lista))}"
    return resumen

# ---------------------------------------------------------------------------
# Teclado principal
# ---------------------------------------------------------------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [['📜 Ver Lista', '🆕 Nueva Lista'], ['📊 API Status', '🤖 IA', '❓ Ayuda']],
    resize_keyboard=True
)

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy tu gestor Nequi.\nEnvíame capturas y gestionaré tus cobros.",
        reply_markup=MAIN_KEYBOARD
    )

def _build_api_status() -> tuple:
    def barra(used, total):
        pct = min(used / total * 100, 100) if total > 0 else 0
        filled = int(pct / 10)
        return "█" * filled + "░" * (10 - filled), pct

    q = load_quota()
    count, tokens = q["count"], q["tokens"]
    b, pct = barra(tokens, GROQ_TPD)
    groq_estado = "🟢 Activo" if groq_client else "⚫ No configurado"
    gem_estado  = "🟢 Configurado" if gemini_client else "⚫ No configurado"

    texto = (
        f"🤖 <b>Estado APIs</b>\n\n"
        f"⚡ <b>Groq</b> ({GROQ_MODEL[:30]}): {groq_estado}\n"
        f"Solicitudes: {barra(count, GROQ_RPD)[0]} <code>{count}/{GROQ_RPD}</code>\n"
        f"Tokens: {b} <code>{tokens:,}/{GROQ_TPD:,}</code> ({pct:.1f}%)\n"
        f"<i>Reset 7pm Colombia</i>\n\n"
        f"🔁 <b>Fallback Gemini</b> ({GEMINI_MODEL}): {gem_estado}"
    )
    return texto, None

async def ver_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto, markup = _build_api_status()
    await update.message.reply_text(texto, parse_mode='HTML',
                                    reply_markup=markup or MAIN_KEYBOARD)

def _btns_429():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Reintentar", callback_data="groq_retry")]])

async def _mostrar_resultado(datos, user_id, final_path, p_id, context, send_fn, ia="Groq"):
    """Muestra los datos detectados y los botones de acción."""
    res_de   = datos.get("de",    "No encontrada")
    res_valor = datos.get("valor", "$0")
    res_fecha = datos.get("fecha", "No encontrada")
    res_hora  = datos.get("hora",  "No encontrada")
    res_ref   = datos.get("ref",   "No encontrada")

    if res_ref == "No encontrada" or res_ref.strip().upper().startswith('S'):
        res_de = "Corresponsal"

    user_list = load_data().get(user_id, [])
    dup = buscar_duplicado(user_list, res_ref)

    context.user_data[p_id] = {
        "de": res_de, "valor": res_valor,
        "fecha": res_fecha, "hora": res_hora, "ref": res_ref,
        "img_log": os.path.basename(final_path)
    }

    ia_badge = "⚡ <i>Groq</i>" if ia == "Groq" else "✨ <i>Gemini</i>"
    texto = (f"{ia_badge} — <b>Datos Detectados:</b>\n\n"
             f"👤 <b>Contacto:</b> <code>{html.escape(res_de)}</code>\n"
             f"💰 <b>Valor:</b> <code>{html.escape(res_valor)}</code>\n"
             f"📅 <b>Fecha:</b> <code>{html.escape(res_fecha)}</code>\n"
             f"🕒 <b>Hora:</b> <code>{html.escape(res_hora)}</code>\n"
             f"🔢 <b>Ref:</b> <code>{html.escape(res_ref)}</code>")

    if dup:
        dup_idx, dup_item = dup
        texto += (f"\n\n⚠️ <b>Posible duplicado:</b> esta referencia ya está "
                  f"en la factura #{dup_idx} de {html.escape(dup_item.get('de', '?'))} "
                  f"({html.escape(dup_item['valor'])})")
        btns = [
            [InlineKeyboardButton("⚠️ Guardar igual", callback_data=f"force_save_{p_id}"),
             InlineKeyboardButton("✏️ Editar", callback_data=f"edit_menu_{p_id}")],
            [InlineKeyboardButton("❌ Descartar", callback_data=f"cancel_{p_id}")]
        ]
    else:
        btns = [
            [InlineKeyboardButton("✅ Guardar", callback_data=f"save_{p_id}"),
             InlineKeyboardButton("✏️ Editar", callback_data=f"edit_menu_{p_id}")],
            [InlineKeyboardButton("❌ Descartar", callback_data=f"cancel_{p_id}")]
        ]
    await send_fn(texto, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))

async def ver_lista(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user_id = str(update.effective_user.id)
    user_list = load_data().get(user_id, [])

    if not user_list:
        await update.message.reply_text("La lista está vacía. 📭", reply_markup=MAIN_KEYBOARD)
        return

    texto, markup = construir_pagina_lista(user_list, page)
    await update.message.reply_text(texto, parse_mode='HTML', reply_markup=markup)

async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Si hay un 429 activo, rechazar nuevas imágenes hasta que el usuario use los botones
    if context.user_data.get("groq_paused"):
        await update.message.reply_text(
            "⏳ <b>Bot pausado</b> — hay un límite activo de Groq.\n"
            "Usa los botones del último mensaje para reintentar o cambiar de key.",
            parse_mode='HTML', reply_markup=MAIN_KEYBOARD
        )
        return

    status_msg = await update.message.reply_text("🔍 Analizando con IA...")
    file_path = f"temp_{update.message.message_id}.jpg"
    user_id = str(update.effective_user.id)

    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)

        # Mover imagen a LOG_DIR antes de analizar para poder reutilizarla en retry
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_image_name = f"{timestamp}_{user_id}_pending.jpg"
        final_path = os.path.join(LOG_DIR, final_image_name)
        os.rename(file_path, final_path)
        file_path = None

        p_id = str(update.message.message_id)

        try:
            datos, ia_usada = await analizar_comprobante(final_path)
        except RuntimeError as e:
            await status_msg.delete()
            msg = str(e)
            if msg.startswith("GROQ_429:") or msg.startswith("ALL_429:"):
                wait = msg.split(":", 1)[1]
                all_apis = msg.startswith("ALL_429:")
                context.user_data["groq_paused"] = True
                context.user_data["groq_pending"] = {"img_path": final_path, "p_id": p_id}
                detalle = "Groq y Gemini tienen límite activo." if all_apis else "Límite de Groq alcanzado."
                await update.message.reply_text(
                    f"⏳ <b>{detalle}</b>\n\n"
                    f"Intenta de nuevo en <b>{wait}</b>.\n"
                    f"<i>El bot está pausado hasta que uses uno de los botones.</i>",
                    parse_mode='HTML', reply_markup=_btns_429()
                )
            else:
                await update.message.reply_text("❌ Error al analizar la imagen. Intenta de nuevo.",
                                                reply_markup=MAIN_KEYBOARD)
            return
        except Exception:
            await status_msg.delete()
            await update.message.reply_text("❌ Error al analizar la imagen. Intenta de nuevo.",
                                            reply_markup=MAIN_KEYBOARD)
            return

        if not datos:
            await status_msg.delete()
            await update.message.reply_text(
                "❌ No pude entender la imagen. Revisa los logs del bot para ver el error.",
                reply_markup=MAIN_KEYBOARD)
            return

        # Renombrar imagen con la ref real ahora que la tenemos
        ref_clean = datos.get("ref", "sin_ref").replace(" ", "_")
        real_name = f"{timestamp}_{user_id}_{ref_clean}.jpg"
        real_path = os.path.join(LOG_DIR, real_name)
        os.rename(final_path, real_path)
        log_debug_info(user_id, datos, real_name)

        await status_msg.delete()
        await _mostrar_resultado(datos, user_id, real_path, p_id, context,
                                 update.message.reply_text, ia=ia_usada or "Groq")

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Error al procesar la imagen.", reply_markup=MAIN_KEYBOARD)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    data = load_data()
    user_list = data.get(user_id, [])
    raw = query.data

    # Botón decorativo sin acción
    if raw == "noop":
        return

    # --- RETRY TRAS 429 ---
    if raw == "groq_retry":
        pending = context.user_data.get("groq_pending")
        if not pending:
            await query.answer("❌ No hay imagen pendiente")
            return
        await query.answer("🔄 Reintentando...")

        img_path = pending["img_path"]
        p_id = pending["p_id"]

        if not os.path.exists(img_path):
            await query.edit_message_text("❌ La imagen ya no está disponible. Envíala de nuevo.")
            context.user_data.pop("groq_paused", None)
            context.user_data.pop("groq_pending", None)
            return

        await query.edit_message_text("🔍 Analizando con IA...")
        try:
            datos, ia_usada = await analizar_comprobante(img_path)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("GROQ_429:") or msg.startswith("ALL_429:"):
                wait = msg.split(":", 1)[1]
                all_apis = msg.startswith("ALL_429:")
                detalle = "Groq y Gemini tienen límite activo." if all_apis else "Límite de Groq alcanzado."
                await query.edit_message_text(
                    f"⏳ <b>{detalle}</b>\n\n"
                    f"Intenta de nuevo en <b>{wait}</b>.",
                    parse_mode='HTML', reply_markup=_btns_429()
                )
            else:
                await query.edit_message_text("❌ Error al analizar. Intenta de nuevo.")
            return
        except Exception:
            await query.edit_message_text("❌ Error al analizar. Intenta de nuevo.")
            return

        context.user_data.pop("groq_paused", None)
        context.user_data.pop("groq_pending", None)

        if not datos:
            await query.edit_message_text("❌ No pude entender la imagen.")
            return

        await _mostrar_resultado(datos, user_id, img_path, p_id, context,
                                 query.edit_message_text, ia=ia_usada or "Groq")
        return

    # --- CAMBIAR KEY ACTIVA ---
    if raw in ("ia_set_groq", "ia_set_gemini"):
        nueva = "groq" if raw == "ia_set_groq" else "gemini"
        set_preferred_ia(nueva)
        nombre = "⚡ Groq" if nueva == "groq" else "✨ Gemini"
        await query.answer(f"✅ IA cambiada a {nombre}")
        groq_mark  = "✅ " if nueva == "groq"   else ""
        gemini_mark = "✅ " if nueva == "gemini" else ""
        btns = [[
            InlineKeyboardButton(f"{groq_mark}⚡ Groq",    callback_data="ia_set_groq"),
            InlineKeyboardButton(f"{gemini_mark}✨ Gemini", callback_data="ia_set_gemini"),
        ]]
        await query.edit_message_text(
            f"🤖 <b>IA activa:</b> {nombre}\n\nElige cuál usar para analizar los comprobantes:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns)
        )
        return

    # --- DESCARGAS ---
    if raw == "download_txt":
        if not user_list:
            return
        file_name = f"lista_{user_id}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("REPORTE NEQUI\n" + "=" * 20 + "\n")
            for idx, item in enumerate(user_list, 1):
                f.write(f"{idx}. {item['de']} | {item['valor']} | {item['fecha']} | {item.get('hora', '')} | {item['ref']}\n")
        await context.bot.send_document(chat_id=user_id, document=open(file_name, 'rb'), filename="Lista_Nequi.txt")
        os.remove(file_name)
        return

    if raw == "download_xlsx":
        if not user_list:
            return
        file_name = f"lista_{user_id}.xlsx"
        
        # Crear DataFrame
        df = pd.DataFrame(user_list)
        
        # Convertir horas en formato colombiano "HH:MM p. m." / "HH:MM p.m." a tiempo
        import re as _re
        def _parse_hora(h):
            if not isinstance(h, str):
                return None
            clean = _re.sub(r'p\.?\s*m\.?', 'PM', h, flags=_re.IGNORECASE)
            clean = _re.sub(r'a\.?\s*m\.?', 'AM', clean, flags=_re.IGNORECASE).strip()
            for fmt in ('%I:%M %p', '%H:%M'):
                try:
                    return datetime.strptime(clean, fmt).time()
                except ValueError:
                    continue
            return None
        df['Hora'] = df['hora'].apply(_parse_hora)
        
        # Reordenar y renombrar columnas
        df_export = df[['de', 'valor', 'fecha', 'Hora', 'ref']].rename(columns={
            'de': 'Contacto',
            'valor': 'Monto',
            'fecha': 'Fecha',
            'ref': 'Referencia'
        })

        # Guardar a Excel
        df_export.to_excel(file_name, index=False, engine='openpyxl')
        
        await context.bot.send_document(chat_id=user_id, document=open(file_name, 'rb'), filename="Lista_Nequi.xlsx")
        os.remove(file_name)
        return

    # --- PAGINACIÓN DE LISTA ---
    if raw.startswith("lista_p_"):
        page = int(raw.split("_")[2])
        if not user_list:
            await query.edit_message_text("La lista está vacía. 📭")
            return
        texto, markup = construir_pagina_lista(user_list, page)
        await query.edit_message_text(texto, parse_mode='HTML', reply_markup=markup)
        return

    # --- ELIMINAR: menú de selección ---
    if raw.startswith("del_menu_"):
        page = int(raw.split("_")[2])
        if not user_list:
            await query.edit_message_text("La lista está vacía. 📭")
            return

        n = len(user_list)
        total_pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, n)

        texto = f"🗑️ <b>Eliminar factura</b> — elige el número:\n<i>Página {page + 1} de {total_pages}</i>\n\n"
        for i in range(start, end):
            it = user_list[i]
            texto += f"{i + 1}. {html.escape(it.get('de', '?'))} — {html.escape(it['valor'])}\n"

        # Botones numéricos para eliminar (hasta 4 por fila)
        btns = []
        row = []
        for i in range(start, end):
            row.append(InlineKeyboardButton(f"#{i + 1}", callback_data=f"del_ask_{i}"))
            if len(row) == 4:
                btns.append(row)
                row = []
        if row:
            btns.append(row)

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"del_menu_{page - 1}"))
        if end < n:
            nav.append(InlineKeyboardButton("▶", callback_data=f"del_menu_{page + 1}"))
        if nav:
            btns.append(nav)

        btns.append([InlineKeyboardButton("🔙 Volver", callback_data=f"lista_p_{page}")])
        await query.edit_message_text(texto, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
        return

    # --- ELIMINAR: pedir confirmación ---
    if raw.startswith("del_ask_"):
        idx = int(raw.split("_")[2])  # 0-based
        if idx >= len(user_list):
            await query.edit_message_text("⚠️ Factura no encontrada.")
            return
        it = user_list[idx]
        page = idx // PAGE_SIZE
        texto = (f"⚠️ ¿Eliminar la factura #{idx + 1}?\n\n"
                 f"👤 {html.escape(it.get('de', '?'))}\n"
                 f"💰 {html.escape(it['valor'])}\n"
                 f"🔢 {html.escape(it.get('ref', 'N/A'))}")
        btns = [[
            InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"del_exec_{idx}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"lista_p_{page}")
        ]]
        await query.edit_message_text(texto, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
        return

    # --- ELIMINAR: ejecutar ---
    if raw.startswith("del_exec_"):
        idx = int(raw.split("_")[2])  # 0-based
        if idx < len(user_list):
            eliminada = user_list.pop(idx)
            data[user_id] = user_list
            save_data(data)

            if not user_list:
                await query.edit_message_text(
                    f"🗑️ Factura #{idx + 1} de {html.escape(eliminada.get('de', '?'))} eliminada.\n\nLa lista quedó vacía. 📭"
                )
                return

            # Volver a la página donde estaba (ajustada si quedó vacía)
            page = min(idx // PAGE_SIZE, (len(user_list) - 1) // PAGE_SIZE)
            texto, markup = construir_pagina_lista(user_list, page)
            await query.edit_message_text(
                f"🗑️ Factura #{idx + 1} eliminada.\n\n" + texto,
                parse_mode='HTML', reply_markup=markup
            )
        return

    # --- GUARDAR (normal) ---
    if raw.startswith("save_"):
        p_id = raw.split("_", 1)[1]
        item = context.user_data.get(p_id)
        if item:
            if user_id not in data:
                data[user_id] = []
            data[user_id].append(item)
            save_data(data)
            num = len(data[user_id])
            await query.edit_message_text(construir_resumen_guardado(data[user_id], num), parse_mode='HTML')
            del context.user_data[p_id]
        return

    # --- GUARDAR (forzado, ignorando duplicado) ---
    if raw.startswith("force_save_"):
        p_id = raw.split("_", 2)[2]
        item = context.user_data.get(p_id)
        if item:
            if user_id not in data:
                data[user_id] = []
            data[user_id].append(item)
            save_data(data)
            num = len(data[user_id])
            await query.edit_message_text(construir_resumen_guardado(data[user_id], num), parse_mode='HTML')
            del context.user_data[p_id]
        return

    # --- DESCARTAR ---
    if raw.startswith("cancel_"):
        p_id = raw.split("_", 1)[1]
        if p_id in context.user_data:
            del context.user_data[p_id]
        await query.edit_message_text("🗑️ Descartado.")
        return

    # --- EDITAR: menú de campos ---
    if raw.startswith("edit_menu_"):
        p_id = raw.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("👤 Contacto", callback_data=f"edit_field_{p_id}_de")],
            [InlineKeyboardButton("💰 Valor", callback_data=f"edit_field_{p_id}_valor")],
            [InlineKeyboardButton("📅 Fecha", callback_data=f"edit_field_{p_id}_fecha")],
            [InlineKeyboardButton("🕒 Hora", callback_data=f"edit_field_{p_id}_hora")],
            [InlineKeyboardButton("🔢 Ref", callback_data=f"edit_field_{p_id}_ref")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"back_{p_id}")]
        ]
        await query.edit_message_text("¿Qué campo deseas editar?", reply_markup=InlineKeyboardMarkup(btns))
        return

    # --- EDITAR: selección de campo ---
    if raw.startswith("edit_field_"):
        after = raw[len("edit_field_"):]       # "{p_id}_{field}"
        field = after.rsplit("_", 1)[1]
        p_id = after.rsplit("_", 1)[0]
        context.user_data['editing'] = {"p_id": p_id, "field": field}
        await query.edit_message_text(
            f"✍️ Escribe el nuevo valor para <b>{field.capitalize()}</b>:", parse_mode='HTML'
        )
        return

    # --- VOLVER a datos detectados ---
    if raw.startswith("back_"):
        p_id = raw.split("_", 1)[1]
        item = context.user_data.get(p_id)
        if item:
            response = (f"✅ <b>Datos Detectados:</b>\n\n"
                        f"👤 <b>Contacto:</b> <code>{html.escape(item['de'])}</code>\n"
                        f"💰 <b>Valor:</b> <code>{html.escape(item['valor'])}</code>\n"
                        f"📅 <b>Fecha:</b> <code>{html.escape(item['fecha'])}</code>\n"
                        f"🕒 <b>Hora:</b> <code>{html.escape(item['hora'])}</code>\n"
                        f"🔢 <b>Ref:</b> <code>{html.escape(item['ref'])}</code>")
            btns = [
                [InlineKeyboardButton("✅ Guardar", callback_data=f"save_{p_id}"),
                 InlineKeyboardButton("✏️ Editar", callback_data=f"edit_menu_{p_id}")],
                [InlineKeyboardButton("❌ Descartar", callback_data=f"cancel_{p_id}")]
            ]
            await query.edit_message_text(response, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
        return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text

    # --- MODO EDICIÓN ---
    if 'editing' in context.user_data:
        edit_info = context.user_data['editing']
        p_id = edit_info['p_id']
        field = edit_info['field']

        if p_id in context.user_data:
            context.user_data[p_id][field] = t
            item = context.user_data[p_id]
            response = (f"✏️ <b>Dato Actualizado:</b>\n\n"
                        f"👤 <b>Contacto:</b> <code>{html.escape(item['de'])}</code>\n"
                        f"💰 <b>Valor:</b> <code>{html.escape(item['valor'])}</code>\n"
                        f"📅 <b>Fecha:</b> <code>{html.escape(item['fecha'])}</code>\n"
                        f"🕒 <b>Hora:</b> <code>{html.escape(item['hora'])}</code>\n"
                        f"🔢 <b>Ref:</b> <code>{html.escape(item['ref'])}</code>")
            btns = [
                [InlineKeyboardButton("✅ Guardar", callback_data=f"save_{p_id}"),
                 InlineKeyboardButton("✏️ Editar", callback_data=f"edit_menu_{p_id}")],
                [InlineKeyboardButton("❌ Descartar", callback_data=f"cancel_{p_id}")]
            ]
            await update.message.reply_text(response, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))

        del context.user_data['editing']
        return

    if t == '📜 Ver Lista':
        await ver_lista(update, context)
    elif t == '🆕 Nueva Lista':
        u_id = str(update.effective_user.id)
        data = load_data()
        data[u_id] = []
        save_data(data)
        await update.message.reply_text("🧹 Lista borrada.")
    elif t == '📊 API Status':
        await ver_api_status(update, context)
    elif t == '🤖 IA':
        preferida = get_preferred_ia()
        groq_mark  = "✅ " if preferida == "groq"   else ""
        gemini_mark = "✅ " if preferida == "gemini" else ""
        btns = [[
            InlineKeyboardButton(f"{groq_mark}⚡ Groq",    callback_data="ia_set_groq"),
            InlineKeyboardButton(f"{gemini_mark}✨ Gemini", callback_data="ia_set_gemini"),
        ]]
        await update.message.reply_text(
            f"🤖 <b>IA activa:</b> {'⚡ Groq' if preferida == 'groq' else '✨ Gemini'}\n\n"
            "Elige cuál usar para analizar los comprobantes:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns)
        )
    elif t == '❓ Ayuda':
        await update.message.reply_text("Envíame fotos de Nequi.")


if __name__ == '__main__':
    if not TOKEN:
        print("❌ Token no configurado")
    else:
        # Construir la aplicación con tiempos de espera extendidos (30s) para evitar 'Timed out'
        app = ApplicationBuilder().token(TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("status", ver_api_status))
        app.add_handler(MessageHandler(filters.PHOTO, process_photo))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.run_polling()
