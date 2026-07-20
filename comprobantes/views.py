from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import get_negocio
from core.downloads import nombre_descarga

from django.db.models import Count, Q

from .models import ArchivoPendiente, Comprobante, LoteCarga, Notificacion, Ruta
from .tasks import procesar_lote, reprocesar_lote

# Tamaños de página permitidos en la lista de comprobantes.
TAM_PAGINA = {"20", "50", "100", "200"}


def _recontar_lote_carga(lote):
    """Recalcula exitosas/duplicadas según los comprobantes que siguen vivos.

    total/procesadas/fallidas reflejan el resultado histórico del procesamiento
    (imágenes subidas, no comprobantes actuales) y no se tocan aquí; exitosas y
    duplicadas sí mapean 1:1 a comprobantes vivos, así que quedan desactualizadas
    si el usuario borra alguno después (p. ej. al depurar duplicados a mano).
    """
    lote.exitosas = lote.comprobantes.filter(es_duplicado=False).count()
    lote.duplicadas = lote.comprobantes.filter(es_duplicado=True).count()
    lote.save(update_fields=["exitosas", "duplicadas"])


def _excel_comprobantes(qs, filename="comprobantes.xlsx"):
    """Genera una respuesta Excel a partir de un queryset de comprobantes."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Comprobantes"
    ws.append(["Remitente", "Valor", "Referencia", "Fecha", "Hora", "Ruta", "Estado"])
    for c in qs:
        ws.append([
            c.de, float(c.valor), c.ref, c.fecha, c.hora,
            c.ruta.numero if c.ruta else "", c.get_estado_display(),
        ])
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"
    wb.save(response)
    return response


@login_required
def subir(request):
    """Subida masiva: guarda las imágenes, crea un lote y lo encola."""
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    if request.method == "POST":
        archivos = request.FILES.getlist("imagenes")
        if not archivos:
            messages.error(request, "Selecciona al menos una imagen.")
            return redirect("comprobantes:subir")

        from django.db import transaction
        with transaction.atomic():
            lote = LoteCarga.objects.create(
                negocio=negocio, creado_por=request.user, total=len(archivos)
            )
            # Solo se guarda la imagen pendiente; el comprobante se crea tras analizar.
            for f in archivos:
                ArchivoPendiente.objects.create(lote=lote, imagen=f)
        procesar_lote.delay(lote.id)
        messages.success(request, f"Lote #{lote.id} en proceso ({len(archivos)} imágenes).")
        return redirect("comprobantes:lote_detalle", lote_id=lote.id)

    return render(request, "comprobantes/subir.html", {"negocio": negocio})


@login_required
def lote_detalle(request, lote_id):
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    return render(request, "comprobantes/lote_detalle.html", {
        "lote": lote, "comprobantes": lote.comprobantes.all(),
        "fallidos": lote.archivos.filter(fallido=True).order_by("id"),
    })


@login_required
def descargar_imagenes_lote(request, lote_id):
    """Descarga en un .zip todas las imágenes de los comprobantes de una subida."""
    import io
    import os
    import zipfile

    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for comp in lote.comprobantes.exclude(imagen=""):
            nombre = f"{comp.id}_{os.path.basename(comp.imagen.name)}"
            with comp.imagen.open("rb") as fh:
                zf.writestr(nombre, fh.read())

    nombre = nombre_descarga("imagenes", [f"subida-{lote_id}"], ext="zip")
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f"attachment; filename={nombre}"
    return response


@login_required
def lote_progreso(request, lote_id):
    """Endpoint JSON para la barra de progreso (polling)."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    ultimos = [
        {"id": c.id, "de": c.de, "valor": float(c.valor), "ref": c.ref, "dup": c.es_duplicado}
        for c in lote.comprobantes.order_by("-id")[:20]
    ]
    return JsonResponse({
        "estado": lote.estado,
        "estado_display": lote.get_estado_display(),
        "progreso": lote.progreso_pct,
        "procesadas": lote.procesadas,
        "total": lote.total,
        "exitosas": lote.exitosas,
        "duplicadas": lote.duplicadas,
        "fallidas": lote.fallidas,
        "pausado": lote.estado == LoteCarga.PAUSADO,
        "terminado": lote.estado in (LoteCarga.COMPLETADO, LoteCarga.CON_ERRORES),
        "ultimos": ultimos,
    })


