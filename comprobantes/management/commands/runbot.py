"""Bot de Telegram conectado al ORM de Django y al núcleo compartido.

Reemplaza la persistencia JSON del bot original: cada comprobante se guarda en
la misma base de datos que la web (modelo Comprobante), enlazado al negocio del
usuario de Telegram (creado automáticamente la primera vez).

Porta la interfaz completa de botones del bot original: datos detectados con
Guardar/Editar/Descartar, lista paginada (◀▶) con descargas TXT/Excel y
eliminación por botones, selector de IA y estado de APIs.

Uso:  python manage.py runbot
"""

import html
import io
import os
import tempfile
from datetime import datetime

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update,
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

from accounts.models import Negocio, PerfilUsuario
from comprobantes.models import Comprobante
from core import config
from core.extraction import analizar_comprobante, groq_client, gemini_client
from core.parsing import buscar_duplicado, fmt_total, limpiar_monto
from core.quota import get_preferred_ia, load_quota, set_preferred_ia

User = get_user_model()

PAGE_SIZE = 5
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [['📜 Ver Lista', '🆕 Nueva Lista'], ['📊 API Status', '🤖 IA', '❓ Ayuda']],
    resize_keyboard=True,
)


def fmt_money(valor) -> str:
    return f"${float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Acceso a datos (ORM) envuelto para contexto async
# ---------------------------------------------------------------------------

@sync_to_async
def _resolver_negocio(tg_user):
    perfil = PerfilUsuario.objects.filter(telegram_id=tg_user.id).select_related(
        "user", "negocio"
    ).first()
    if perfil and perfil.negocio:
        return perfil.user, perfil.negocio
    username = f"tg_{tg_user.id}"
    user, _ = User.objects.get_or_create(
        username=username, defaults={"first_name": (tg_user.first_name or "")[:30]}
    )
    negocio, _ = Negocio.objects.get_or_create(nombre=f"Negocio de {username}")
    PerfilUsuario.objects.get_or_create(
        user=user,
        defaults={"negocio": negocio, "telegram_id": tg_user.id,
                  "rol": PerfilUsuario.ROL_ADMIN},
    )
    return user, negocio


@sync_to_async
def _listar(negocio):
    """Lista de dicts (más antiguo primero, factura #1 = primera guardada)."""
    return [
        {"id": c.id, "de": c.de, "valor": c.valor_raw or fmt_money(c.valor),
         "valor_dec": float(c.valor), "fecha": c.fecha, "hora": c.hora, "ref": c.ref}
        for c in Comprobante.objects.filter(negocio=negocio).order_by("creado_en")
    ]


@sync_to_async
def _crear(negocio, user, item, img_path=None):
    comp = Comprobante.objects.create(
        negocio=negocio, creado_por=user,
        de=item.get("de", "No encontrada"),
        valor=limpiar_monto(item.get("valor", "0")),
        valor_raw=item.get("valor", ""),
        fecha=item.get("fecha", ""), hora=item.get("hora", ""),
        ref=(item.get("ref") or "").strip(),
        fuente_ia=item.get("ia", ""), origen=Comprobante.ORIGEN_TELEGRAM,
    )
    if img_path and os.path.exists(img_path):
        from django.core.files import File
        with open(img_path, "rb") as fh:
            comp.imagen.save(os.path.basename(img_path), File(fh), save=True)
    return Comprobante.objects.filter(negocio=negocio).count()


@sync_to_async
def _eliminar(negocio, pk):
    comp = Comprobante.objects.filter(negocio=negocio, pk=pk).first()
    if comp:
        datos = (comp.de, comp.valor_raw or fmt_money(comp.valor), comp.ref)
        comp.delete()
        return datos
    return None


@sync_to_async
def _vaciar(negocio):
    Comprobante.objects.filter(negocio=negocio).delete()


# ---------------------------------------------------------------------------
# Construcción de vistas (texto + teclados)
# ---------------------------------------------------------------------------

