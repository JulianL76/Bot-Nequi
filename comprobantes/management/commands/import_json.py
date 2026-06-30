"""Importa los datos legados de `listas_nequi.json` a la base de datos.

Estructura esperada del JSON:  { "<telegram_user_id>": [ {de, valor, fecha, hora, ref, img_log}, ... ] }

Cada user_id de Telegram se mapea a un usuario/negocio: si ya existe un
PerfilUsuario con ese telegram_id se reutiliza; si no, se crea uno automático.
"""

import json
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Negocio, PerfilUsuario
from comprobantes.models import Comprobante
from core.parsing import limpiar_monto

User = get_user_model()


class Command(BaseCommand):
    help = "Importa listas_nequi.json a la tabla Comprobante."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=os.path.join(settings.BASE_DIR, "listas_nequi.json"),
            help="Ruta al archivo listas_nequi.json",
        )

    def handle(self, *args, **options):
        path = options["path"]
        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"No existe el archivo: {path}"))
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_importados = 0
        with transaction.atomic():
            for user_id, lista in data.items():
                user, negocio = self._resolver_destino(user_id)
                for item in lista:
                    ref = (item.get("ref") or "").strip()
                    # Saltar duplicados por (negocio, ref) ya existentes.
                    if ref and ref != "No encontrada" and Comprobante.objects.filter(
                        negocio=negocio, ref=ref
                    ).exists():
                        continue
                    Comprobante.objects.create(
                        negocio=negocio,
                        creado_por=user,
                        de=item.get("de", "No encontrada"),
                        valor=limpiar_monto(item.get("valor", "0")),
                        valor_raw=item.get("valor", ""),
                        fecha=item.get("fecha", ""),
                        hora=item.get("hora", ""),
                        ref=ref,
                        origen=Comprobante.ORIGEN_TELEGRAM,
                    )
                    total_importados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Importados {total_importados} comprobantes."
        ))

    def _resolver_destino(self, user_id):
        """Devuelve (user, negocio) para un telegram user_id, creando lo necesario."""
        try:
            tg_id = int(user_id)
        except (TypeError, ValueError):
            tg_id = None

        if tg_id is not None:
            perfil = PerfilUsuario.objects.filter(telegram_id=tg_id).select_related(
                "user", "negocio"
            ).first()
            if perfil and perfil.negocio:
                return perfil.user, perfil.negocio

        username = f"tg_{user_id}"
        user, _ = User.objects.get_or_create(username=username)
        negocio, _ = Negocio.objects.get_or_create(nombre=f"Negocio de {username}")
        PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={"negocio": negocio, "telegram_id": tg_id},
        )
        return user, negocio
