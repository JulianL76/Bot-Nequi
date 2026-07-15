import datetime
from collections import OrderedDict
import random

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.utils import get_negocio
from comprobantes.models import Comprobante
from conciliaciones.models import Conciliacion
from core.downloads import nombre_descarga


def get_greeting(request):
    user = request.user
    hour = timezone.localtime().hour
    name = user.first_name or user.username
    
    # Check if we should use the cached greeting
    if 5 <= hour < 12:
        time_block = "manana"
    elif 12 <= hour < 19:
        time_block = "tarde"
    elif 19 <= hour < 23:
        time_block = "noche"
    elif hour >= 23 or hour < 3:
        time_block = "trasnoche"
    else:
        time_block = "madrugada"
        
    session_block = request.session.get("saludo_time_block")
    session_saludo = request.session.get("saludo_actual")
    if session_block == time_block and session_saludo:
        return session_saludo
    
    # Check for romantic mode
    es_especial = False
    if hasattr(user, 'perfil') and user.perfil.es_especial:
        es_especial = True

    if es_especial:
        opciones = [
            f"¡Qué linda te ves hoy, {name}! 🥰",
            f"Te extrañaba por aquí ❤️",
            f"Haces que las cuentas se vean mejor, {name} ✨",
        ]
        if 5 <= hour < 12:
            opciones.append(f"Buenos días, preciosa ☀️")
            opciones.append(f"¡A comerse el mundo hoy, mi amor! 🌅")
        elif 12 <= hour < 19:
            opciones.append(f"Buenas tardes, mi vida 🌤️")
            opciones.append(f"¿Cómo va tu tarde, pastelito? 😋")
        elif 19 <= hour < 23:
            opciones.append(f"Buenas noches, amor 🌙")
            opciones.append(f"Que descanses muy rico, cosita hermosa 💤")
        elif hour >= 23 or hour < 3:
            opciones = [
                f"¿Trasnochando, mi amor? 🥺",
                f"Ve a dormir pronto, mi solecito 💖",
                f"A descansar que es tarde, corazón 😴"
            ]
        else:
            opciones = [
                f"¿Despierta tan temprano, amor? ❤️",
                f"¡Qué madrugadora, preciosa! 🌅"
            ]
        saludo_final = random.choice(opciones)
        request.session["saludo_time_block"] = time_block
        request.session["saludo_actual"] = saludo_final
        return saludo_final

    # Normal mode
    opciones = [
        f"¡Qué bueno verte por aquí, {name}! 👋",
        f"¿Listo para organizar el negocio, {name}? 🚀",
        f"Todo bajo control, {name} ✨",
    ]
    
    if 5 <= hour < 12:
        opciones.append(f"Buenos días, {name} ☀️")
        opciones.append(f"¡A por un excelente día, {name}! 🌅")
    elif 12 <= hour < 19:
        opciones.append(f"Buenas tardes, {name} 🌤️")
        opciones.append(f"¿Cómo va la tarde, {name}? ☕")
    elif 19 <= hour < 23:
        opciones.append(f"Buenas noches, {name} 🌙")
        opciones.append(f"Buen momento para hacer cierre, {name} 📊")
    elif hour >= 23 or hour < 3:
        opciones = [
            f"¿Trasnochando, {name}? 🦉",
            f"Aún trabajando a esta hora, ¿eh, {name}? 🦇",
            f"Las mejores cuentas se hacen de noche, {name} 💡"
        ]
    else:
        opciones = [
            f"¿Madrugando, {name}? ☕",
            f"¡Al que madruga Dios lo ayuda, {name}! 🐓"
        ]
        
    saludo_final = random.choice(opciones)
    request.session["saludo_time_block"] = time_block
    request.session["saludo_actual"] = saludo_final
    return saludo_final


def _qs_negocio(request):
    negocio = get_negocio(request.user)
    if not negocio:
        return Comprobante.objects.none(), None
    return Comprobante.objects.filter(negocio=negocio), negocio


