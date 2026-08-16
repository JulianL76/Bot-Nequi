import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Negocio, PerfilUsuario

from .models import ArchivoPendiente, LoteCarga

MEDIA_TMP = tempfile.mkdtemp()


def _imagen(nombre="foto.jpg"):
    """Un JPEG mínimo válido (ImageField lo verifica con Pillow)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="JPEG")
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SubidaPorArchivoTest(TestCase):
    """Subida imagen a imagen: es lo que hace viable subir desde el celular."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test")
        self.user = User.objects.create_user("u1", password="x")
        PerfilUsuario.objects.create(user=self.user, negocio=self.negocio)
        self.client.force_login(self.user)

    def _subir(self, n=3):
        for i in range(n):
            r = self.client.post(reverse("comprobantes:subir_archivo"),
                                 {"imagenes": _imagen(f"f{i}.jpg")})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.decode().isdigit())

    def test_cada_imagen_va_en_su_peticion_y_se_acumula_en_un_borrador(self):
        self._subir(3)
        lotes = LoteCarga.objects.filter(estado=LoteCarga.BORRADOR)
        self.assertEqual(lotes.count(), 1, "debe reusar el mismo borrador")
        self.assertEqual(lotes.first().archivos.count(), 3)

    def test_el_borrador_sobrevive_a_recargar_la_pagina(self):
        self._subir(2)
        r = self.client.get(reverse("comprobantes:subir"))
        self.assertEqual(r.context["guardadas"], 2)

    def test_se_pueden_agregar_mas_imagenes_despues(self):
        self._subir(2)
        self._subir(3)
        self.assertEqual(ArchivoPendiente.objects.count(), 5)
        self.assertEqual(LoteCarga.objects.filter(estado=LoteCarga.BORRADOR).count(), 1)

    def test_procesar_encola_el_borrador_con_su_total(self):
        self._subir(4)
        with patch("comprobantes.views.procesar_lote.delay") as delay:
            r = self.client.post(reverse("comprobantes:subir"))
        lote = LoteCarga.objects.get()
        self.assertEqual(lote.estado, LoteCarga.EN_COLA)
        self.assertEqual(lote.total, 4)
        delay.assert_called_once_with(lote.id)
        self.assertRedirects(r, reverse("comprobantes:lote_detalle", args=[lote.id]))

    def test_procesar_sin_imagenes_no_crea_lote(self):
        with patch("comprobantes.views.procesar_lote.delay") as delay:
            self.client.post(reverse("comprobantes:subir"))
        self.assertFalse(LoteCarga.objects.exists())
        delay.assert_not_called()

    def test_respaldo_sin_js_sigue_aceptando_el_post_con_los_archivos(self):
        with patch("comprobantes.views.procesar_lote.delay"):
            self.client.post(reverse("comprobantes:subir"),
                             {"imagenes": [_imagen("a.jpg"), _imagen("b.jpg")]})
        lote = LoteCarga.objects.get()
        self.assertEqual((lote.estado, lote.total), (LoteCarga.EN_COLA, 2))

    def test_descartar_borra_las_imagenes_pendientes(self):
        self._subir(3)
        self.client.post(reverse("comprobantes:descartar_borrador"))
        self.assertFalse(LoteCarga.objects.exists())
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_el_borrador_no_aparece_en_el_historial(self):
        self._subir(1)
        r = self.client.get(reverse("comprobantes:lotes"))
        self.assertEqual(list(r.context["page"]), [])

    def test_el_borrador_es_por_usuario(self):
        self._subir(2)
        otro = User.objects.create_user("u2", password="x")
        PerfilUsuario.objects.create(user=otro, negocio=self.negocio)
        self.client.force_login(otro)
        self._subir(1)
        self.assertEqual(LoteCarga.objects.filter(estado=LoteCarga.BORRADOR).count(), 2)

    def test_peticion_sin_archivo_responde_400(self):
        r = self.client.post(reverse("comprobantes:subir_archivo"), {})
        self.assertEqual(r.status_code, 400)
