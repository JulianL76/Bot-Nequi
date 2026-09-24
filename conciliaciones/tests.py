import shutil
import tempfile
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Negocio, PerfilUsuario
from comprobantes.models import Comprobante, Ruta
# Fábricas de archivos de prueba compartidas (imagen, zip).
from comprobantes.tests import _bytes_jpeg, _imagen, _zip
from conciliaciones.models import Conciliacion, LoteConciliacion
from conciliaciones.tasks import validar_y_emparejar, _comp_candidato

_MEDIA_TMP = tempfile.mkdtemp()


class EmparejamientoVoucherTest(TestCase):
    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test Negocio", titular_nequi="KAREN ACUNA")
        self.ruta = Ruta.objects.create(negocio=self.negocio, numero=1, nombre="Juan")
        self.lote = LoteConciliacion.objects.create(negocio=self.negocio, ruta=self.ruta)

        # Crear dos comprobantes con el mismo monto y la misma hora
        self.comp1 = Comprobante.objects.create(
            negocio=self.negocio,
            ref="S79903816",
            valor=45000,
            fecha="14 de julio de 2026",
            hora="11:21",
        )
        self.comp2 = Comprobante.objects.create(
            negocio=self.negocio,
            ref="S78987831",
            valor=45000,
            fecha="14 de julio de 2026",
            hora="11:21",
        )

    def test_voucher_con_referencia_exacta_s(self):
        # Voucher donde la ref se fijó exacta como S78987831
        item = Conciliacion.objects.create(
            lote=self.lote,
            negocio=self.negocio,
            tipo=Conciliacion.TIPO_VOUCHER,
            ref="S78987831",
            valor=45000,
            fecha_dt=date(2026, 7, 14),
            hora="11:21",
            para="KAREN ACUNA",
        )

        candidato = _comp_candidato(item)
        self.assertEqual(candidato.ref, "S78987831")

        resultado = validar_y_emparejar(item, self.lote)
        self.assertEqual(resultado, "ok")
        self.assertEqual(item.comprobante, self.comp2)

    def test_voucher_con_apro_sufijo(self):
        # Voucher donde la ref es solo el APRO (78987831)
        item = Conciliacion.objects.create(
            lote=self.lote,
            negocio=self.negocio,
            tipo=Conciliacion.TIPO_VOUCHER,
            ref="78987831",
            valor=45000,
            fecha_dt=date(2026, 7, 14),
            hora="11:21",
            para="KAREN ACUNA",
        )

        candidato = _comp_candidato(item)
        self.assertEqual(candidato.ref, "S78987831")

        resultado = validar_y_emparejar(item, self.lote)
        self.assertEqual(resultado, "ok")
        self.assertEqual(item.comprobante, self.comp2)


