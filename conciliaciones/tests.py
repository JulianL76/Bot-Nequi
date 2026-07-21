from datetime import date
from django.test import TestCase
from accounts.models import Negocio
from comprobantes.models import Comprobante, Ruta
from conciliaciones.models import Conciliacion, LoteConciliacion
from conciliaciones.tasks import validar_y_emparejar, _comp_candidato


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

