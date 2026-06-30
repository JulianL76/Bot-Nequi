from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistroForm(UserCreationForm):
    """Registro de usuario + nombre del negocio que se crea para él."""

    email = forms.EmailField(required=False)
    negocio = forms.CharField(
        max_length=120, label="Nombre del negocio",
        help_text="Se creará un negocio nuevo del que serás administrador.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
