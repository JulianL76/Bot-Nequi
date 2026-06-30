from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from accounts.models import Negocio
from comprobantes.models import Comprobante, Ruta


class LoteConciliacion(models.Model):
    """Un proceso de conciliación de comprobantes contra una ruta."""

    EN_COLA = "en_cola"
    PROCESANDO = "procesando"
    PAUSADO = "pausado"
    COMPLETADO = "completado"
    ESTADOS = [
        (EN_COLA, "En cola"),
        (PROCESANDO, "Procesando"),
        (PAUSADO, "Pausado"),
        (COMPLETADO, "Completado"),
    ]

    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="lotes_conciliacion")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="lotes_conciliacion",
    )
    ruta = models.ForeignKey(Ruta, on_delete=models.SET_NULL, null=True, related_name="lotes_conciliacion")
    total = models.PositiveIntegerField(default=0)
    procesadas = models.PositiveIntegerField(default=0)
    ok = models.PositiveIntegerField(default=0)
    pendientes = models.PositiveIntegerField(default=0)
    no_esta = models.PositiveIntegerField(default=0)
    revision = models.PositiveIntegerField(default=0)
    duplicados = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EN_COLA)
    creado_en = models.DateTimeField(auto_now_add=True)
    terminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Lote de conciliación"
        verbose_name_plural = "Lotes de conciliación"

    def __str__(self):
        return f"Conciliación #{self.pk} ({self.procesadas}/{self.total})"

    @property
    def progreso_pct(self) -> int:
        if not self.total:
            return 0
        return int(self.procesadas / self.total * 100)

    @property
    def terminado(self) -> bool:
        return self.estado == self.COMPLETADO


class Conciliacion(models.Model):
    """Resultado de conciliar una imagen subida contra los comprobantes."""

    OK = "ok"
    PENDIENTE = "pendiente"
    NO_ESTA = "no_esta"
    REVISION = "revision"
    DUPLICADO = "duplicado"
    RESULTADOS = [
        (OK, "OK"),
        (PENDIENTE, "Pendiente"),
        (NO_ESTA, "No está"),
        (REVISION, "Revisión manual"),
        (DUPLICADO, "Duplicado"),
    ]

    TIPO_VOUCHER = "voucher"
    TIPO_NEQUI = "nequi"
    TIPO_OTRO = "otro"
    TIPOS = [
        (TIPO_VOUCHER, "Voucher (corresponsal)"),
        (TIPO_NEQUI, "Comprobante Nequi"),
        (TIPO_OTRO, "Otro"),
    ]

    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="conciliaciones")
    lote = models.ForeignKey(LoteConciliacion, on_delete=models.CASCADE, related_name="items")
    ruta = models.ForeignKey(Ruta, on_delete=models.SET_NULL, null=True, related_name="conciliaciones")
    imagen = models.ImageField(upload_to="conciliaciones/%Y/%m/", null=True, blank=True)

    # Datos extraídos por la IA de la imagen subida.
    de = models.CharField(max_length=200, blank=True, default="")
    para = models.CharField("Destinatario/Titular", max_length=200, blank=True, default="")
    num = models.CharField("Número destino", max_length=30, blank=True, default="")
    tipo = models.CharField(max_length=20, choices=TIPOS, blank=True, default="")
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_raw = models.CharField(max_length=50, blank=True, default="")
    fecha = models.CharField(max_length=60, blank=True, default="")
    fecha_dt = models.DateField(null=True, blank=True, db_index=True)
    hora = models.CharField(max_length=30, blank=True, default="")
    ref = models.CharField(max_length=80, blank=True, default="")

    resultado = models.CharField(max_length=20, choices=RESULTADOS, null=True, blank=True)
    # Motivo de revisión manual o aviso (p. ej. dónde ya fue confirmado un duplicado).
    motivo_revision = models.CharField(max_length=200, blank=True, default="")
    aviso = models.CharField(max_length=200, blank=True, default="")
    comprobante = models.ForeignKey(
        Comprobante, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conciliaciones",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Conciliación"
        verbose_name_plural = "Conciliaciones"

    def __str__(self):
        return f"{self.ref} → {self.get_resultado_display() or 'pendiente'}"


@receiver(post_delete, sender=Conciliacion)
def _borrar_imagen_conciliacion(sender, instance, **kwargs):
    """Elimina el archivo de imagen del disco al borrar la conciliación."""
    if instance.imagen:
        instance.imagen.delete(save=False)
