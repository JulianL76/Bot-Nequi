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
GROQ_KEY_BACKUP = os.getenv("GROQ_API_KEY_BACKUP")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
ACTIVE_KEY_FILE = "active_key.json"

_clients = {}
if GROQ_KEY:
    _clients["primary"] = Groq(api_key=GROQ_KEY)
else:
    logger.error("❌ No se encontró GROQ_API_KEY en el archivo .env")
if GROQ_KEY_BACKUP:
    _clients["backup"] = Groq(api_key=GROQ_KEY_BACKUP)

def get_active_key_name() -> str:
    try:
        if os.path.exists(ACTIVE_KEY_FILE):
            with open(ACTIVE_KEY_FILE, "r") as f:
                return json.load(f).get("active", "primary")
    except Exception:
        pass
    return "primary"

def set_active_key_name(name: str):
    with open(ACTIVE_KEY_FILE, "w") as f:
        json.dump({"active": name}, f)

def get_groq_client():
    return _clients.get(get_active_key_name()) or next(iter(_clients.values()), None)

def _key_tag(name: str) -> str:
    key = GROQ_KEY if name == "primary" else GROQ_KEY_BACKUP
    return (key or "")[-6:]

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

def load_quota(name: str = None) -> dict:
    if name is None:
        name = get_active_key_name()
    tag = _key_tag(name)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if os.path.exists(QUOTA_FILE) and os.path.getsize(QUOTA_FILE) > 0:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
            entry = all_data.get(tag, {})
            if entry.get("date") == today:
                return {"count": entry.get("count", 0), "tokens": entry.get("tokens", 0)}
    except Exception:
        pass
    return {"count": 0, "tokens": 0}

def increment_quota(tokens: int = 0) -> dict:
    name = get_active_key_name()
    tag = _key_tag(name)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        all_data = {}
        if os.path.exists(QUOTA_FILE) and os.path.getsize(QUOTA_FILE) > 0:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
    except Exception:
        all_data = {}
    entry = all_data.get(tag, {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0, "tokens": 0}
    entry["count"] += 1
    entry["tokens"] += tokens
    all_data[tag] = entry
    with open(QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f)
    return {"count": entry["count"], "tokens": entry["tokens"]}

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

async def analizar_comprobante(path):
    prompt = ('JSON solo, sin texto extra:\n'
              '{"de":"remitente o Corresponsal","valor":"$X.XXX","fecha":"DD de Mes AAAA",'
              '"hora":"H:MM am/pm","ref":"numero"}\n'
              'Dato ausente: "No encontrada".')
    try:
        image_data = await asyncio.to_thread(_resize_image, path)
        last_err = None
        for attempt in range(2):
            try:
                response = await asyncio.to_thread(
                    get_groq_client().chat.completions.create,
                    model=GROQ_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                            {"type": "text", "text": prompt}
                        ]
                    }],
                    max_tokens=200,
                    temperature=0
                )
                tokens_usados = getattr(response.usage, "total_tokens", 0) or 0
                increment_quota(tokens_usados)
                text = response.choices[0].message.content.strip()
                clean_json = text.replace('```json', '').replace('```', '').strip()
                return json.loads(clean_json)
            except Exception as e:
                if "429" in str(e) and attempt == 0:
                    active = get_active_key_name()
                    other = "backup" if active == "primary" else "primary"
                    if other in _clients:
                        set_active_key_name(other)
                        logger.warning(f"429 en key {active} — cambiando a {other}")
                        last_err = e
                        continue
                last_err = e
                break
        err = str(last_err) if last_err else ""
        if "429" in err:
            m = re.search(r'try again in ([0-9hms. ]+)', err)
            wait = m.group(1).strip() if m else "unos minutos"
            raise RuntimeError(f"GROQ_429:{wait}")
        if last_err:
            logger.error(f"Error en Groq: {last_err}")
        return None
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error en Groq: {e}")
        return None

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
    [['📜 Ver Lista', '🆕 Nueva Lista'], ['📊 API Status', '❓ Ayuda']],
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
    active = get_active_key_name()

    def barra(pct):
        filled = int(min(pct, 100) / 10)
        return "█" * filled + "░" * (10 - filled)

    texto = f"🤖 <b>Estado API Groq</b>\n<b>Modelo:</b> <code>{GROQ_MODEL}</code>\n\n"
    for name, label in [("primary", "Principal"), ("backup", "Backup")]:
        if name not in _clients:
            continue
        marker = "▶ " if name == active else "    "
        q = load_quota(name)
        count, tokens = q["count"], q["tokens"]
        pct_req = count / GROQ_RPD * 100
        pct_tok = tokens / GROQ_TPD * 100
        texto += (
            f"{marker}🔑 <b>Key {label}</b>\n"
            f"Solicitudes: {barra(pct_req)} <code>{count}/{GROQ_RPD}</code> ({pct_req:.1f}%)\n"
            f"Tokens: {barra(pct_tok)} <code>{tokens:,}/{GROQ_TPD:,}</code> ({pct_tok:.1f}%)\n\n"
        )
    texto += f"<b>Límite:</b> {GROQ_RPM} req/min | reset 7pm Colombia"

    btns = []
    if len(_clients) > 1:
        other = "backup" if active == "primary" else "primary"
        other_label = "Backup" if other == "backup" else "Principal"
        btns.append([InlineKeyboardButton(f"🔄 Cambiar a Key {other_label}", callback_data="switch_key")])
    return texto, InlineKeyboardMarkup(btns) if btns else None

