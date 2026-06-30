from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import RegistroForm
from .models import Negocio, PerfilUsuario


def registro(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = RegistroForm(request.POST)
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
    else:
        form = RegistroForm()

    return render(request, "registration/registro.html", {"form": form})
