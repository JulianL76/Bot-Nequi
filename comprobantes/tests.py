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
    """JPEG con contraste real (fondo claro + trazos oscuros).

    No sirve un cuadrado de un solo color: el servidor rechaza las imágenes
    lisas porque son el síntoma del canvas que falla en el celular.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (120, 80), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 15, 110, 25], fill=(15, 15, 15))
    d.rectangle([10, 40, 70, 48], fill=(30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
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
            self.assertEqual(r.json(), {"resultados": [{"n": 1, "omitidas": 0}]})

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
        self.assertEqual(r.json()["resultados"], [{"n": 3, "omitidas": 0}])
        self.assertEqual(ArchivoPendiente.objects.count(), 3)

    def test_omite_lo_que_no_es_imagen_admitida_y_lo_reporta(self):
        jpg = _bytes_jpeg()
        r = self.client.post(self.url, {"imagenes": _zip({
            "ok.jpg": jpg, "notas.txt": b"hola", "video.mp4": b"x", "foto.heic": b"x",
        })})
        self.assertEqual(r.json()["resultados"], [{"n": 1, "omitidas": 3}])
        self.assertEqual(ArchivoPendiente.objects.count(), 1)

    def test_ignora_la_basura_de_macos_y_las_carpetas(self):
        jpg = _bytes_jpeg()
        r = self.client.post(self.url, {"imagenes": _zip({
            "fotos/": b"", "fotos/a.jpg": jpg, "__MACOSX/._a.jpg": b"x", ".DS_Store": b"x",
        })})
        self.assertEqual(r.json()["resultados"][0]["n"], 1)

    def test_no_escribe_fuera_de_media_aunque_el_zip_traiga_rutas_trampa(self):
        """Zip slip: la ruta del zip se descarta, solo se usa el nombre base."""
        r = self.client.post(self.url, {"imagenes": _zip({
            "../../../../evil.jpg": _bytes_jpeg(),
        })})
        self.assertEqual(r.json()["resultados"][0]["n"], 1)
        ruta = ArchivoPendiente.objects.get().imagen.name
        self.assertNotIn("..", ruta)
        self.assertTrue(ruta.startswith("pendientes/"), ruta)

    def test_zip_danado_se_reporta_sin_crear_nada(self):
        malo = SimpleUploadedFile("roto.zip", b"esto no es un zip",
                                  content_type="application/zip")
        r = self.client.post(self.url, {"imagenes": malo})
        self.assertEqual(r.status_code, 200)
        self.assertIn("zip", r.json()["resultados"][0]["error"].lower())
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_zip_sin_imagenes_se_reporta(self):
        r = self.client.post(self.url, {"imagenes": _zip({"a.txt": b"hola"})})
        self.assertEqual(r.status_code, 200)
        self.assertIn("error", r.json()["resultados"][0])
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


def _imagen_lisa(color=(0, 0, 0), nombre="negra.jpg"):
    """Una imagen de un solo color: lo que produce el canvas cuando falla."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG", quality=82)
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type="image/jpeg")


