import os
import re
import logging
import easyocr
import json
import torch
import csv
import cv2
import numpy as np
import html
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

use_gpu = torch.cuda.is_available()
print(f"🚀 {'GPU Detectada' if use_gpu else 'CPU Usada'}")
reader = easyocr.Reader(['es'], gpu=use_gpu)

# Configuración de carpetas
DATA_FILE = "listas_nequi.json"
LOG_DIR = "logs_comprobantes"
PAGE_SIZE = 5

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

# ---------------------------------------------------------------------------
# OCR e imagen
# ---------------------------------------------------------------------------

def preprocesar_imagen(path):
    """Preprocesamiento optimizado para capturas de Nequi desde el mismo celular."""
    img = cv2.imread(path)
    if img is None:
        return path

    # Upscale 2x — mayor resolución = OCR más preciso en texto pequeño de móvil
    img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Filtro bilateral: elimina ruido JPEG preservando bordes del texto
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # CLAHE con clipLimit mayor para capturas de pantalla móvil
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)

    # Kernel de nitidez para texto
    kernel = np.array([[0, -1, 0],
                       [-1,  5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(contrast, -1, kernel)

    proc_path = "proc_" + os.path.basename(path)
    cv2.imwrite(proc_path, sharpened)
    return proc_path

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
        InlineKeyboardButton("📊 CSV", callback_data="download_csv"),
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
    status_msg = await update.message.reply_text("🔍 Analizando datos...")
    file_path = f"temp_{update.message.message_id}.jpg"
    proc_path = None
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)

        proc_path = preprocesar_imagen(file_path)

        raw_results = reader.readtext(
            proc_path,
            detail=1,
            paragraph=False,
            contrast_ths=0.1,
            adjust_contrast=0.5,
            text_threshold=0.7,
            low_text=0.4,
        )

        MIN_CONF = 0.3
        results = [(bbox, text.strip(), conf) for bbox, text, conf in raw_results if conf >= MIN_CONF and text.strip()]
        results.sort(key=lambda r: r[0][0][1])  # top-left y

        blocks = [text for _, text, _ in results]
        full_txt = " ".join(blocks)
        logger.info(f"Bloques OCR ({len(blocks)}): {blocks}")

        res_de = "Corresponsal"
        res_valor = "$0"
        res_fecha = "No encontrada"
        res_hora = "No encontrada"
        res_ref = "No encontrada"

        for i, (bbox, text, conf) in enumerate(results):
            t_clean = text.lower()

            if t_clean in ["de", "para"] and i + 1 < len(results):
                posible = results[i + 1][1]
                if "¿cu" not in posible.lower() and "$" not in posible and len(posible) > 2:
                    res_de = posible

            if "$" in text:
                val_match = re.search(r'\$\s*[\d\.]+', text)
                if val_match:
                    res_valor = val_match.group(0).replace(" ", "")

            if re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+20\d{2}', text, re.IGNORECASE):
                h_match = re.search(r'\d{1,2}[:.]\d{2}\s*[aApP]\.?\s*[mM]\.?', text)
                if h_match:
                    res_hora = h_match.group(0).strip()
                    res_fecha = re.sub(r'\d{1,2}[:.]\d{2}\s*[aApP]\.?\s*[mM]\.?', '', text)
                    res_fecha = res_fecha.replace("a las", "").strip(" ,-")
                else:
                    res_fecha = text

            if re.search(r'^(referencia|ref\.?)$', t_clean):
                if i + 1 < len(results):
                    res_ref = results[i + 1][1]

        if res_valor == "$0":
            val_fall = re.search(r'\$\s*[\d\.]{3,}', full_txt)
            if val_fall:
                res_valor = val_fall.group(0).replace(" ", "")

        if res_fecha == "No encontrada":
            fecha_fall = re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+20\d{2}', full_txt, re.IGNORECASE)
            if fecha_fall:
                res_fecha = fecha_fall.group(0)

        if res_hora == "No encontrada":
            hora_fall = re.search(r'\d{1,2}[:.]\d{2}\s*[aApP]\.?\s*[mM]\.?', full_txt, re.IGNORECASE)
            if hora_fall:
                res_hora = hora_fall.group(0).strip()

        if res_ref == "No encontrada":
            ref_fall = re.search(r'\bM[O0-9]{9,}\b|\b\d{10,}\b', full_txt, re.IGNORECASE)
            if ref_fall:
                res_ref = ref_fall.group(0)

        if res_ref != "No encontrada":
            if res_ref.upper().startswith('M'):
                res_ref = 'M' + res_ref[1:].upper().replace('O', '0')
            else:
                res_ref = res_ref.replace('O', '0').replace('o', '0')

        # --- DETECCIÓN DE DUPLICADO ---
        user_id = str(update.effective_user.id)
        user_list = load_data().get(user_id, [])
        dup = buscar_duplicado(user_list, res_ref)

        # --- PERSISTENCIA DE IMAGEN ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ref_clean = res_ref.replace(" ", "_").replace("/", "-")
        final_image_name = f"ocr_{timestamp}_{user_id}_{ref_clean}.jpg"
        final_path = os.path.join(LOG_DIR, final_image_name)
        
        os.rename(file_path, final_path)
        file_path = None # Evitar borrado en finally

        p_id = str(update.message.message_id)
        context.user_data[p_id] = {
            "de": res_de, "valor": res_valor,
            "fecha": res_fecha, "hora": res_hora, "ref": res_ref,
            "img_log": final_image_name
        }

        response = (f"✅ <b>Datos Detectados:</b>\n\n"
                    f"👤 <b>Contacto:</b> <code>{html.escape(res_de)}</code>\n"
                    f"💰 <b>Valor:</b> <code>{html.escape(res_valor)}</code>\n"
                    f"📅 <b>Fecha:</b> <code>{html.escape(res_fecha)}</code>\n"
                    f"🕒 <b>Hora:</b> <code>{html.escape(res_hora)}</code>\n"
                    f"🔢 <b>Ref:</b> <code>{html.escape(res_ref)}</code>")

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
        await update.message.reply_text("❌ Error al procesar.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if proc_path and os.path.exists(proc_path):
            os.remove(proc_path)


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

    if raw == "download_csv":
        if not user_list:
            return
        file_name = f"lista_{user_id}.csv"
        with open(file_name, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['#', 'Contacto', 'Valor', 'Fecha', 'Hora', 'Referencia'])
            for idx, item in enumerate(user_list, 1):
                writer.writerow([idx, item['de'], item['valor'], item['fecha'], item.get('hora', ''), item['ref']])
        await context.bot.send_document(chat_id=user_id, document=open(file_name, 'rb'), filename="Lista_Nequi.csv")
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
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, process_photo))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.run_polling()