def construir_pagina_lista(lista, page):
    n = len(lista)
    total_pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start, end = page * PAGE_SIZE, min((page + 1) * PAGE_SIZE, n)

    texto = (f"📜 <b>Lista Nequi</b> — {n} factura{'s' if n != 1 else ''} | "
             f"<b>{html.escape(fmt_total(lista))}</b>\n"
             f"<i>Página {page + 1} de {total_pages}</i>\n\n")
    for i in range(start, end):
        it = lista[i]
        texto += (f"{i + 1}. 💰 <b>{html.escape(str(it['valor']))}</b> — 👤 {html.escape(it.get('de', 'N/A'))}\n"
                  f"   🔢 {html.escape(it.get('ref', 'N/A'))} | 📅 {html.escape(it.get('fecha', 'N/A'))}\n\n")

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Anterior", callback_data=f"lista_p_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if end < n:
        nav.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"lista_p_{page + 1}"))

    botones = [nav] if nav else []
    botones.append([
        InlineKeyboardButton("📥 TXT", callback_data="download_txt"),
        InlineKeyboardButton("📊 EXCEL", callback_data="download_xlsx"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_menu_{page}"),
    ])
    return texto, InlineKeyboardMarkup(botones)


def construir_resumen_guardado(num):
    return f"💾 <b>Guardada como factura #{num}</b>"


def _datos_detectados_text(item, ia="Groq", titulo="Datos Detectados"):
    badge = "⚡ <i>Groq</i>" if ia == "Groq" else "✨ <i>Gemini</i>"
    return (f"{badge} — <b>{titulo}:</b>\n\n"
            f"👤 <b>Contacto:</b> <code>{html.escape(item['de'])}</code>\n"
            f"💰 <b>Valor:</b> <code>{html.escape(item['valor'])}</code>\n"
            f"📅 <b>Fecha:</b> <code>{html.escape(item['fecha'])}</code>\n"
            f"🕒 <b>Hora:</b> <code>{html.escape(item['hora'])}</code>\n"
            f"🔢 <b>Ref:</b> <code>{html.escape(item['ref'])}</code>")


def _btns_resultado(p_id, duplicado=False):
    save_cb = f"force_save_{p_id}" if duplicado else f"save_{p_id}"
    save_lbl = "⚠️ Guardar igual" if duplicado else "✅ Guardar"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(save_lbl, callback_data=save_cb),
         InlineKeyboardButton("✏️ Editar", callback_data=f"edit_menu_{p_id}")],
        [InlineKeyboardButton("❌ Descartar", callback_data=f"cancel_{p_id}")],
    ])


def _btns_429():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Reintentar", callback_data="groq_retry")]])


# ---------------------------------------------------------------------------
# Handlers de comandos / texto
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy tu gestor Nequi.\nEnvíame capturas y gestionaré tus cobros.",
        reply_markup=MAIN_KEYBOARD,
    )


async def ver_lista(update_or_query, context, negocio, page=0, edit=False):
    lista = await _listar(negocio)
    if not lista:
        msg = "La lista está vacía. 📭"
        if edit:
            await update_or_query.edit_message_text(msg)
        else:
            await update_or_query.message.reply_text(msg, reply_markup=MAIN_KEYBOARD)
        return
    texto, markup = construir_pagina_lista(lista, page)
    if edit:
        await update_or_query.edit_message_text(texto, parse_mode='HTML', reply_markup=markup)
    else:
        await update_or_query.message.reply_text(texto, parse_mode='HTML', reply_markup=markup)


def _api_status_text():
    def barra(used, total):
        pct = min(used / total * 100, 100) if total > 0 else 0
        return "█" * int(pct / 10) + "░" * (10 - int(pct / 10)), pct
    q = load_quota()
    count, tokens = q["count"], q["tokens"]
    b, pct = barra(tokens, config.GROQ_TPD)
    groq_estado = "🟢 Activo" if groq_client else "⚫ No configurado"
    gem_estado = "🟢 Configurado" if gemini_client else "⚫ No configurado"
    return (f"🤖 <b>Estado APIs</b>\n\n"
            f"⚡ <b>Groq</b>: {groq_estado}\n"
            f"Solicitudes: <code>{count}/{config.GROQ_RPD}</code>\n"
            f"Tokens: {b} <code>{tokens:,}/{config.GROQ_TPD:,}</code> ({pct:.1f}%)\n"
            f"<i>Reset 7pm Colombia</i>\n\n"
            f"🔁 <b>Fallback Gemini</b>: {gem_estado}")


