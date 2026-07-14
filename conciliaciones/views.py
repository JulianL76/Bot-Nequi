from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.utils import get_negocio
from comprobantes.models import Comprobante, Ruta

from .models import Conciliacion, LoteConciliacion
from .tasks import emparejar_item, procesar_conciliacion

# Tamaños de página permitidos en el panel global (evita castear un valor
# arbitrario del usuario directo a int() para Paginator).
PANEL_TAM_PAGINA = {"20", "50", "100", "200"}


def _excel_conciliaciones(qs, filename="conciliaciones.xlsx"):
    """Genera una respuesta Excel a partir de un queryset de Conciliacion."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Conciliaciones"
    ws.append(["De", "Para", "Valor", "Referencia", "Fecha", "Hora", "Tipo",
               "Resultado", "Lote", "Ruta", "Observaciones"])
    for it in qs:
        ws.append([
            it.de, it.para, float(it.valor), it.ref, it.fecha, it.hora,
            it.get_tipo_display() if it.tipo else "",
            it.get_resultado_display() if it.resultado else "",
            it.lote_id, it.ruta.numero if it.ruta else "", it.observaciones,
        ])
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"
    wb.save(response)
    return response


def _filtrar_conciliaciones(request, negocio):
    """Aplica los filtros (r/desde/hasta/ruta) y devuelve (queryset, contexto).

    Compartido por el panel paginado y la exportación a Excel para que ambos
    respeten exactamente los mismos filtros.
    """
    import datetime

    qs = (Conciliacion.objects.filter(negocio=negocio)
          .select_related("lote", "lote__ruta", "ruta", "comprobante")
          if negocio else Conciliacion.objects.none())

    # Resultado (mismo criterio que lote_detalle: "obs" = con observaciones).
    r = request.GET.get("r", "").strip()
    validos = {Conciliacion.OK, Conciliacion.PENDIENTE, Conciliacion.NO_ESTA,
               Conciliacion.REVISION, Conciliacion.DUPLICADO}
    if r in validos:
        qs = qs.filter(resultado=r)
    elif r == "obs":
        qs = qs.exclude(observaciones="")

    # Rango de fechas sobre fecha_dt (si vienen invertidas, se intercambian).
    desde = request.GET.get("desde", "").strip()
    hasta = request.GET.get("hasta", "").strip()
    desde_obj = hasta_obj = None
    try:
        if desde:
            desde_obj = datetime.datetime.strptime(desde, "%Y-%m-%d").date()
        if hasta:
            hasta_obj = datetime.datetime.strptime(hasta, "%Y-%m-%d").date()
    except ValueError:
        pass
    if desde_obj and hasta_obj and desde_obj > hasta_obj:
        desde_obj, hasta_obj = hasta_obj, desde_obj
        desde, hasta = hasta, desde
    if desde_obj:
        qs = qs.filter(fecha_dt__gte=desde_obj)
    if hasta_obj:
        qs = qs.filter(fecha_dt__lte=hasta_obj)

    # Ruta propia del ítem (admite varias y/o "sin" para sin ruta asignada).
    rutas_sel = request.GET.getlist("ruta")
    ids = [x for x in rutas_sel if x.isdigit()]
    incluir_sin = "sin" in rutas_sel
    if ids or incluir_sin:
        cond = Q()
        if ids:
            cond |= Q(ruta_id__in=ids)
        if incluir_sin:
            cond |= Q(ruta__isnull=True)
        qs = qs.filter(cond)

    ctx = {"r": r, "desde": desde, "hasta": hasta, "desde_obj": desde_obj,
           "hasta_obj": hasta_obj, "ruta_sel": ids, "ruta_sin": incluir_sin}
    return qs, ctx


def _volver_detalle(lote_id, r, sort=""):
    """Redirige al detalle conservando filtro (?r=) y orden (?sort=)."""
    resp = redirect("conciliaciones:lote_detalle", lote_id=lote_id)
    params = []
    if r:
        params.append(f"r={r}")
    if sort:
        params.append(f"sort={sort}")
    if params:
        resp["Location"] += "?" + "&".join(params)
    return resp


def _recontar_lote(lote):
    """Recalcula los contadores del lote a partir de los resultados de sus ítems."""
    items = lote.items
    lote.ok = items.filter(resultado=Conciliacion.OK).count()
    lote.pendientes = items.filter(resultado=Conciliacion.PENDIENTE).count()
    lote.no_esta = items.filter(resultado=Conciliacion.NO_ESTA).count()
    lote.revision = items.filter(resultado=Conciliacion.REVISION).count()
    lote.duplicados = items.filter(resultado=Conciliacion.DUPLICADO).count()
    lote.save(update_fields=["ok", "pendientes", "no_esta", "revision", "duplicados"])


@login_required
def lista(request):
    """Historial de conciliaciones (lotes de conciliación)."""
    negocio = get_negocio(request.user)
    qs = (LoteConciliacion.objects.filter(negocio=negocio).select_related("ruta")
          .annotate(n_obs=Count("items", filter=~Q(items__observaciones="")))
          .order_by("-creado_en")
          if negocio else LoteConciliacion.objects.none())
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "conciliaciones/lista.html", {"page": page})


@login_required
def panel(request):
    """Panel global: ítems de conciliación de TODOS los lotes/rutas del negocio.

    Permite filtrar por resultado (p. ej. solo pendientes) y rango de fechas,
    exportar lo filtrado a Excel, y paginar con un tamaño configurable.
    """
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    qs, ctx = _filtrar_conciliaciones(request, negocio)

    # Stats sobre TODO lo filtrado (no solo la página actual).
    stats = qs.aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(resultado=Conciliacion.OK)),
        pendiente=Count("id", filter=Q(resultado=Conciliacion.PENDIENTE)),
        no_esta=Count("id", filter=Q(resultado=Conciliacion.NO_ESTA)),
        revision=Count("id", filter=Q(resultado=Conciliacion.REVISION)),
        duplicado=Count("id", filter=Q(resultado=Conciliacion.DUPLICADO)),
    )
    stats["manuales"] = qs.filter(comprobante__origen=Comprobante.ORIGEN_MANUAL).count()

    # Ordenamiento (mismo whitelist que lote_detalle).
    sort = request.GET.get("sort", "").strip()
    base = sort[1:] if sort.startswith("-") else sort
    if base in {"valor", "fecha_dt", "hora", "ref", "resultado", "para"}:
        pagina_qs = qs.order_by(sort, "id")
    else:
        pagina_qs = qs.order_by("-fecha_dt", "-hora", "-id")
        sort = ""

    tam = request.GET.get("tam", "").strip()
    if tam not in PANEL_TAM_PAGINA:
        tam = "50"
    paginator = Paginator(pagina_qs, int(tam))
    page = paginator.get_page(request.GET.get("page"))

    rutas = Ruta.objects.filter(negocio=negocio, activa=True)
    return render(request, "conciliaciones/panel.html",
                  {"page": page, "stats": stats, "sort": sort, "tam": tam,
                   "rutas": rutas, **ctx})


@login_required
def exportar_panel(request):
    """Exporta a Excel el panel global según los filtros activos (r/fechas/ruta)."""
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    qs, _ = _filtrar_conciliaciones(request, negocio)
    return _excel_conciliaciones(qs.order_by("-fecha_dt", "-hora", "-id"), "conciliaciones.xlsx")


@login_required
def conciliar(request):
    """Sube imágenes asociadas a una ruta y lanza la conciliación."""
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    rutas = Ruta.objects.filter(negocio=negocio, activa=True)

    if request.method == "POST":
        ruta = get_object_or_404(Ruta, pk=request.POST.get("ruta"), negocio=negocio)
        archivos = request.FILES.getlist("imagenes")
        if not archivos:
            messages.error(request, "Selecciona al menos una imagen.")
            return redirect("conciliaciones:conciliar")

        lote = LoteConciliacion.objects.create(
            negocio=negocio, creado_por=request.user, ruta=ruta, total=len(archivos)
        )
        for f in archivos:
            Conciliacion.objects.create(negocio=negocio, lote=lote, ruta=ruta, imagen=f)
        procesar_conciliacion.delay(lote.id)
        messages.success(request, f"Conciliación #{lote.id} en proceso ({len(archivos)} imágenes).")
        return redirect("conciliaciones:lote_detalle", lote_id=lote.id)

    return render(request, "conciliaciones/conciliar.html", {"negocio": negocio, "rutas": rutas})


@login_required
def lote_detalle(request, lote_id):
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    items = lote.items.select_related("comprobante").all()
    n_obs_lote = lote.items.exclude(observaciones="").count()
    # Filtro por resultado (p. ej. solo revisión o solo no encontrados), u "obs" para
    # ver solo los ítems con observación.
    r = request.GET.get("r", "").strip()
    validos = {Conciliacion.OK, Conciliacion.PENDIENTE, Conciliacion.NO_ESTA,
               Conciliacion.REVISION, Conciliacion.DUPLICADO}
    if r in validos:
        items = items.filter(resultado=r)
    elif r == "obs":
        items = items.exclude(observaciones="")

    # Ordenamiento de los registros.
    sort = request.GET.get("sort", "").strip()
    base = sort[1:] if sort.startswith("-") else sort
    if base in {"valor", "fecha_dt", "hora", "ref", "resultado", "para"}:
        items = items.order_by(sort, "id")
    else:
        items = items.order_by("id")
        sort = ""

    items = list(items)
    # Para los duplicados, localizar el ítem ORIGINAL (OK con el mismo comprobante).
    for it in items:
        it.original = None
        if it.resultado == Conciliacion.DUPLICADO and it.comprobante_id:
            it.original = (Conciliacion.objects
                           .filter(comprobante_id=it.comprobante_id, resultado=Conciliacion.OK)
                           .select_related("lote", "lote__ruta").order_by("creado_en").first())

    return render(request, "conciliaciones/lote_detalle.html",
                  {"lote": lote, "items": items, "filtro_r": r, "sort": sort, "n_obs_lote": n_obs_lote})


@login_required
def reprocesar_lote_conc(request, lote_id):
    """Reprocesa TODOS los ítems del lote en orden (respetando confirmaciones manuales)."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    if request.method == "POST" and lote.estado != LoteConciliacion.PROCESANDO:
        n = 0
        for it in lote.items.select_related("comprobante").order_by("id"):
            # No tocar los confirmados manualmente ("Añadir y Confirmar").
            if (it.resultado == Conciliacion.OK and it.comprobante
                    and it.comprobante.origen == Comprobante.ORIGEN_MANUAL):
                continue
            emparejar_item(it, lote)
            n += 1
        _recontar_lote(lote)
        messages.success(request, f"Conciliación reprocesada ({n} ítem(s)).")
    return _volver_detalle(lote.id, r)