async def ver_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto, markup = _build_api_status()
    await update.message.reply_text(texto, parse_mode='HTML',
                                    reply_markup=markup or MAIN_KEYBOARD)

async def ver_lista(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user_id = str(update.effective_user.id)
    user_list = load_data().get(user_id, [])

    if not user_list:
        await update.message.reply_text("La lista está vacía. 📭", reply_markup=MAIN_KEYBOARD)
        return

    texto, markup = construir_pagina_lista(user_list, page)
    await update.message.reply_text(texto, parse_mode='HTML', reply_markup=markup)

async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🔍 Analizando con IA...")
    file_path = f"temp_{update.message.message_id}.jpg"

    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)

        try:
            datos = await analizar_comprobante(file_path)
        except RuntimeError as e:
            await status_msg.delete()
            msg = str(e)
            if msg.startswith("GROQ_429:"):
                wait = msg.split(":", 1)[1]
                await update.message.reply_text(
                    f"⏳ <b>Límite de Groq alcanzado.</b>\n\n"
                    f"Intenta de nuevo en <b>{wait}</b>.\n"
                    f"La cuota diaria se resetea a las <b>7pm hora Colombia</b>.",
                    parse_mode='HTML', reply_markup=MAIN_KEYBOARD
                )
            else:
                await update.message.reply_text(
                    "❌ Error al analizar la imagen. Intenta de nuevo.",
                    reply_markup=MAIN_KEYBOARD
                )
            return
        except Exception as e:
            await status_msg.delete()
            await update.message.reply_text(
                "❌ Error al analizar la imagen. Intenta de nuevo.",
                reply_markup=MAIN_KEYBOARD
            )
            return

        if not datos:
            await status_msg.delete()
            await update.message.reply_text(
                "❌ No pude entender la imagen. Revisa los logs del bot para ver el error.",
                reply_markup=MAIN_KEYBOARD
            )
            return

        aviso_cuota = ""

        res_de = datos.get("de", "No encontrada")
        res_valor = datos.get("valor", "$0")
        res_fecha = datos.get("fecha", "No encontrada")
        res_hora = datos.get("hora", "No encontrada")
        res_ref = datos.get("ref", "No encontrada")

        # --- REGLA DE NEGOCIO: Corresponsal basado en Referencia ---
        if res_ref == "No encontrada" or res_ref.strip().upper().startswith('S'):
            res_de = "Corresponsal"

        # --- DETECCIÓN DE DUPLICADO ---
        user_id = str(update.effective_user.id)
        user_list = load_data().get(user_id, [])
        dup = buscar_duplicado(user_list, res_ref)

        # --- PERSISTENCIA DE IMAGEN Y LOG ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ref_clean = res_ref.replace(" ", "_")
        final_image_name = f"{timestamp}_{user_id}_{ref_clean}.jpg"
        final_path = os.path.join(LOG_DIR, final_image_name)
        
        # Copiar imagen temporal a carpeta de logs en lugar de borrarla
        os.rename(file_path, final_path)
        file_path = None # Evitar que el finally intente borrarla

        # Guardar log técnico
        log_debug_info(user_id, datos, final_image_name)

        p_id = str(update.message.message_id)
        context.user_data[p_id] = {
            "de": res_de, "valor": res_valor,
            "fecha": res_fecha, "hora": res_hora, "ref": res_ref,
            "img_log": final_image_name # Guardamos referencia a la imagen
        }

        response = (f"✨ <b>Datos Detectados por IA:</b>\n\n"
                    f"👤 <b>Contacto:</b> <code>{html.escape(res_de)}</code>\n"
                    f"💰 <b>Valor:</b> <code>{html.escape(res_valor)}</code>\n"
                    f"📅 <b>Fecha:</b> <code>{html.escape(res_fecha)}</code>\n"
                    f"🕒 <b>Hora:</b> <code>{html.escape(res_hora)}</code>\n"
                    f"🔢 <b>Ref:</b> <code>{html.escape(res_ref)}</code>"
                    f"{aviso_cuota}")

        if dup:
            dup_idx, dup_item = dup
            response += (f"\n\n⚠️ <b>Posible duplicado:</b> esta referencia ya está "
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

        await status_msg.delete()
        await update.message.reply_text(response, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Error al procesar la imagen.", reply_markup=MAIN_KEYBOARD)
    finally:
        # Verificamos que file_path no sea None antes de intentar borrar
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

    # --- CAMBIAR KEY ACTIVA ---
    if raw == "switch_key":
        active = get_active_key_name()
        other = "backup" if active == "primary" else "primary"
        if other in _clients:
            set_active_key_name(other)
            other_label = "Backup" if other == "backup" else "Principal"
            await query.answer(f"✅ Cambiado a Key {other_label}")
            texto, markup = _build_api_status()
            await query.edit_message_text(texto, parse_mode='HTML', reply_markup=markup)
        else:
            await query.answer("❌ Key backup no configurada")
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
