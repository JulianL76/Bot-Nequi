import os
import re
import logging
import json
import csv
import html
import asyncio
import time
from google import genai
import pandas as pd
from PIL import Image
from datetime import datetime
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
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_KEY_BACKUP = os.getenv("GEMINI_API_KEY_BACKUP")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash-lite"
_usando_backup = False
_last_gemini_call = 0.0
GEMINI_MIN_INTERVAL = 4.5  # máx ~13 req/min, por debajo del límite de 15

def configurar_gemini(api_key):
    return genai.Client(api_key=api_key, http_options={"timeout": 60, "retryOptions": {"attempts": 1}})

if GEMINI_KEY:
    gemini = configurar_gemini(GEMINI_KEY)
else:
    logger.error("❌ No se encontró GEMINI_API_KEY en el archivo .env")
    gemini = None

def switch_a_backup():
    global gemini, _usando_backup
    if GEMINI_KEY_BACKUP and not _usando_backup:
        gemini = configurar_gemini(GEMINI_KEY_BACKUP)
        _usando_backup = True
        logger.warning("Cuota principal agotada — cambiando a API key de backup")
        return True
    return False

# Configuración de carpetas y archivos
DATA_FILE = "listas_nequi.json"
LOG_DIR = "logs_comprobantes"
DEBUG_FILE = "debug_log.json"
QUOTA_FILE = "quota_tracker.json"
PAGE_SIZE = 5
DAILY_LIMIT = 1500
QUOTA_WARN = 1200  # avisar al llegar al 80%

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ---------------------------------------------------------------------------
# Cuota diaria Gemini
# ---------------------------------------------------------------------------

def load_quota() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if os.path.exists(QUOTA_FILE) and os.path.getsize(QUOTA_FILE) > 0:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today:
                return data.get("count", 0)
    except Exception:
        pass
    return 0

def increment_quota() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    count = load_quota() + 1
    with open(QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today, "count": count}, f)
    return count

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

async def analizar_comprobante(path):
    global _last_gemini_call
    prompt = """
    Analiza esta imagen de un comprobante de Nequi y extrae los datos para un sistema contable.
    Responde ÚNICAMENTE con un objeto JSON con esta estructura exacta:
    {
      "de": "Nombre de la persona o entidad que envía (o 'Corresponsal')",
      "valor": "$0.000 (con símbolo y puntos)",
      "fecha": "DD de Mes de AAAA",
      "hora": "HH:MM am/pm",
      "ref": "Número de referencia o movimiento"
    }
    Si no encuentras un dato, usa "No encontrada". No añadas texto extra, solo el JSON.
    """
    try:
        # Respetar límite de 15 req/min
        espera = GEMINI_MIN_INTERVAL - (time.monotonic() - _last_gemini_call)
        if espera > 0:
            await asyncio.sleep(espera)
        _last_gemini_call = time.monotonic()

        with Image.open(path) as img:
            img.load()
            pil_img = img.copy()

        try:
            response = gemini.models.generate_content(model=GEMINI_MODEL, contents=[prompt, pil_img])
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                delay_match = re.search(r'"seconds":\s*"?(\d+)"?', err) or re.search(r'retry in (\d+)', err)
                retry_after = int(delay_match.group(1)) if delay_match else 20
                if "PerDay" in err or "PerModelPerDay" in err:
                    if switch_a_backup():
                        response = gemini.models.generate_content(model=GEMINI_MODEL, contents=[prompt, pil_img])
                    else:
                        raise
                else:
                    logger.warning(f"Límite por minuto — esperando {retry_after}s")
                    await asyncio.sleep(retry_after)
                    _last_gemini_call = time.monotonic()
                    response = gemini.models.generate_content(model=GEMINI_MODEL, contents=[prompt, pil_img])
            else:
                raise

        clean_json = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise
        logger.error(f"Error en Gemini: {e}")
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
    [['📜 Ver Lista', '🆕 Nueva Lista'], ['❓ Ayuda']],
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
        quota_actual = load_quota()
        if quota_actual >= DAILY_LIMIT:
            await status_msg.delete()
            await update.message.reply_text(
                f"🚫 <b>Límite diario alcanzado</b>\n\n"
                f"Se usaron las {DAILY_LIMIT} consultas de hoy a Gemini AI.\n"
                f"El límite se resetea a las <b>7pm hora Colombia</b>.\n\n"
                f"Intenta de nuevo más tarde.",
                parse_mode='HTML',
                reply_markup=MAIN_KEYBOARD
            )
            return

        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)

        try:
            datos = await analizar_comprobante(file_path)
        except Exception as quota_err:
            await status_msg.delete()
            await update.message.reply_text(
                "🚫 <b>Cuota de Gemini agotada.</b>\n\nIntenta de nuevo a las 7pm hora Colombia.",
                parse_mode='HTML',
                reply_markup=MAIN_KEYBOARD
            )
            return

        if not datos:
            await status_msg.delete()
            await update.message.reply_text(
                "❌ No pude entender la imagen. Intenta con otra.",
                reply_markup=MAIN_KEYBOARD
            )
            return

        quota_actual = increment_quota()
        aviso_cuota = ""
        if quota_actual >= QUOTA_WARN:
            restantes = DAILY_LIMIT - quota_actual
            aviso_cuota = f"\n\n⚠️ <i>Cuota: {quota_actual}/{DAILY_LIMIT} — quedan {restantes} consultas hoy</i>"

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
        
        # Intentar convertir horas a formato tiempo de Excel
        # Quitamos puntos extras (como a. m.) para que pandas lo entienda mejor
        df['hora_clean'] = df['hora'].str.replace('.', '', regex=False).str.upper()
        df['Hora'] = pd.to_datetime(df['hora_clean'], errors='coerce').dt.time
        
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
    elif t == '❓ Ayuda':
        await update.message.reply_text("Envíame fotos de Nequi.")


if __name__ == '__main__':
    if not TOKEN:
        print("❌ Token no configurado")
    else:
        # Construir la aplicación con tiempos de espera extendidos (30s) para evitar 'Timed out'
        app = ApplicationBuilder().token(TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, process_photo))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.run_polling()
