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


def _bytes_jpeg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="JPEG")
    return buf.getvalue()


def _imagen(nombre="foto.jpg"):
    """Un JPEG mínimo válido (ImageField lo verifica con Pillow)."""
    return SimpleUploadedFile(nombre, _bytes_jpeg(), content_type="image/jpeg")


def _zip(entradas, nombre="fotos.zip"):
    """Un .zip en memoria. `entradas` es {ruta dentro del zip: bytes}."""
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for ruta, datos in entradas.items():
            zf.writestr(ruta, datos)
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type="application/zip")


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
            self.assertEqual(r.json(), {"n": 1, "omitidas": 0})

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


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SubidaZipTest(TestCase):
    """Un .zip sube como un archivo y se expande a N imágenes en el servidor."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test")
        self.user = User.objects.create_user("u1", password="x")
        PerfilUsuario.objects.create(user=self.user, negocio=self.negocio)
        self.client.force_login(self.user)
        self.url = reverse("comprobantes:subir_archivo")

    def test_expande_las_imagenes_del_zip(self):
        jpg = _bytes_jpeg()
        r = self.client.post(self.url, {"imagenes": _zip({
            "a.jpg": jpg, "sub/carpeta/b.png": jpg, "c.JPEG": jpg,
        })})
        self.assertEqual(r.json(), {"n": 3, "omitidas": 0})
        self.assertEqual(ArchivoPendiente.objects.count(), 3)

    def test_omite_lo_que_no_es_imagen_admitida_y_lo_reporta(self):
        jpg = _bytes_jpeg()
        r = self.client.post(self.url, {"imagenes": _zip({
            "ok.jpg": jpg, "notas.txt": b"hola", "video.mp4": b"x", "foto.heic": b"x",
        })})
        self.assertEqual(r.json(), {"n": 1, "omitidas": 3})
        self.assertEqual(ArchivoPendiente.objects.count(), 1)

    def test_ignora_la_basura_de_macos_y_las_carpetas(self):
        jpg = _bytes_jpeg()
        r = self.client.post(self.url, {"imagenes": _zip({
            "fotos/": b"", "fotos/a.jpg": jpg, "__MACOSX/._a.jpg": b"x", ".DS_Store": b"x",
        })})
        self.assertEqual(r.json()["n"], 1)

    def test_no_escribe_fuera_de_media_aunque_el_zip_traiga_rutas_trampa(self):
        """Zip slip: la ruta del zip se descarta, solo se usa el nombre base."""
        r = self.client.post(self.url, {"imagenes": _zip({
            "../../../../evil.jpg": _bytes_jpeg(),
        })})
        self.assertEqual(r.json()["n"], 1)
        ruta = ArchivoPendiente.objects.get().imagen.name
        self.assertNotIn("..", ruta)
        self.assertTrue(ruta.startswith("pendientes/"), ruta)

    def test_zip_danado_responde_400_sin_crear_nada(self):
        malo = SimpleUploadedFile("roto.zip", b"esto no es un zip",
                                  content_type="application/zip")
        r = self.client.post(self.url, {"imagenes": malo})
        self.assertEqual(r.status_code, 400)
        self.assertIn("zip", r.json()["error"].lower())
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_zip_sin_imagenes_responde_400(self):
        r = self.client.post(self.url, {"imagenes": _zip({"a.txt": b"hola"})})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_el_zip_se_mezcla_con_imagenes_sueltas_en_el_mismo_borrador(self):
        self.client.post(self.url, {"imagenes": _imagen("suelta.jpg")})
        self.client.post(self.url, {"imagenes": _zip({"a.jpg": _bytes_jpeg(),
                                                     "b.jpg": _bytes_jpeg()})})
        lote = LoteCarga.objects.get(estado=LoteCarga.BORRADOR)
        self.assertEqual(lote.archivos.count(), 3)

    def test_procesar_cuenta_las_imagenes_del_zip_en_el_total(self):
        self.client.post(self.url, {"imagenes": _zip({f"f{i}.jpg": _bytes_jpeg()
                                                      for i in range(5)})})
        with patch("comprobantes.views.procesar_lote.delay"):
            self.client.post(reverse("comprobantes:subir"))
        self.assertEqual(LoteCarga.objects.get().total, 5)

    def test_respaldo_sin_js_tambien_acepta_zip(self):
        with patch("comprobantes.views.procesar_lote.delay"):
            self.client.post(reverse("comprobantes:subir"),
                             {"imagenes": _zip({"a.jpg": _bytes_jpeg(),
                                                "b.jpg": _bytes_jpeg()})})
        self.assertEqual(LoteCarga.objects.get().total, 2)
