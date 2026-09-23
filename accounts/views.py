from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import redirect
from inertia import render as inertia_render

from core.peticiones import datos_post

from .forms import RegistroForm
from .models import Negocio, PerfilUsuario


def _errores(form):
    """Errores del formulario en el formato que espera Inertia: {campo: mensaje}.

    Los que no son de un campo concreto (credenciales inválidas, por ejemplo)
    van bajo "general", que es donde la pantalla los muestra arriba del todo.
    """
    errores = {campo: lista[0] for campo, lista in form.errors.items() if campo != "__all__"}
    if form.non_field_errors():
        errores["general"] = form.non_field_errors()[0]
    return errores


def entrar(request):
    """Inicio de sesión."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = AuthenticationForm(request, data=datos_post(request))
        if form.is_valid():
            login(request, form.get_user())
            # `next` permite volver a donde el usuario quería entrar.
            return redirect(request.GET.get("next") or "dashboard:home")
        return inertia_render(request, "Auth/Entrar", props={"errors": _errores(form)})

    return inertia_render(request, "Auth/Entrar", props={"errors": {}})


def registro(request):
    """Alta de un operador con su negocio."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = RegistroForm(datos_post(request))
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = form.cleaned_data.get("email", "")
                user.save()
                negocio = Negocio.objects.create(nombre=form.cleaned_data["negocio"])
                PerfilUsuario.objects.create(
                    user=user, negocio=negocio, rol=PerfilUsuario.ROL_ADMIN
                )
            login(request, user)
            return redirect("dashboard:home")

        return inertia_render(
            request,
            "Auth/Registro",
            props={"errors": _errores(form), "campos": _campos(form)},
        )

    return inertia_render(
        request, "Auth/Registro", props={"errors": {}, "campos": _campos(RegistroForm())}
    )


def _campos(form):
    """Describe los campos del formulario para que React los pinte.

    Se toman del formulario de Django en vez de repetirlos en el front: si
    mañana se agrega un campo al registro, la pantalla lo muestra sola.
    """
    return [
        {
            "nombre": nombre,
            "etiqueta": campo.label or nombre.replace("_", " ").capitalize(),
            "tipo": "password" if "password" in nombre else (
                "email" if nombre == "email" else "text"
            ),
            "ayuda": str(campo.help_text or ""),
            "requerido": campo.required,
        }
        for nombre, campo in form.fields.items()
    ]