def _btns_ia(preferida):
    gm = "✅ " if preferida == "groq" else ""
    em = "✅ " if preferida == "gemini" else ""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{gm}⚡ Groq", callback_data="ia_set_groq"),
        InlineKeyboardButton(f"{em}✨ Gemini", callback_data="ia_set_gemini"),
    ]])


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text

    # --- MODO EDICIÓN: el usuario escribe el nuevo valor de un campo ---
    if 'editing' in context.user_data:
        info = context.user_data.pop('editing')
        p_id, field = info["p_id"], info["field"]
        if p_id in context.user_data:
            context.user_data[p_id][field] = t
            item = context.user_data[p_id]
            await update.message.reply_text(
                _datos_detectados_text(item, item.get("ia", "Groq"), "Dato Actualizado"),
                parse_mode='HTML', reply_markup=_btns_resultado(p_id),
            )
        return

    if t == '📜 Ver Lista':
        _, negocio = await _resolver_negocio(update.effective_user)
        await ver_lista(update, context, negocio)
    elif t == '🆕 Nueva Lista':
        _, negocio = await _resolver_negocio(update.effective_user)
        await _vaciar(negocio)
        await update.message.reply_text("🧹 Lista borrada.", reply_markup=MAIN_KEYBOARD)
    elif t == '📊 API Status':
        await update.message.reply_text(_api_status_text(), parse_mode='HTML',
                                        reply_markup=MAIN_KEYBOARD)
    elif t == '🤖 IA':
        pref = get_preferred_ia()
        await update.message.reply_text(
            f"🤖 <b>IA activa:</b> {'⚡ Groq' if pref == 'groq' else '✨ Gemini'}\n\n"
            "Elige cuál usar para analizar los comprobantes:",
            parse_mode='HTML', reply_markup=_btns_ia(pref),
        )
    elif t == '❓ Ayuda':
        await update.message.reply_text("Envíame fotos de Nequi y las guardaré en tu cuenta web.")


# ---------------------------------------------------------------------------
# Foto → análisis
# ---------------------------------------------------------------------------

async def _mostrar_resultado(datos, negocio, p_id, context, send_fn, ia="Groq"):
    item = {
        "de": datos.get("de", "No encontrada"),
        "valor": datos.get("valor", "$0"),
        "fecha": datos.get("fecha", "No encontrada"),
        "hora": datos.get("hora", "No encontrada"),
        "ref": datos.get("ref", "No encontrada"),
        "ia": ia,
    }
    context.user_data[p_id] = item

    lista = await _listar(negocio)
    dup = buscar_duplicado(lista, item["ref"])
    texto = _datos_detectados_text(item, ia)
    if dup:
        idx, ditem = dup
        texto += (f"\n\n⚠️ <b>Posible duplicado:</b> la referencia ya está en la "
                  f"factura #{idx} de {html.escape(ditem.get('de', '?'))} "
                  f"({html.escape(str(ditem['valor']))})")
    await send_fn(texto, parse_mode='HTML', reply_markup=_btns_resultado(p_id, bool(dup)))


async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("groq_paused"):
        await update.message.reply_text(
            "⏳ <b>Bot pausado</b> — límite activo de Groq. Usa los botones del "
            "último mensaje para reintentar.", parse_mode='HTML', reply_markup=MAIN_KEYBOARD)
        return

    status = await update.message.reply_text("🔍 Analizando con IA...")
    _, negocio = await _resolver_negocio(update.effective_user)
    p_id = str(update.message.message_id)

    photo = await update.message.photo[-1].get_file()
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    await photo.download_to_drive(path)

    try:
        datos, ia = await analizar_comprobante(path)
    except RuntimeError as e:
        await status.delete()
        msg = str(e)
        if msg.startswith("GROQ_429:") or msg.startswith("ALL_429:"):
            wait = msg.split(":", 1)[1]
            context.user_data["groq_paused"] = True
            context.user_data["groq_pending"] = {"img_path": path, "p_id": p_id}
            detalle = "Groq y Gemini tienen límite activo." if msg.startswith("ALL_429:") else "Límite de Groq alcanzado."
            await update.message.reply_text(
                f"⏳ <b>{detalle}</b>\n\nIntenta de nuevo en <b>{wait}</b>.",
                parse_mode='HTML', reply_markup=_btns_429())
        else:
            await update.message.reply_text("❌ Error al analizar la imagen.", reply_markup=MAIN_KEYBOARD)
        return
    except Exception:
        await status.delete()
        await update.message.reply_text("❌ Error al analizar la imagen.", reply_markup=MAIN_KEYBOARD)
        return

    if not datos:
        await status.delete()
        await update.message.reply_text("❌ No pude entender la imagen.", reply_markup=MAIN_KEYBOARD)
        os.remove(path)
        return

    context.user_data[f"img_{p_id}"] = path  # guardar ruta para adjuntar al guardar
    await status.delete()
    await _mostrar_resultado(datos, negocio, p_id, context,
                             update.message.reply_text, ia=ia or "Groq")


