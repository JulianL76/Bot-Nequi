from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from accounts.models import Negocio
from core.parsing import parse_fecha, parse_hora


class Ruta(models.Model):
    """Ruta de cobro/entrega predefinida por negocio (para la conciliación)."""

    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="rutas")
    numero = models.PositiveIntegerField()
    nombre = models.CharField(max_length=120, blank=True, default="")
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["numero"]
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        constraints = [
            models.UniqueConstraint(fields=["negocio", "numero"], name="ruta_unica_por_negocio")
        ]

    def __str__(self):
        return f"Ruta {self.numero}" + (f" — {self.nombre}" if self.nombre else "")


class LoteCarga(models.Model):
    """Un lote de subida masiva de comprobantes procesado en segundo plano."""

    # Borrador: el usuario está subiendo imágenes (una petición por imagen) y
    # todavía no ha pulsado "Procesar". No aparece en el historial ni se encola.
    BORRADOR = "borrador"
    EN_COLA = "en_cola"
    PROCESANDO = "procesando"
    PAUSADO = "pausado"
    COMPLETADO = "completado"
    CON_ERRORES = "con_errores"
    ESTADOS = [
        (BORRADOR, "Borrador"),
        (EN_COLA, "En cola"),
        (PROCESANDO, "Procesando"),
        (PAUSADO, "Pausado"),
        (COMPLETADO, "Completado"),
        (CON_ERRORES, "Completado con errores"),
    ]

    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="lotes")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="lotes"
    )
    total = models.PositiveIntegerField(default=0)
    procesadas = models.PositiveIntegerField(default=0)
    exitosas = models.PositiveIntegerField(default=0)
    fallidas = models.PositiveIntegerField(default=0)
    duplicadas = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EN_COLA)
    creado_en = models.DateTimeField(auto_now_add=True)
    terminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Lote de carga"
        verbose_name_plural = "Lotes de carga"

    def __str__(self):
        return f"Lote #{self.pk} ({self.procesadas}/{self.total})"

    @property
    def progreso_pct(self) -> int:
        if not self.total:
            return 0
        return int(self.procesadas / self.total * 100)

    @property
    def terminado(self) -> bool:
        return self.estado in (self.COMPLETADO, self.CON_ERRORES)


class ArchivoPendiente(models.Model):
    """Imagen subida que aún no se ha analizado.

    El comprobante solo se crea cuando la IA extrae los datos correctamente, así
    que las imágenes recién subidas viven aquí hasta ser procesadas.
    """

    lote = models.ForeignKey(LoteCarga, on_delete=models.CASCADE, related_name="archivos")
    imagen = models.ImageField(upload_to="pendientes/%Y/%m/")
    # Marcado cuando el análisis falla, para poder reprocesarlo después.
    fallido = models.BooleanField(default=False)
    # Motivo del último fallo (para mostrarlo al usuario).
    error = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Archivo pendiente"
        verbose_name_plural = "Archivos pendientes"