class ConfirmacionPreviaTest(TestCase):
    """Una conciliación no debe pisar una confirmación hecha fuera de ella.

    Pasó en producción: un comprobante confirmado a mano desde el listado fue
    re-confirmado por una conciliación posterior, y se perdió quién lo había
    confirmado, cuándo y con qué ruta.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("sharick", password="x")
        self.negocio = Negocio.objects.create(nombre="N", titular_nequi="KAREN ACUNA")
        self.ruta = Ruta.objects.create(negocio=self.negocio, numero=7)
        self.lote = LoteConciliacion.objects.create(negocio=self.negocio, ruta=self.ruta)
        self.comp = Comprobante.objects.create(
            negocio=self.negocio, ref="M22497800", valor=250000,
            fecha="18 de septiembre de 2026", hora="18:35",
        )

    def _item(self):
        return Conciliacion.objects.create(
            negocio=self.negocio, lote=self.lote, ruta=self.ruta,
            tipo=Conciliacion.TIPO_NEQUI, para="KAREN ACUNA",
            ref="M22497800", valor=250000,
            fecha="18 de septiembre de 2026", hora="18:35",
        )

    def test_no_pisa_una_confirmacion_manual(self):
        self.comp.marcar_confirmado(Comprobante.VIA_LISTA, self.usuario)
        self.comp.save()
        antes = (self.comp.confirmado_via, self.comp.confirmado_en, self.comp.confirmado_por_id)

        item = self._item()
        self.assertEqual(validar_y_emparejar(item, self.lote), "duplicado")

        item.refresh_from_db()
        self.assertIn("Ya confirmado", item.aviso)

        self.comp.refresh_from_db()
        self.assertEqual(
            (self.comp.confirmado_via, self.comp.confirmado_en, self.comp.confirmado_por_id),
            antes,
            "la conciliación pisó la confirmación manual",
        )
        self.assertIsNone(self.comp.ruta_id, "no debe reasignar la ruta")

    def test_el_aviso_señala_la_discrepancia_de_ruta(self):
        """Si la ruta que ya tiene no es la de esta conciliación, hay que verlo."""
        otra = Ruta.objects.create(negocio=self.negocio, numero=3)
        self.comp.ruta = otra
        self.comp.marcar_confirmado(Comprobante.VIA_LISTA, self.usuario)
        self.comp.save()

        item = self._item()
        self.assertEqual(validar_y_emparejar(item, self.lote), "duplicado")
        item.refresh_from_db()
        self.assertIn("RUTA DISTINTA", item.aviso)
        self.assertIn("Ruta 3", item.aviso)   # la que tiene
        self.assertIn("Ruta 7", item.aviso)   # la de esta conciliación

    def test_el_aviso_no_alarma_si_la_ruta_coincide(self):
        self.comp.ruta = self.ruta
        self.comp.marcar_confirmado(Comprobante.VIA_LISTA, self.usuario)
        self.comp.save()

        item = self._item()
        self.assertEqual(validar_y_emparejar(item, self.lote), "duplicado")
        item.refresh_from_db()
        self.assertNotIn("DISTINTA", item.aviso)
        self.assertIn("Ruta 7", item.aviso)

    def test_el_aviso_avisa_cuando_no_tiene_ruta(self):
        self.comp.marcar_confirmado(Comprobante.VIA_LISTA, self.usuario)
        self.comp.save()

        item = self._item()
        validar_y_emparejar(item, self.lote)
        item.refresh_from_db()
        self.assertIn("sin ruta", item.aviso)
        self.assertIn("Ruta 7", item.aviso)

    def test_sin_confirmar_previa_si_confirma_normalmente(self):
        """El caso normal no se ve afectado por la comprobación nueva."""
        item = self._item()
        self.assertEqual(validar_y_emparejar(item, self.lote), "ok")

        self.comp.refresh_from_db()
        self.assertEqual(self.comp.estado, Comprobante.CONFIRMADO)
        self.assertEqual(self.comp.confirmado_via, Comprobante.VIA_CONCILIACION)
        self.assertEqual(self.comp.ruta_id, self.ruta.pk)


class ParseHoraTest(TestCase):
    def test_variantes_ampm_y_puntos(self):
        from core.parsing import parse_hora
        from datetime import time

        # 12h AM / PM con y sin espacios, puntos, minús/mayús
        self.assertEqual(parse_hora("11:21 AM"), time(11, 21))
        self.assertEqual(parse_hora("11:21AM"), time(11, 21))
        self.assertEqual(parse_hora("11:21 am"), time(11, 21))
        self.assertEqual(parse_hora("11:21a.m."), time(11, 21))
        self.assertEqual(parse_hora("05:43 p. m."), time(17, 43))
        self.assertEqual(parse_hora("5:43pm"), time(17, 43))
        self.assertEqual(parse_hora("11.21 a. m."), time(11, 21))
        self.assertEqual(parse_hora("11.21.05 PM"), time(23, 21, 5))

        # 24h
        self.assertEqual(parse_hora("17:32:00"), time(17, 32))
        self.assertEqual(parse_hora("17:32"), time(17, 32))
        self.assertEqual(parse_hora("11:21"), time(11, 21))

        # 12:00 AM (medianoche) y 12:00 PM (mediodía)
        self.assertEqual(parse_hora("12:00 AM"), time(0, 0))
        self.assertEqual(parse_hora("12:00 PM"), time(12, 0))



@override_settings(MEDIA_ROOT=_MEDIA_TMP)
class SubidaPorArchivoConciliarTest(TestCase):
    """Subida imagen a imagen: la ruta se aplica al cerrar el lote, no al subir."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA_TMP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Test")
        self.ruta = Ruta.objects.create(negocio=self.negocio, numero=7)
        self.user = User.objects.create_user("u1", password="x")
        PerfilUsuario.objects.create(user=self.user, negocio=self.negocio)
        self.client.force_login(self.user)

    def _subir(self, n=3):
        for i in range(n):
            r = self.client.post(reverse("conciliaciones:conciliar_archivo"),
                                 {"imagenes": _imagen(f"f{i}.jpg")})
            self.assertEqual(r.status_code, 200)

    def test_las_imagenes_se_acumulan_en_un_borrador_sin_ruta(self):
        self._subir(3)
        lote = LoteConciliacion.objects.get(estado=LoteConciliacion.BORRADOR)
        self.assertIsNone(lote.ruta)
        self.assertEqual(lote.items.count(), 3)

    def test_el_borrador_sobrevive_a_recargar_la_pagina(self):
        self._subir(2)
        r = self.client.get(reverse("conciliaciones:conciliar"))
        self.assertEqual(r.context["guardadas"], 2)

    def test_conciliar_aplica_la_ruta_al_lote_y_a_sus_items(self):
        self._subir(3)
        with patch("conciliaciones.views.procesar_conciliacion.delay") as delay:
            self.client.post(reverse("conciliaciones:conciliar"), {"ruta": self.ruta.id})
        lote = LoteConciliacion.objects.get()
        self.assertEqual((lote.estado, lote.total, lote.ruta), (LoteConciliacion.EN_COLA, 3, self.ruta))
        self.assertEqual(lote.items.filter(ruta=self.ruta).count(), 3)
        delay.assert_called_once_with(lote.id)

    def test_respaldo_sin_js_sigue_aceptando_el_post_con_los_archivos(self):
        with patch("conciliaciones.views.procesar_conciliacion.delay"):
            self.client.post(reverse("conciliaciones:conciliar"),
                             {"ruta": self.ruta.id, "imagenes": [_imagen("a.jpg"), _imagen("b.jpg")]})
        lote = LoteConciliacion.objects.get()
        self.assertEqual((lote.estado, lote.total), (LoteConciliacion.EN_COLA, 2))
        self.assertEqual(lote.items.filter(ruta=self.ruta).count(), 2)

    def test_descartar_borra_las_imagenes_pendientes(self):
        self._subir(2)
        self.client.post(reverse("conciliaciones:descartar_borrador"))
        self.assertFalse(LoteConciliacion.objects.exists())
        self.assertFalse(Conciliacion.objects.exists())

    def test_el_borrador_no_aparece_ni_en_el_historial_ni_en_el_panel(self):
        self._subir(2)
        self.assertEqual(list(self.client.get(reverse("conciliaciones:lista")).context["page"]), [])
        self.assertEqual(list(self.client.get(reverse("conciliaciones:panel")).context["page"]), [])

    def test_un_zip_se_expande_a_varias_imagenes_del_borrador(self):
        r = self.client.post(reverse("conciliaciones:conciliar_archivo"),
                             {"imagenes": _zip({"a.jpg": _bytes_jpeg(),
                                                "sub/b.png": _bytes_jpeg(),
                                                "notas.txt": b"hola"})})
        self.assertEqual(r.json()["resultados"], [{"n": 2, "omitidas": 1}])
        lote = LoteConciliacion.objects.get(estado=LoteConciliacion.BORRADOR)
        self.assertEqual(lote.items.count(), 2)

    def test_conciliar_aplica_la_ruta_tambien_a_las_imagenes_del_zip(self):
        self.client.post(reverse("conciliaciones:conciliar_archivo"),
                         {"imagenes": _zip({f"f{i}.jpg": _bytes_jpeg() for i in range(4)})})
        with patch("conciliaciones.views.procesar_conciliacion.delay"):
            self.client.post(reverse("conciliaciones:conciliar"), {"ruta": self.ruta.id})
        lote = LoteConciliacion.objects.get()
        self.assertEqual(lote.total, 4)
        self.assertEqual(lote.items.filter(ruta=self.ruta).count(), 4)

    def test_zip_danado_se_reporta_sin_crear_nada(self):
        malo = SimpleUploadedFile("roto.zip", b"no soy un zip", content_type="application/zip")
        r = self.client.post(reverse("conciliaciones:conciliar_archivo"), {"imagenes": malo})
        self.assertEqual(r.status_code, 200)
        self.assertIn("error", r.json()["resultados"][0])
        self.assertFalse(Conciliacion.objects.exists())
