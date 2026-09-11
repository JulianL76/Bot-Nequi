"""Genera el par de llaves VAPID para las notificaciones push.

Se corre UNA sola vez. Las llaves identifican a este servidor ante el servicio
de push (Google/Mozilla): sin ellas cualquiera que robara la URL de suscripción
de un usuario podría mandarle notificaciones.

    python manage.py gen_vapid

Después se copian al .env (o a las variables del stack en producción). Si se
cambian, TODAS las suscripciones existentes dejan de servir y hay que volver a
pedir permiso a cada usuario.
"""

import base64

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera VAPID_PUBLIC_KEY y VAPID_PRIVATE_KEY para copiar al .env."

    def handle(self, *args, **options):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        clave = ec.generate_private_key(ec.SECP256R1())

        # Privada: en formato DER PKCS8, en base64url (lo que espera pywebpush).
        priv_der = clave.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Pública: punto sin comprimir (65 bytes), que es lo que consume el navegador.
        pub_raw = clave.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        def b64(datos: bytes) -> str:
            return base64.urlsafe_b64encode(datos).decode().rstrip("=")

        self.stdout.write(self.style.SUCCESS("Llaves VAPID generadas. Copialas al .env:\n"))
        self.stdout.write(f"VAPID_PUBLIC_KEY={b64(pub_raw)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={b64(priv_der)}")
        self.stdout.write("VAPID_ADMIN_EMAIL=tu-correo@ejemplo.com")
        self.stdout.write(self.style.WARNING(
            "\nGuardalas bien: si las cambiás, todos los usuarios tienen que "
            "volver a aceptar las notificaciones."
        ))