class Comprobante(models.Model):
    """Comprobante de transferencia Nequi con los campos extraídos por la IA.

    Replica el modelo JSON original (de, valor, fecha, hora, ref) pero tipado y
    relacional, con el negocio dueño y la imagen asociada.
    """

    ORIGEN_WEB = "web"
    ORIGEN_TELEGRAM = "telegram"
    ORIGEN_MANUAL = "manual"
    ORIGENES = [(ORIGEN_WEB, "Web"), (ORIGEN_TELEGRAM, "Telegram"), (ORIGEN_MANUAL, "Manual")]

    SIN_CONFIRMAR = "sin_confirmar"
    CONFIRMADO = "confirmado"
    ESTADOS = [(SIN_CONFIRMAR, "Sin confirmar"), (CONFIRMADO, "Confirmado")]

    negocio = models.ForeignKey(
        Negocio, on_delete=models.CASCADE, related_name="comprobantes"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="comprobantes",
    )
    lote = models.ForeignKey(
        LoteCarga, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="comprobantes",
    )

    de = models.CharField("Remitente", max_length=200, default="No encontrada")
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_raw = models.CharField(max_length=50, blank=True, default="")
    fecha = models.CharField(max_length=60, blank=True, default="")
    # Fecha parseada desde el texto `fecha`, para filtrar por día (ver save()).
    fecha_dt = models.DateField(null=True, blank=True, db_index=True)
    hora = models.CharField(max_length=30, blank=True, default="")
    ref = models.CharField("Referencia", max_length=80, blank=True, default="")
    # Ruta asignada al confirmarse vía conciliación.
    ruta = models.ForeignKey(
        Ruta, on_delete=models.SET_NULL, null=True, blank=True, related_name="comprobantes"
    )

    imagen = models.ImageField(upload_to="comprobantes/%Y/%m/", null=True, blank=True)
    fuente_ia = models.CharField(max_length=20, blank=True, default="")
    origen = models.CharField(max_length=20, choices=ORIGENES, default=ORIGEN_WEB)
    # Marcado cuando al subir ya existía otro comprobante con la misma referencia.
    es_duplicado = models.BooleanField(default=False)
    duplicado_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicados"
    )
    # Estado de revisión. Por defecto "sin confirmar" (extraído por IA, pendiente
    # de revisión humana); se marca "confirmado" cuando un usuario lo valida.
    estado = models.CharField(max_length=20, choices=ESTADOS, default=SIN_CONFIRMAR)

    # Trazabilidad de la confirmación: por qué vía, cuándo, quién y (si aplica)
    # con qué ítem de conciliación se confirmó. Ver marcar_confirmado().
    VIA_CONCILIACION = "conciliacion"
    VIA_CONC_PENDIENTE = "conc_pendiente"
    VIA_CONC_AGREGAR = "conc_agregar"
    VIA_LISTA = "lista"
    VIA_EDICION = "edicion"
    VIA_IMPORTACION = "importacion"
    VIAS_CONFIRMACION = [
        (VIA_CONCILIACION, "Conciliación automática"),
        (VIA_CONC_PENDIENTE, "Conciliación (pendiente confirmado a mano)"),
        (VIA_CONC_AGREGAR, "Conciliación (añadido y confirmado a mano)"),
        (VIA_LISTA, "Manual desde el listado"),
        (VIA_EDICION, "Manual al editar"),
        (VIA_IMPORTACION, "Importación de Excel"),
    ]
    confirmado_via = models.CharField(max_length=20, choices=VIAS_CONFIRMACION, blank=True, default="")
    confirmado_en = models.DateTimeField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="comprobantes_confirmados",
    )
    confirmado_conciliacion = models.ForeignKey(
        "conciliaciones.Conciliacion", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        constraints = [
            # Una referencia no se repite dentro del mismo negocio.
            # Solo se exige a los originales; los marcados como duplicado quedan exentos.
            models.UniqueConstraint(
                fields=["negocio", "ref"],
                condition=~models.Q(ref="") & ~models.Q(ref="No encontrada") & models.Q(es_duplicado=False),
                name="ref_unica_por_negocio",
            )
        ]
        indexes = [models.Index(fields=["negocio", "ref"])]

    def save(self, *args, **kwargs):
        # Mantener fecha_dt sincronizada con el texto `fecha` (web, bot y conciliación).
        self.fecha_dt = parse_fecha(self.fecha)
        # Normalizar la hora a 24h (ej. "05:43 p. m." → "17:43"); si no parsea, se deja igual.
        t = parse_hora(self.hora)
        if t:
            self.hora = t.strftime("%H:%M")
        super().save(*args, **kwargs)

    CAMPOS_CONFIRMACION = ["estado", "confirmado_via", "confirmado_en",
                           "confirmado_por", "confirmado_conciliacion"]

    def marcar_confirmado(self, via, usuario=None, conciliacion=None):
        """Marca como confirmado registrando la trazabilidad (no guarda)."""
        from django.utils import timezone

        self.estado = self.CONFIRMADO
        self.confirmado_via = via
        self.confirmado_en = timezone.now()
        self.confirmado_por = usuario
        self.confirmado_conciliacion = conciliacion

    def quitar_confirmacion(self):
        """Vuelve a "sin confirmar" y limpia la trazabilidad (no guarda)."""
        self.estado = self.SIN_CONFIRMAR
        self.confirmado_via = ""
        self.confirmado_en = None
        self.confirmado_por = None
        self.confirmado_conciliacion = None

    def __str__(self):
        return f"{self.de} — {self.valor} ({self.ref})"


class Notificacion(models.Model):
    """Notificación in-app (p. ej. fin de procesamiento de un lote)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    titulo = models.CharField(max_length=160)
    mensaje = models.TextField(blank=True, default="")
    leida = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return self.titulo


class SuscripcionPush(models.Model):
    """Un navegador/dispositivo suscrito a las notificaciones push del usuario.

    Cada dispositivo genera su propia suscripción, así que un usuario puede
    tener varias (celular + PC). El `endpoint` es la URL única que da el
    navegador; es lo que identifica al dispositivo y por eso es la clave.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="suscripciones_push"
    )
    endpoint = models.TextField(unique=True)
    # Claves de cifrado que da el navegador; sin ellas no se puede enviar.
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    # Para poder mostrar "Chrome en Android" y depurar suscripciones muertas.
    user_agent = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Suscripción push"
        verbose_name_plural = "Suscripciones push"

    def __str__(self):
        return f"{self.usuario} — {self.endpoint[:40]}…"

    def como_dict(self) -> dict:
        """El formato que espera pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }


@receiver(post_delete, sender=Comprobante)
def _borrar_imagen_comprobante(sender, instance, **kwargs):
    """Elimina el archivo de imagen del disco al borrar el comprobante."""
    if instance.imagen:
        instance.imagen.delete(save=False)


@receiver(post_delete, sender=ArchivoPendiente)
def _borrar_imagen_pendiente(sender, instance, **kwargs):
    """Elimina la imagen de staging del disco al borrar el archivo pendiente."""
    if instance.imagen:
        instance.imagen.delete(save=False)