@login_required
def lote_progreso(request, lote_id):
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    return JsonResponse({
        "estado": lote.estado,
        "estado_display": lote.get_estado_display(),
        "progreso": lote.progreso_pct,
        "procesadas": lote.procesadas,
        "total": lote.total,
        "ok": lote.ok,
        "pendientes": lote.pendientes,
        "no_esta": lote.no_esta,
        "revision": lote.revision,
        "duplicados": lote.duplicados,
        "pausado": lote.estado == LoteConciliacion.PAUSADO,
        "terminado": lote.terminado,
    })


@login_required
def pausar_conciliacion(request, lote_id):
    """Marca la conciliación como pausada; la tarea se detiene en la siguiente imagen."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    if request.method == "POST" and lote.estado in (LoteConciliacion.PROCESANDO, LoteConciliacion.EN_COLA):
        lote.estado = LoteConciliacion.PAUSADO
        lote.save(update_fields=["estado"])
        messages.success(request, f"Conciliación #{lote.id} pausada.")
    return redirect("conciliaciones:lote_detalle", lote_id=lote.id)


@login_required
def reanudar_conciliacion(request, lote_id):
    """Reanuda una conciliación pausada: vuelve a encolar lo pendiente."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    if request.method == "POST" and lote.estado == LoteConciliacion.PAUSADO:
        pendientes = lote.items.filter(resultado__isnull=True).count()
        if pendientes:
            procesar_conciliacion.delay(lote.id)
            messages.success(request, f"Reanudando conciliación #{lote.id} ({pendientes} pendiente(s)).")
        else:
            lote.estado = LoteConciliacion.COMPLETADO
            lote.save(update_fields=["estado"])
            messages.info(request, "No quedan imágenes pendientes en esa conciliación.")
    return redirect("conciliaciones:lote_detalle", lote_id=lote.id)