# ---------------------------------------------------------------------------
# Callbacks de botones
# ---------------------------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    raw = query.data
    user, negocio = await _resolver_negocio(update.effective_user)

    if raw == "noop":
        return

    # --- RETRY tras 429 ---
    if raw == "groq_retry":
        pending = context.user_data.get("groq_pending")
        if not pending:
            await query.answer("❌ No hay imagen pendiente")
            return
        img_path, p_id = pending["img_path"], pending["p_id"]
        if not os.path.exists(img_path):
            await query.edit_message_text("❌ La imagen ya no está. Envíala de nuevo.")
            context.user_data.pop("groq_paused", None)
            context.user_data.pop("groq_pending", None)
            return
        await query.edit_message_text("🔍 Analizando con IA...")
        try:
            datos, ia = await analizar_comprobante(img_path)
        except RuntimeError as e:
            msg = str(e)
            wait = msg.split(":", 1)[1] if ":" in msg else "unos minutos"
            await query.edit_message_text(f"⏳ Límite activo. Intenta en <b>{wait}</b>.",
                                          parse_mode='HTML', reply_markup=_btns_429())
            return
        except Exception:
            await query.edit_message_text("❌ Error al analizar.")
            return
        context.user_data.pop("groq_paused", None)
        context.user_data.pop("groq_pending", None)
        if not datos:
            await query.edit_message_text("❌ No pude entender la imagen.")
            return
        context.user_data[f"img_{p_id}"] = img_path
        await _mostrar_resultado(datos, negocio, p_id, context,
                                 query.edit_message_text, ia=ia or "Groq")
        return

    # --- Selector de IA ---
    if raw in ("ia_set_groq", "ia_set_gemini"):
        nueva = "groq" if raw == "ia_set_groq" else "gemini"
        set_preferred_ia(nueva)
        nombre = "⚡ Groq" if nueva == "groq" else "✨ Gemini"
        await query.edit_message_text(
            f"🤖 <b>IA activa:</b> {nombre}\n\nElige cuál usar:",
            parse_mode='HTML', reply_markup=_btns_ia(nueva))
        return

    # --- Descargas ---
    if raw == "download_txt":
        lista = await _listar(negocio)
        if not lista:
            return
        buf = io.BytesIO()
        contenido = "REPORTE NEQUI\n" + "=" * 20 + "\n"
        for i, it in enumerate(lista, 1):
            contenido += f"{i}. {it['de']} | {it['valor']} | {it['fecha']} | {it.get('hora','')} | {it['ref']}\n"
        buf.write(contenido.encode("utf-8"))
        buf.seek(0)
        await context.bot.send_document(chat_id=query.message.chat_id, document=buf,
                                        filename="Lista_Nequi.txt")
        return

    if raw == "download_xlsx":
        lista = await _listar(negocio)
        if not lista:
            return
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Comprobantes"
        ws.append(["Contacto", "Monto", "Fecha", "Hora", "Referencia"])
        for it in lista:
            ws.append([it['de'], it['valor_dec'], it['fecha'], it.get('hora', ''), it['ref']])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        await context.bot.send_document(chat_id=query.message.chat_id, document=buf,
                                        filename="Lista_Nequi.xlsx")
        return

    # --- Paginación ---
    if raw.startswith("lista_p_"):
        await ver_lista(query, context, negocio, int(raw.split("_")[2]), edit=True)
        return

    # --- Eliminar: menú ---
    if raw.startswith("del_menu_"):
        page = int(raw.split("_")[2])
        lista = await _listar(negocio)
        if not lista:
            await query.edit_message_text("La lista está vacía. 📭")
            return
        n = len(lista)
        total_pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start, end = page * PAGE_SIZE, min((page + 1) * PAGE_SIZE, n)
        texto = (f"🗑️ <b>Eliminar factura</b> — elige el número:\n"
                 f"<i>Página {page + 1} de {total_pages}</i>\n\n")
        btns, row = [], []
        for i in range(start, end):
            it = lista[i]
            texto += f"{i + 1}. {html.escape(it.get('de', '?'))} — {html.escape(str(it['valor']))}\n"
            row.append(InlineKeyboardButton(f"#{i + 1}", callback_data=f"del_ask_{it['id']}_{page}"))
            if len(row) == 4:
                btns.append(row); row = []
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

    # --- Eliminar: confirmar ---
    if raw.startswith("del_ask_"):
        _, _, pk, page = raw.split("_")
        lista = await _listar(negocio)
        it = next((x for x in lista if x["id"] == int(pk)), None)
        if not it:
            await query.edit_message_text("⚠️ Factura no encontrada.")
            return
        texto = (f"⚠️ ¿Eliminar esta factura?\n\n"
                 f"👤 {html.escape(it.get('de', '?'))}\n"
                 f"💰 {html.escape(str(it['valor']))}\n🔢 {html.escape(it.get('ref', 'N/A'))}")
        btns = [[InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"del_exec_{pk}_{page}"),
                 InlineKeyboardButton("❌ Cancelar", callback_data=f"lista_p_{page}")]]
        await query.edit_message_text(texto, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
        return

    # --- Eliminar: ejecutar ---
    if raw.startswith("del_exec_"):
        _, _, pk, page = raw.split("_")
        eliminada = await _eliminar(negocio, int(pk))
        lista = await _listar(negocio)
        if not lista:
            await query.edit_message_text("🗑️ Factura eliminada.\n\nLa lista quedó vacía. 📭")
            return
        page = min(int(page), (len(lista) - 1) // PAGE_SIZE)
        texto, markup = construir_pagina_lista(lista, page)
        await query.edit_message_text("🗑️ Factura eliminada.\n\n" + texto,
                                      parse_mode='HTML', reply_markup=markup)
        return

    # --- Guardar (normal o forzado) ---
    if raw.startswith("save_") or raw.startswith("force_save_"):
        p_id = raw.split("save_", 1)[1]
        item = context.user_data.get(p_id)
        if item:
            img_path = context.user_data.pop(f"img_{p_id}", None)
            num = await _crear(negocio, user, item, img_path)
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
            await query.edit_message_text(construir_resumen_guardado(num), parse_mode='HTML')
            del context.user_data[p_id]
        return

    # --- Descartar ---
    if raw.startswith("cancel_"):
        p_id = raw.split("_", 1)[1]
        context.user_data.pop(p_id, None)
        img_path = context.user_data.pop(f"img_{p_id}", None)
        if img_path and os.path.exists(img_path):
            os.remove(img_path)
        await query.edit_message_text("🗑️ Descartado.")
        return

    # --- Editar: menú de campos ---
    if raw.startswith("edit_menu_"):
        p_id = raw.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("👤 Contacto", callback_data=f"edit_field_{p_id}_de")],
            [InlineKeyboardButton("💰 Valor", callback_data=f"edit_field_{p_id}_valor")],
            [InlineKeyboardButton("📅 Fecha", callback_data=f"edit_field_{p_id}_fecha")],
            [InlineKeyboardButton("🕒 Hora", callback_data=f"edit_field_{p_id}_hora")],
            [InlineKeyboardButton("🔢 Ref", callback_data=f"edit_field_{p_id}_ref")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"back_{p_id}")],
        ]
        await query.edit_message_text("¿Qué campo deseas editar?",
                                      reply_markup=InlineKeyboardMarkup(btns))
        return

    # --- Editar: selección de campo ---
    if raw.startswith("edit_field_"):
        after = raw[len("edit_field_"):]
        field = after.rsplit("_", 1)[1]
        p_id = after.rsplit("_", 1)[0]
        context.user_data['editing'] = {"p_id": p_id, "field": field}
        await query.edit_message_text(
            f"✍️ Escribe el nuevo valor para <b>{field.capitalize()}</b>:", parse_mode='HTML')
        return

    # --- Volver a datos detectados ---
    if raw.startswith("back_"):
        p_id = raw.split("_", 1)[1]
        item = context.user_data.get(p_id)
        if item:
            await query.edit_message_text(
                _datos_detectados_text(item, item.get("ia", "Groq")),
                parse_mode='HTML', reply_markup=_btns_resultado(p_id))
        return


class Command(BaseCommand):
    help = "Arranca el bot de Telegram (polling) conectado a la BD."

    def handle(self, *args, **options):
        if not config.TELEGRAM_TOKEN:
            self.stderr.write(self.style.ERROR("Falta TELEGRAM_TOKEN en el entorno."))
            return
        app = (ApplicationBuilder().token(config.TELEGRAM_TOKEN)
               .connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
               .build())
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, process_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(CallbackQueryHandler(callback_handler))
        self.stdout.write(self.style.SUCCESS("🤖 Bot corriendo (Ctrl+C para parar)..."))
        app.run_polling()