def _imagen_con_contenido(nombre="recibo.jpg"):
    """Simula un comprobante: fondo claro con texto oscuro."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 200), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 40, 280, 60], fill=(15, 15, 15))
    d.rectangle([20, 90, 200, 105], fill=(30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class ImagenEnBlancoTest(TestCase):
    """El canvas del celular a veces no dibuja y sube una imagen lisa."""

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

    def test_detecta_la_negra_y_la_blanca(self):
        from core.imagenes import esta_en_blanco

        self.assertTrue(esta_en_blanco(_imagen_lisa((0, 0, 0))))
        self.assertTrue(esta_en_blanco(_imagen_lisa((255, 255, 255))))

    def test_no_confunde_un_comprobante_real(self):
        from core.imagenes import esta_en_blanco

        self.assertFalse(esta_en_blanco(_imagen_con_contenido()))
        self.assertFalse(esta_en_blanco(_imagen()))  # el fixture ya trae contraste

    def test_rechaza_la_imagen_negra_y_no_la_guarda(self):
        """El error viaja por archivo: en una tanda no puede tumbar a los demás."""
        r = self.client.post(self.url, {"imagenes": _imagen_lisa()})
        self.assertEqual(r.status_code, 200)
        self.assertIn("blanco", r.json()["resultados"][0]["error"])
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_la_imagen_con_contenido_si_entra(self):
        r = self.client.post(self.url, {"imagenes": _imagen_con_contenido()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ArchivoPendiente.objects.count(), 1)

    def test_una_negra_no_arrastra_a_las_buenas(self):
        self.client.post(self.url, {"imagenes": _imagen_con_contenido("a.jpg")})
        self.client.post(self.url, {"imagenes": _imagen_lisa()})
        self.client.post(self.url, {"imagenes": _imagen_con_contenido("b.jpg")})
        self.assertEqual(ArchivoPendiente.objects.count(), 2)

    def test_un_archivo_ilegible_no_se_rechaza_por_las_dudas(self):
        """Ante la duda deja pasar: mejor eso que perder una imagen buena."""
        from core.imagenes import esta_en_blanco

        self.assertFalse(esta_en_blanco(
            SimpleUploadedFile("x.jpg", b"no soy una imagen", content_type="image/jpeg")))


@override_settings(MEDIA_ROOT=MEDIA_TMP, MAX_ZIP_MB=1)
class TopeTamanoZipTest(TestCase):
    """El tope del navegador se salta trivialmente; el que cuenta es el del servidor."""

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

    def test_rechaza_el_zip_que_pasa_el_tope(self):
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("relleno.bin", b"\0" * (2 * 1024 * 1024))  # 2 MB > tope de 1 MB
        grande = SimpleUploadedFile("grande.zip", buf.getvalue(),
                                    content_type="application/zip")
        r = self.client.post(self.url, {"imagenes": grande})
        self.assertEqual(r.status_code, 200)
        self.assertIn("MB", r.json()["resultados"][0]["error"])
        self.assertFalse(ArchivoPendiente.objects.exists())

    def test_el_zip_chico_sigue_pasando(self):
        r = self.client.post(self.url, {"imagenes": _zip({"a.jpg": _bytes_jpeg()})})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["resultados"][0]["n"], 1)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SubidaPorTandasTest(TestCase):
    """Varias imágenes en UNA petición: es lo que recorta los viajes de red."""

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

    def test_una_tanda_guarda_todas_y_devuelve_un_resultado_por_archivo(self):
        tanda = [_imagen(f"f{i}.jpg") for i in range(8)]
        r = self.client.post(self.url, {"imagenes": tanda})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["resultados"], [{"n": 1, "omitidas": 0}] * 8)
        self.assertEqual(ArchivoPendiente.objects.count(), 8)

    def test_un_archivo_malo_no_arrastra_a_los_buenos_de_la_tanda(self):
        """Lo que justifica el resultado por archivo en vez de un status global."""
        tanda = [_imagen("ok1.jpg"), _imagen_lisa(nombre="negra.jpg"),
                 _imagen("ok2.jpg"), _imagen("ok3.jpg")]
        r = self.client.post(self.url, {"imagenes": tanda})
        res = r.json()["resultados"]
        self.assertEqual(r.status_code, 200)
        self.assertEqual([("error" in x) for x in res], [False, True, False, False])
        self.assertEqual(ArchivoPendiente.objects.count(), 3)

    def test_el_orden_de_los_resultados_calza_con_el_de_los_archivos(self):
        """El cliente mapea resultados[i] -> archivo[i]; si se desordena, miente."""
        tanda = [_imagen("a.jpg"),
                 _zip({"x.jpg": _bytes_jpeg(), "y.jpg": _bytes_jpeg()}),
                 _imagen_lisa(nombre="negra.jpg"),
                 _imagen("b.jpg")]
        res = self.client.post(self.url, {"imagenes": tanda}).json()["resultados"]
        self.assertEqual(res[0], {"n": 1, "omitidas": 0})
        self.assertEqual(res[1], {"n": 2, "omitidas": 0})   # el zip aporta 2
        self.assertIn("error", res[2])
        self.assertEqual(res[3], {"n": 1, "omitidas": 0})

    def test_las_tandas_se_acumulan_en_el_mismo_borrador(self):
        for _ in range(3):
            self.client.post(self.url, {"imagenes": [_imagen(f"{_}-{i}.jpg") for i in range(8)]})
        self.assertEqual(LoteCarga.objects.filter(estado=LoteCarga.BORRADOR).count(), 1)
        self.assertEqual(ArchivoPendiente.objects.count(), 24)

    def test_una_tanda_de_uno_sigue_funcionando(self):
        r = self.client.post(self.url, {"imagenes": _imagen()})
        self.assertEqual(r.json()["resultados"], [{"n": 1, "omitidas": 0}])


VAPID_TEST = {
    "VAPID_PUBLIC_KEY": "BGpl6ezK7CLwZUiL301BJCJ0amTAhiK0ahqVMnUeC88LgAqSDe-iPYfNlmbmbbY2hRWKRZ2ujI6-kbh5UOeKliA",
    "VAPID_PRIVATE_KEY": "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQghIsHGZKAu6KrRF2aV7v8JYws1ICcqEwS7WsCtV6LgrehRANCAARqZensyuwi8GVIi99NQSQidGpkwIYitGoalTJ1HgvPC4AKkg3voj2HzZZm5m22NoUVikWdroyOvpG4eVDnipYg",
    "VAPID_ADMIN_EMAIL": "test@example.com",
}


def _suscripcion(endpoint="https://fcm.googleapis.com/fcm/send/abc123"):
    return {"endpoint": endpoint, "keys": {"p256dh": "clave-p256dh", "auth": "clave-auth"}}


@override_settings(**VAPID_TEST)
class PushSuscripcionTest(TestCase):
    """Alta/baja de dispositivos para las notificaciones push."""

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test")
        self.user = User.objects.create_user("u1", password="x")
        PerfilUsuario.objects.create(user=self.user, negocio=self.negocio)
        self.client.force_login(self.user)

    def _suscribir(self, sub=None):
        import json
        return self.client.post(reverse("comprobantes:push_suscribir"),
                                json.dumps(sub or _suscripcion()),
                                content_type="application/json")

    def test_guarda_la_suscripcion_del_dispositivo(self):
        from .models import SuscripcionPush

        r = self._suscribir()
        self.assertEqual(r.status_code, 200)
        s = SuscripcionPush.objects.get()
        self.assertEqual(s.usuario, self.user)
        self.assertEqual(s.p256dh, "clave-p256dh")

    def test_un_usuario_puede_tener_varios_dispositivos(self):
        from .models import SuscripcionPush

        self._suscribir(_suscripcion("https://fcm.googleapis.com/celular"))
        self._suscribir(_suscripcion("https://fcm.googleapis.com/pc"))
        self.assertEqual(SuscripcionPush.objects.filter(usuario=self.user).count(), 2)

    def test_re_suscribir_el_mismo_dispositivo_no_duplica(self):
        from .models import SuscripcionPush

        self._suscribir()
        self._suscribir()
        self.assertEqual(SuscripcionPush.objects.count(), 1)

    def test_desuscribir_borra_solo_ese_dispositivo(self):
        import json

        from .models import SuscripcionPush

        self._suscribir(_suscripcion("https://fcm.googleapis.com/celular"))
        self._suscribir(_suscripcion("https://fcm.googleapis.com/pc"))
        self.client.post(reverse("comprobantes:push_desuscribir"),
                         json.dumps({"endpoint": "https://fcm.googleapis.com/pc"}),
                         content_type="application/json")
        self.assertEqual([s.endpoint for s in SuscripcionPush.objects.all()],
                         ["https://fcm.googleapis.com/celular"])

    def test_suscripcion_mal_formada_responde_400(self):
        import json

        r = self.client.post(reverse("comprobantes:push_suscribir"),
                             json.dumps({"endpoint": "x"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_requiere_login(self):
        import json

        self.client.logout()
        r = self.client.post(reverse("comprobantes:push_suscribir"),
                             json.dumps(_suscripcion()), content_type="application/json")
        self.assertNotEqual(r.status_code, 200)


@override_settings(**VAPID_TEST)
class PushEnvioTest(TestCase):
    """El envío en sí, con pywebpush interceptado."""

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test")
        self.user = User.objects.create_user("u1", password="x")
        PerfilUsuario.objects.create(user=self.user, negocio=self.negocio)
        from .models import SuscripcionPush
        SuscripcionPush.objects.create(
            usuario=self.user, endpoint="https://fcm.googleapis.com/a",
            p256dh="p", auth="a")

    def test_envia_a_cada_dispositivo_con_el_contenido_correcto(self):
        import json

        from .notifications import notificar_push

        with patch("pywebpush.webpush") as wp:
            n = notificar_push(self.user, "Lote #7 terminado", "380 exitosas",
                               url="/comprobantes/lote/7/")
        self.assertEqual(n, 1)
        carga = json.loads(wp.call_args.kwargs["data"])
        self.assertEqual(carga["titulo"], "Lote #7 terminado")
        self.assertEqual(carga["url"], "/comprobantes/lote/7/")

    def test_borra_la_suscripcion_cuando_el_navegador_ya_no_existe(self):
        """410 Gone = el usuario desinstaló o limpió datos; no sirve reintentarla."""
        from pywebpush import WebPushException

        from .models import SuscripcionPush
        from .notifications import notificar_push

        resp = type("R", (), {"status_code": 410})()
        with patch("pywebpush.webpush", side_effect=WebPushException("gone", response=resp)):
            n = notificar_push(self.user, "x")
        self.assertEqual(n, 0)
        self.assertFalse(SuscripcionPush.objects.exists())

    def test_un_error_pasajero_no_borra_la_suscripcion(self):
        from pywebpush import WebPushException

        from .models import SuscripcionPush
        from .notifications import notificar_push

        resp = type("R", (), {"status_code": 500})()
        with patch("pywebpush.webpush", side_effect=WebPushException("boom", response=resp)):
            notificar_push(self.user, "x")
        self.assertTrue(SuscripcionPush.objects.exists())

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    def test_sin_llaves_configuradas_no_hace_nada(self):
        from .notifications import notificar_push

        with patch("pywebpush.webpush") as wp:
            self.assertEqual(notificar_push(self.user, "x"), 0)
        wp.assert_not_called()

    def test_el_fin_de_lote_dispara_el_push(self):
        """El enganche real: _notificar_fin ya llamaba a inapp y Telegram."""
        from .models import LoteCarga
        from .tasks import _notificar_fin

        lote = LoteCarga.objects.create(negocio=self.negocio, creado_por=self.user,
                                        total=5, exitosas=5)
        with patch("comprobantes.tasks.notificar_push") as push, \
             patch("comprobantes.tasks.notificar_telegram"):
            _notificar_fin(lote)
        push.assert_called_once()
        self.assertIn(f"/comprobantes/lote/{lote.pk}/", push.call_args.kwargs["url"])