@login_required
def eliminar_lote(request, lote_id):
    """Borra una conciliación completa y revierte todo lo que confirmó:
    - Ítems OK cuyo comprobante fue creado manualmente para esta conciliación
      (origen=MANUAL, vía "Añadir y confirmar") → se borra el comprobante entero.
    - Ítems OK sobre un comprobante ya existente → se revierte a "sin confirmar"
      y se le quita la ruta asignada (no se toca su origen ni sus datos).
    Los ítems Duplicado no se tocan: no confirmaron ni reasignaron nada.
    """
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteConciliacion, pk=lote_id, negocio=negocio)
    if request.method == "POST":
        items_ok = (lote.items.filter(resultado=Conciliacion.OK, comprobante__isnull=False)
                    .select_related("comprobante"))
        n_revertidos = n_borrados = 0
        for item in items_ok:
            comp = item.comprobante
            if comp.origen == Comprobante.ORIGEN_MANUAL:
                comp.delete()
                n_borrados += 1
            else:
                comp.estado = Comprobante.SIN_CONFIRMAR
                comp.ruta = None
                comp.save(update_fields=["estado", "ruta"])
                n_revertidos += 1
        lote.delete()  # cascada de Conciliacion + sus imágenes (señal post_delete)
        messages.success(
            request,
            f"Conciliación #{lote_id} eliminada. {n_revertidos} comprobante(s) revertido(s) a "
            f"sin confirmar y {n_borrados} comprobante(s) manual(es) eliminado(s)."
        )
    return redirect("conciliaciones:lista")