@login_required
def home(request):
    qs, negocio = _qs_negocio(request)

    fecha_str = request.GET.get('fecha', '')
    if fecha_str == 'all':
        fecha_filtro = None
    elif fecha_str:
        try:
            fecha_filtro = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            fecha_filtro = datetime.date.today()
    else:
        fecha_filtro = datetime.date.today()

    qs_kpi = qs
    if fecha_filtro:
        qs_kpi = qs.filter(creado_en__date=fecha_filtro)

    total_facturas = qs_kpi.count()
    total_monto = qs_kpi.aggregate(s=Sum("valor"))["s"] or 0

    # Serie de los últimos 14 días para la gráfica.
    desde = datetime.date.today() - datetime.timedelta(days=13)
    por_dia = (
        qs.filter(creado_en__date__gte=desde)
        .annotate(dia=TruncDate("creado_en"))
        .values("dia")
        .annotate(total=Sum("valor"), n=Count("id"))
        .order_by("dia")
    )
    serie = OrderedDict()
    for i in range(14):
        d = desde + datetime.timedelta(days=i)
        serie[d.isoformat()] = 0
    for row in por_dia:
        serie[row["dia"].isoformat()] = float(row["total"] or 0)

    top_contactos = (
        qs.values("de")
        .annotate(total=Sum("valor"), n=Count("id"))
        .order_by("-total")[:5]
    )

    sin_confirmar = qs_kpi.filter(estado=Comprobante.SIN_CONFIRMAR).count()
    monto_sin_confirmar = qs_kpi.filter(estado=Comprobante.SIN_CONFIRMAR).aggregate(s=Sum("valor"))["s"] or 0
    concils = Conciliacion.objects.filter(negocio=negocio, resultado=Conciliacion.PENDIENTE) if negocio else Conciliacion.objects.none()
    if fecha_filtro:
        concils = concils.filter(creado_en__date=fecha_filtro)
    concil_pendientes = concils.count()

    contexto = {
        "negocio": negocio,
        "fecha_filtro": fecha_filtro,
        "total_facturas": total_facturas,
        "total_monto": total_monto,
        "chart_labels": list(serie.keys()),
        "chart_values": list(serie.values()),
        "top_contactos": top_contactos,
        "ultimos": qs.select_related("negocio")[:8],
        "sin_confirmar": sin_confirmar,
        "monto_sin_confirmar": monto_sin_confirmar,
        "concil_pendientes": concil_pendientes,
        "saludo": get_greeting(request),
    }
    return render(request, "dashboard/home.html", contexto)


@login_required
def pendientes(request):
    """Bandeja de pendientes: comprobantes sin confirmar + conciliaciones pendientes."""
    negocio = get_negocio(request.user)
    if negocio:
        comps = Comprobante.objects.filter(negocio=negocio, estado=Comprobante.SIN_CONFIRMAR)
        concils = (Conciliacion.objects.filter(negocio=negocio, resultado=Conciliacion.PENDIENTE)
                   .select_related("comprobante", "ruta"))
    else:
        comps = Comprobante.objects.none()
        concils = Conciliacion.objects.none()
    return render(request, "dashboard/pendientes.html",
                  {"comprobantes": comps, "conciliaciones": concils})


@login_required
def exportar_excel(request):
    import openpyxl

    qs, negocio = _qs_negocio(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Comprobantes"
    ws.append(["Remitente", "Valor", "Referencia", "Fecha", "Hora", "Origen", "Creado"])
    for c in qs:
        ws.append([
            c.de, float(c.valor), c.ref, c.fecha, c.hora,
            c.get_origen_display(),
            c.creado_en.strftime("%Y-%m-%d %H:%M"),
        ])

    nombre = nombre_descarga("comprobantes")
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f"attachment; filename={nombre}"
    wb.save(response)
    return response