@login_required
def pausar_lote(request, lote_id):
    """Marca el lote como pausado; la tarea se detiene en la siguiente imagen."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    if request.method == "POST" and lote.estado in (LoteCarga.PROCESANDO, LoteCarga.EN_COLA):
        lote.estado = LoteCarga.PAUSADO
        lote.save(update_fields=["estado"])
        messages.success(request, f"Lote #{lote.id} pausado.")
    return redirect("comprobantes:lote_detalle", lote_id=lote.id)


@login_required
def reanudar_lote(request, lote_id):
    """Reanuda un lote pausado: vuelve a encolar el procesamiento de lo pendiente."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    if request.method == "POST" and lote.estado == LoteCarga.PAUSADO:
        pendientes = lote.archivos.filter(fallido=False).count()
        if pendientes:
            procesar_lote.delay(lote.id)
            messages.success(request, f"Reanudando lote #{lote.id} ({pendientes} pendiente(s)).")
        else:
            lote.estado = LoteCarga.COMPLETADO if lote.fallidas == 0 else LoteCarga.CON_ERRORES
            lote.save(update_fields=["estado"])
            messages.info(request, "No quedan imágenes pendientes en ese lote.")
    return redirect("comprobantes:lote_detalle", lote_id=lote.id)


def _filtrar_comprobantes(request, negocio):
    """Aplica los filtros (q/día/dup/lote/estado) y devuelve (queryset, contexto).

    Compartido por la lista paginada y la exportación a Excel para que ambos
    respeten exactamente los mismos filtros.
    """
    import datetime

    from core.parsing import limpiar_monto

    qs = Comprobante.objects.filter(negocio=negocio) if negocio else Comprobante.objects.none()

    q = request.GET.get("q", "").strip()
    if q:
        # "#727" (o "#"+id) busca por ID exacto del comprobante.
        if q.startswith("#") and q[1:].strip().isdigit():
            qs = qs.filter(pk=int(q[1:].strip()))
        else:
            filtro = Q(de__icontains=q) | Q(ref__icontains=q)
            # Si "q" parece un monto ("30000", "$30.000", "30,000"), buscar
            # también por valor exacto (tolerante a separadores de miles/decimales).
            monto_q = limpiar_monto(q)
            if monto_q:
                filtro |= Q(valor=monto_q)
            qs = qs.filter(filtro)

    # Filtro por día (usa la fecha parseada fecha_dt).
    dia = request.GET.get("dia", "").strip()
    dia_obj = None
    if dia:
        qs = qs.filter(fecha_dt=dia)
        try:
            dia_obj = datetime.datetime.strptime(dia, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Filtro por hora exacta (24h "HH:MM"; la hora está normalizada en ese formato).
    hora = request.GET.get("hora", "").strip()
    if hora:
        qs = qs.filter(hora=hora)

    # Filtro por duplicados: "1" = solo duplicados, "0" = solo originales.
    dup = request.GET.get("dup", "").strip()
    if dup == "1":
        qs = qs.filter(es_duplicado=True)
    elif dup == "0":
        qs = qs.filter(es_duplicado=False)

    # Filtro por estado: confirmado / sin confirmar.
    estado = request.GET.get("estado", "").strip()
    if estado in (Comprobante.CONFIRMADO, Comprobante.SIN_CONFIRMAR):
        qs = qs.filter(estado=estado)

    # Filtro por lote/subida (los comprobantes creados en esa misma subida).
    lote = request.GET.get("lote", "").strip()
    lote_obj = None
    if lote.isdigit():
        qs = qs.filter(lote_id=lote)
        lote_obj = LoteCarga.objects.filter(pk=lote, negocio=negocio).first()

    ctx = {"q": q, "dia": dia, "dia_obj": dia_obj, "hora": hora,
           "dup": dup, "estado": estado, "lote": lote, "lote_obj": lote_obj}
    return qs, ctx


# Campos por los que se puede ordenar la tabla (nombre → expresión de orden).
SORT_FIELDS = {"de", "valor", "ref", "fecha_dt", "hora", "origen", "estado"}


@login_required
def lista(request):
    from django.db.models import Sum

    negocio = get_negocio(request.user)
    qs, ctx = _filtrar_comprobantes(request, negocio)

    # Totales de TODO lo filtrado (no solo la página actual).
    resumen = qs.aggregate(n=Count("id"), total=Sum("valor"))

    n_duplicados = (Comprobante.objects.filter(negocio=negocio, es_duplicado=True).count()
                    if negocio else 0)

    # Anotar nº de duplicados SOLO en la página (no en el qs del agregado, para
    # no alterar la suma con el GROUP BY).
    pagina_qs = qs.select_related("ruta").annotate(n_dups=Count("duplicados"))

    # Ordenamiento por columna (?sort=campo o -campo). Tiene prioridad sobre lo demás.
    sort = request.GET.get("sort", "").strip()
    base = sort[1:] if sort.startswith("-") else sort
    if base in SORT_FIELDS:
        orden = [sort]
        if base == "fecha_dt":  # desempate por hora
            orden.append("-hora" if sort.startswith("-") else "hora")
        pagina_qs = pagina_qs.order_by(*orden)
    elif ctx["q"]:
        # Al buscar por referencia (etiqueta de duplicado), original primero y luego duplicados.
        pagina_qs = pagina_qs.order_by("es_duplicado", "creado_en", "id")
        sort = ""
    else:
        pagina_qs = pagina_qs.order_by("-creado_en", "-id")
        sort = ""

    tam = request.GET.get("tam", "").strip()
    if tam not in TAM_PAGINA:
        tam = "20"
    paginator = Paginator(pagina_qs, int(tam))
    page = paginator.get_page(request.GET.get("page"))

    # Para los confirmados, enlazar la conciliación (OK) que los confirmó.
    from conciliaciones.models import Conciliacion
    ids = [c.pk for c in page.object_list]
    mapa_conc = {}
    for co in (Conciliacion.objects.filter(comprobante_id__in=ids, resultado=Conciliacion.OK)
               .select_related("lote", "lote__ruta").order_by("creado_en")):
        mapa_conc.setdefault(co.comprobante_id, co)
    for c in page.object_list:
        c.conciliacion = mapa_conc.get(c.pk)

    rutas = Ruta.objects.filter(negocio=negocio, activa=True) if negocio else Ruta.objects.none()
    return render(request, "comprobantes/lista.html",
                  {"page": page, "rutas": rutas, "n_duplicados": n_duplicados, "sort": sort, "tam": tam,
                   "total_count": resumen["n"], "total_valor": resumen["total"] or 0, **ctx})


@login_required
def exportar_lista(request):
    """Exporta a Excel los comprobantes según filtros + rango de fechas y ruta.

    Reusa los filtros de la lista (q/día/dup/lote) y añade los del modal de
    exportación: ``desde``/``hasta`` (rango sobre fecha_dt) y ``ruta``.
    """
    negocio = get_negocio(request.user)
    qs, _ = _filtrar_comprobantes(request, negocio)

    desde = request.GET.get("desde", "").strip()
    hasta = request.GET.get("hasta", "").strip()
    if desde:
        qs = qs.filter(fecha_dt__gte=desde)
    if hasta:
        qs = qs.filter(fecha_dt__lte=hasta)

    # Ruta: admite varias (?ruta=1&ruta=2) y/o "sin" para los no asignados.
    rutas_sel = request.GET.getlist("ruta")
    ids = [r for r in rutas_sel if r.isdigit()]
    incluir_sin = "sin" in rutas_sel
    if ids or incluir_sin:
        from django.db.models import Q
        cond = Q()
        if ids:
            cond |= Q(ruta_id__in=ids)
        if incluir_sin:
            cond |= Q(ruta__isnull=True)
        qs = qs.filter(cond)

    # Nombre distintivo según los filtros aplicados.
    lote = request.GET.get("lote", "").strip()
    extra = []
    if lote.isdigit():
        extra.append(f"subida-{lote}")
    if desde or hasta:
        extra.append(f"{desde or 'inicio'}_a_{hasta or 'hoy'}")
    nombre = nombre_descarga("comprobantes", extra)
    return _excel_comprobantes(qs.select_related("ruta"), nombre)


@login_required
def importar_excel(request):
    """Importa comprobantes desde un .xlsx (mismas columnas que la exportación).

    Columnas esperadas (con encabezado en la 1ª fila):
    Remitente · Valor · Referencia · Fecha · Hora · Ruta · Estado
    """
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    if request.method == "POST":
        import openpyxl
        from core.parsing import limpiar_monto

        archivo = request.FILES.get("archivo")
        if not archivo:
            messages.error(request, "Selecciona un archivo .xlsx.")
            return redirect("comprobantes:importar")
        if not archivo.name.lower().endswith((".xlsx", ".xlsm")):
            messages.error(request, "El archivo debe ser un Excel (.xlsx).")
            return redirect("comprobantes:importar")

        try:
            wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
        except Exception as e:
            messages.error(request, f"No se pudo leer el Excel: {e}")
            return redirect("comprobantes:importar")

        ws = wb.active
        creados = duplicados = vacios = 0
        rutas_cache = {}

        for i, fila in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # encabezado
            if not fila or all(c in (None, "") for c in fila):
                continue
            # Rellenar a 7 columnas para evitar IndexError en filas cortas.
            celdas = list(fila) + [None] * (7 - len(fila))
            de, valor, ref, fecha, hora, ruta_num, estado = celdas[:7]

            de = (str(de).strip() if de is not None else "") or "No encontrada"
            ref = str(ref).strip() if ref is not None else ""
            if not de and not ref and not valor:
                vacios += 1
                continue

            # Valor: puede venir numérico (export) o como texto ("$1.000").
            valor_raw = "" if valor is None else str(valor)
            monto = valor if isinstance(valor, (int, float)) else limpiar_monto(valor_raw)

            # Duplicado por (negocio, ref).
            if ref and ref != "No encontrada" and Comprobante.objects.filter(
                negocio=negocio, ref=ref
            ).exists():
                duplicados += 1
                continue

            # Ruta opcional por número.
            ruta = None
            if ruta_num not in (None, ""):
                try:
                    num = int(ruta_num)
                    if num not in rutas_cache:
                        rutas_cache[num] = Ruta.objects.filter(negocio=negocio, numero=num).first()
                    ruta = rutas_cache[num]
                except (TypeError, ValueError):
                    ruta = None

            confirmado = str(estado).strip().lower().startswith("conf") if estado else False

            Comprobante.objects.create(
                negocio=negocio, creado_por=request.user,
                de=de, valor=monto or 0, valor_raw=valor_raw,
                fecha=str(fecha).strip() if fecha is not None else "",
                hora=str(hora).strip() if hora is not None else "",
                ref=ref, ruta=ruta,
                origen=Comprobante.ORIGEN_WEB,
                estado=Comprobante.CONFIRMADO if confirmado else Comprobante.SIN_CONFIRMAR,
            )
            creados += 1

        wb.close()
        messages.success(
            request,
            f"Importación lista: {creados} creado(s), {duplicados} duplicado(s) omitido(s)"
            + (f", {vacios} fila(s) vacía(s)." if vacios else "."),
        )
        return redirect("comprobantes:lista")

    return render(request, "comprobantes/importar.html", {"negocio": negocio})


@login_required
def acciones_lote(request):
    """Aplica una acción (confirmar/asignar ruta/eliminar/exportar) a los seleccionados."""
    negocio = get_negocio(request.user)
    if request.method != "POST":
        return redirect("comprobantes:lista")

    ids = request.POST.getlist("seleccion")
    qs = Comprobante.objects.filter(negocio=negocio, pk__in=ids)
    if not ids:
        messages.error(request, "Selecciona al menos un comprobante.")
        return redirect("comprobantes:lista")

    accion = request.POST.get("accion")

    if accion == "confirmar":
        n = qs.update(estado=Comprobante.CONFIRMADO)
        messages.success(request, f"{n} comprobante(s) confirmado(s).")

    elif accion == "asignar_ruta":
        ruta = Ruta.objects.filter(negocio=negocio, pk=request.POST.get("ruta")).first()
        if not ruta:
            messages.error(request, "Elige una ruta válida.")
        else:
            n = qs.update(ruta=ruta)
            messages.success(request, f"Ruta {ruta.numero} asignada a {n} comprobante(s).")

    elif accion == "eliminar":
        n = qs.count()
        lote_ids = list(qs.exclude(lote__isnull=True).values_list("lote_id", flat=True).distinct())
        qs.delete()  # dispara la señal que borra las imágenes
        for lote in LoteCarga.objects.filter(pk__in=lote_ids):
            _recontar_lote_carga(lote)
        messages.success(request, f"{n} comprobante(s) eliminado(s).")

    elif accion == "exportar":
        nombre = nombre_descarga("comprobantes", ["seleccion"])
        return _excel_comprobantes(qs, nombre)

    return redirect("comprobantes:lista")


@login_required
def editar(request, pk):
    negocio = get_negocio(request.user)
    comp = get_object_or_404(Comprobante, pk=pk, negocio=negocio)
    if request.method == "POST":
        from core.parsing import limpiar_monto

        valor_in = request.POST.get("valor", "")
        comp.de = request.POST.get("de", comp.de)
        comp.valor = limpiar_monto(valor_in) or 0
        comp.valor_raw = valor_in
        comp.ref = request.POST.get("ref", comp.ref)
        comp.fecha = request.POST.get("fecha", comp.fecha)
        comp.hora = request.POST.get("hora", comp.hora)
        comp.estado = Comprobante.CONFIRMADO
        comp.save()
        messages.success(request, "Comprobante actualizado.")
        return redirect("comprobantes:lista")
    return render(request, "comprobantes/editar.html", {"comp": comp})


@login_required
def eliminar(request, pk):
    negocio = get_negocio(request.user)
    comp = get_object_or_404(Comprobante, pk=pk, negocio=negocio)
    lote = comp.lote
    if request.method == "POST":
        comp.delete()
        if lote:
            _recontar_lote_carga(lote)
        messages.success(request, "Comprobante eliminado.")
    return redirect("comprobantes:lista")


@login_required
def notificaciones(request):
    notifs = Notificacion.objects.filter(usuario=request.user)[:50]
    Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    return render(request, "comprobantes/notificaciones.html", {"notifs": notifs})


@login_required
def lotes(request):
    """Historial de subidas (lotes de carga)."""
    negocio = get_negocio(request.user)
    qs = LoteCarga.objects.filter(negocio=negocio) if negocio else LoteCarga.objects.none()
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "comprobantes/lotes.html", {"page": page})