def _aplicar_campos_post(item, request):
    """Vuelca los campos editables del formulario de ajuste en el item (sin guardar)."""
    from core.parsing import limpiar_monto, parse_fecha, parse_hora

    item.de = request.POST.get("de", item.de)
    item.para = request.POST.get("para", item.para).strip()
    item.num = request.POST.get("num", item.num).strip()
    item.tipo = (request.POST.get("tipo", item.tipo) or "").strip().lower()
    item.ref = request.POST.get("ref", item.ref).strip()
    valor_in = request.POST.get("valor", "")
    item.valor_raw = valor_in
    item.valor = limpiar_monto(valor_in) or 0
    item.fecha = request.POST.get("fecha", item.fecha)
    item.fecha_dt = parse_fecha(item.fecha)
    hora_in = request.POST.get("hora", item.hora)
    t = parse_hora(hora_in)
    item.hora = t.strftime("%H:%M") if t else hora_in
    item.observaciones = request.POST.get("observaciones", item.observaciones).strip()


@login_required
def ajustar_item(request, pk):
    """Edita manualmente los datos leídos de una conciliación (ref/valor/fecha/hora)."""
    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    if request.method == "POST":
        r = request.POST.get("r", "").strip()
        sort = request.POST.get("sort", "").strip()
        _aplicar_campos_post(item, request)
        item.save()
        messages.success(request, "Datos ajustados. Pulsa «Reprocesar» para volver a buscar.")
        return _volver_detalle(item.lote_id, r, sort)
    return render(request, "conciliaciones/ajustar.html",
                  {"item": item, "tipos": Conciliacion.TIPOS,
                   "filtro_r": request.GET.get("r", "").strip(),
                   "sort": request.GET.get("sort", "").strip()})


@login_required
def agregar_confirmar(request, pk):
    """Crea un Comprobante a partir de un ítem 'No está' y lo confirma directamente.

    Útil cuando el voucher/comprobante es válido pero no existe en los registrados:
    se añade a los comprobantes normales (confirmado, con la ruta de la conciliación).
    """
    import os
    from django.core.files import File

    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    if request.method != "POST":
        return _volver_detalle(item.lote_id, r, sort)

    # Aplicar las correcciones del formulario y guardarlas en el ítem.
    _aplicar_campos_post(item, request)

    # Duplicado por referencia: si ya existe un original con esa ref, marcarlo como tal
    # para no romper la restricción única (negocio, ref).
    ref = (item.ref or "").strip()
    original = None
    if ref and ref != "No encontrada":
        original = Comprobante.objects.filter(
            negocio=negocio, ref=ref, es_duplicado=False
        ).order_by("creado_en", "id").first()

    comp = Comprobante(
        negocio=negocio, creado_por=request.user,
        de=item.de or "No encontrada", valor=item.valor or 0, valor_raw=item.valor_raw,
        fecha=item.fecha, hora=item.hora, ref=ref,
        origen=Comprobante.ORIGEN_MANUAL,
        estado=Comprobante.CONFIRMADO, ruta=item.lote.ruta,
        es_duplicado=original is not None, duplicado_de=original,
    )
    # Copiar la imagen del ítem al comprobante (archivo independiente).
    if item.imagen:
        with item.imagen.open("rb") as fh:
            comp.imagen.save(os.path.basename(item.imagen.name), File(fh), save=False)
    comp.save()

    # Enlazar el ítem y marcarlo OK.
    item.comprobante = comp
    item.resultado = Conciliacion.OK
    item.aviso = ""
    item.motivo_revision = ""
    item.save()
    _recontar_lote(item.lote)
    messages.success(request, f"Comprobante creado (#{comp.id}) y confirmado en la ruta.")
    return _volver_detalle(item.lote_id, r, sort)


