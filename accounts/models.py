from django.conf import settings
from django.db import models


class Negocio(models.Model):
    """Organización/equipo. Habilita el aislamiento multiusuario: cada
    comprobante pertenece a un negocio y los usuarios solo ven el suyo."""

    nombre = models.CharField(max_length=120)
    # Titular de la cuenta Nequi a validar en la conciliación (el destinatario
    # esperado en comprobantes y vouchers). Si está vacío, no se valida el nombre.
    titular_nequi = models.CharField("Titular Nequi", max_length=200, blank=True, default="")
    # Número Nequi del titular. La conciliación acepta el destinatario si coincide el
    # NOMBRE o el NÚMERO (a veces el nombre varía: apellido extra, apodo).
    numero_nequi = models.CharField("Número Nequi", max_length=30, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Negocio"
        verbose_name_plural = "Negocios"

    def __str__(self):
        return self.nombre


class PerfilUsuario(models.Model):
    ROL_ADMIN = "admin"
    ROL_OPERADOR = "operador"
    ROLES = [
        (ROL_ADMIN, "Administrador"),
        (ROL_OPERADOR, "Operador"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    negocio = models.ForeignKey(
        Negocio, on_delete=models.CASCADE, related_name="miembros", null=True, blank=True
    )
    rol = models.CharField(max_length=20, choices=ROLES, default=ROL_OPERADOR)
    # Enlaza la cuenta web con el usuario del bot de Telegram.
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True, db_index=True)
    es_especial = models.BooleanField(default=False, verbose_name="Modo romántico (Especial)")

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"

    @property
    def es_admin(self) -> bool:
        return self.rol == self.ROL_ADMIN