@login_required
def en_proceso(request):
    """Subidas activas (en cola o procesándose), con progreso en vivo."""
    negocio = get_negocio(request.user)
    lotes_activos = (
        LoteCarga.objects.filter(
            negocio=negocio, estado__in=[LoteCarga.EN_COLA, LoteCarga.PROCESANDO]
        )
        if negocio
        else LoteCarga.objects.none()
    )
    return render(request, "comprobantes/en_proceso.html", {"lotes": lotes_activos})


@login_required
def eliminar_lote(request, lote_id):
    """Borra una subida completa: el lote, sus comprobantes e imágenes."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    if request.method == "POST":
        # Borrar comprobantes primero (la FK es SET_NULL); las señales borran imágenes.
        n = lote.comprobantes.count()
        lote.comprobantes.all().delete()
        lote.delete()  # cascada de ArchivoPendiente + sus imágenes
        messages.success(request, f"Subida #{lote_id} eliminada ({n} comprobante(s)).")
    return redirect("comprobantes:lotes")


@login_required
def reprocesar(request, lote_id):
    """Reintenta las imágenes fallidas de un lote en segundo plano."""
    negocio = get_negocio(request.user)
    lote = get_object_or_404(LoteCarga, pk=lote_id, negocio=negocio)
    if request.method == "POST":
        pendientes = lote.archivos.filter(fallido=True).count()
        if pendientes:
            reprocesar_lote.delay(lote.id)
            messages.success(request, f"Reprocesando {pendientes} imagen(es) del lote #{lote.id}.")
        else:
            messages.info(request, "Ese lote no tiene imágenes fallidas para reprocesar.")
    return redirect("comprobantes:lote_detalle", lote_id=lote.id)


@login_required
def rutas(request):
    """Lista y creación de rutas del negocio."""
    negocio = get_negocio(request.user)
    if not negocio:
        messages.error(request, "Tu usuario no tiene un negocio asignado.")
        return redirect("dashboard:home")

    if request.method == "POST":
        numero = request.POST.get("numero", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        if not numero.isdigit():
            messages.error(request, "El número de ruta debe ser un entero.")
        elif Ruta.objects.filter(negocio=negocio, numero=numero).exists():
            messages.error(request, f"Ya existe la ruta {numero}.")
        else:
            Ruta.objects.create(negocio=negocio, numero=int(numero), nombre=nombre)
            messages.success(request, f"Ruta {numero} creada.")
        return redirect("comprobantes:rutas")

    lista_rutas = (Ruta.objects.filter(negocio=negocio)
                   .annotate(n_comprobantes=Count("comprobantes")))
    return render(request, "comprobantes/rutas.html", {"rutas": lista_rutas})


@login_required
def ruta_toggle(request, pk):
    """Activa/desactiva una ruta."""
    negocio = get_negocio(request.user)
    ruta = get_object_or_404(Ruta, pk=pk, negocio=negocio)
    if request.method == "POST":
        ruta.activa = not ruta.activa
        ruta.save(update_fields=["activa"])
        messages.success(request, f"Ruta {ruta.numero} {'activada' if ruta.activa else 'desactivada'}.")
    return redirect("comprobantes:rutas")