@login_required
def eliminar_item(request, pk):
    """Elimina un ítem de la conciliación (y su imagen). Recalcula los contadores."""
    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    lote = item.lote
    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    if request.method == "POST":
        item.delete()  # dispara la señal que borra la imagen del disco
        lote.total = lote.items.count()
        lote.procesadas = lote.items.exclude(resultado__isnull=True).count()
        lote.save(update_fields=["total", "procesadas"])
        _recontar_lote(lote)
        messages.success(request, "Registro eliminado de la conciliación.")
    return _volver_detalle(lote.id, r, sort)


@login_required
def eliminar_items_masivo(request):
    """Elimina en masa varios ítems de conciliación (checkboxes).

    Se usa desde el detalle de un lote (todos los ítems son del mismo lote)
    y desde el panel global (los ítems pueden pertenecer a lotes distintos):
    recalcula los contadores de CADA lote afectado.
    """
    negocio = get_negocio(request.user)
    if not negocio or request.method != "POST":
        return redirect("conciliaciones:panel")

    ids = [i for i in request.POST.getlist("seleccion") if i.isdigit()]
    items = Conciliacion.objects.filter(negocio=negocio, id__in=ids)
    lote_ids = list(items.values_list("lote_id", flat=True).distinct())
    n = items.count()
    items.delete()  # dispara, por instancia, la señal que borra cada imagen

    for lote in LoteConciliacion.objects.filter(pk__in=lote_ids):
        lote.total = lote.items.count()
        lote.procesadas = lote.items.exclude(resultado__isnull=True).count()
        lote.save(update_fields=["total", "procesadas"])
        _recontar_lote(lote)

    if n:
        messages.success(request, f"{n} registro(s) eliminado(s) de la conciliación.")
    else:
        messages.info(request, "No se seleccionó ningún registro.")

    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    volver_lote = request.POST.get("volver_lote", "").strip()
    if volver_lote.isdigit():
        return _volver_detalle(int(volver_lote), r, sort)

    # Volver al panel global preservando los filtros activos.
    params = []
    for key in ("r", "desde", "hasta", "tam", "sort", "page"):
        val = request.POST.get(key, "").strip()
        if val:
            params.append(f"{key}={val}")
    url = reverse("conciliaciones:panel")
    if params:
        url += "?" + "&".join(params)
    return redirect(url)


@login_required
def guardar_observacion(request, pk):
    """Guarda (o borra, si llega vacía) la observación de un ítem de conciliación."""
    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    if request.method == "POST":
        item.observaciones = request.POST.get("observaciones", "").strip()
        item.save(update_fields=["observaciones"])
        messages.success(request, "Observación guardada." if item.observaciones else "Observación eliminada.")
    return _volver_detalle(item.lote_id, r, sort)


@login_required
def reprocesar_item(request, pk):
    """Vuelve a buscar el comprobante con los datos actuales del ítem (sin IA)."""
    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    r = request.POST.get("r", "").strip()
    sort = request.POST.get("sort", "").strip()
    if request.method == "POST":
        resultado = emparejar_item(item, item.lote)
        _recontar_lote(item.lote)
        etiquetas = {"ok": "OK", "pendiente": "Pendiente", "no_esta": "No está",
                     "revision": "Revisión manual", "duplicado": "Duplicado"}
        messages.success(request, f"Reprocesado: {etiquetas.get(resultado, resultado)}.")
    return _volver_detalle(item.lote_id, r, sort)


@login_required
def confirmar_pendiente(request, pk):
    """Confirma manualmente un comprobante de una conciliación 'Pendiente'."""
    negocio = get_negocio(request.user)
    item = get_object_or_404(Conciliacion, pk=pk, negocio=negocio)
    if request.method == "POST" and item.resultado == Conciliacion.PENDIENTE and item.comprobante:
        comp = item.comprobante
        comp.estado = Comprobante.CONFIRMADO
        comp.ruta = item.ruta
        comp.save()
        item.resultado = Conciliacion.OK
        item.save(update_fields=["resultado"])
        # Actualizar contadores del lote.
        LoteConciliacion.objects.filter(pk=item.lote_id).update(
            ok=item.lote.ok + 1, pendientes=max(item.lote.pendientes - 1, 0)
        )
        messages.success(request, "Comprobante confirmado y asignado a la ruta.")
    return _volver_detalle(item.lote_id, request.POST.get("r", "").strip(),
                           request.POST.get("sort", "").strip())
