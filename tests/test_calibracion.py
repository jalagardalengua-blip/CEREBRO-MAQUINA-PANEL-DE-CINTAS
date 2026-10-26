"""Cálculos puros: píxeles -> carril y cuenta, y filtro de duplicados (incluido el desbordamiento de 32 bits)."""
import unittest

import utilidades  # noqa: F401  (añade software/ al path)
from triaje_link import MASCARA, Antiduplicados, Calibracion


class TestCalibracion(unittest.TestCase):
    def setUp(self):
        self.cal = Calibracion(x_ref_px=640, cuentas_por_px=2.5, limites_carril_px=[0, 180, 360, 540, 720])

    def test_carril_por_fila(self):
        self.assertEqual(self.cal.carril(10), 0)
        self.assertEqual(self.cal.carril(200), 1)
        self.assertEqual(self.cal.carril(719), 3)

    def test_fuera_de_carriles(self):
        self.assertIsNone(self.cal.carril(-1))
        self.assertIsNone(self.cal.carril(720))

    def test_fruta_por_delante_de_la_linea_paso_antes(self):
        # 100 px por delante de la referencia = 250 cuentas antes
        self.assertEqual(self.cal.cuenta_referencia(10000, 740), 9750)

    def test_fruta_por_detras_pasara_despues(self):
        self.assertEqual(self.cal.cuenta_referencia(10000, 540), 10250)

    def test_sentido_invertido(self):
        cal = Calibracion(640, 2.5, [0, 720], sentido=-1)
        self.assertEqual(cal.cuenta_referencia(10000, 740), 10250)

    def test_desbordamiento_32_bits(self):
        self.assertEqual(self.cal.cuenta_referencia(100, 740), (100 - 250) & MASCARA)


class TestAntiduplicados(unittest.TestCase):
    def test_misma_fruta_en_dos_fotos(self):
        d = Antiduplicados(tolerancia_cuentas=80)
        self.assertTrue(d.nuevo(0, 5000))
        self.assertFalse(d.nuevo(0, 5040))

    def test_otro_carril_es_otra_fruta(self):
        d = Antiduplicados(tolerancia_cuentas=80)
        self.assertTrue(d.nuevo(0, 5000))
        self.assertTrue(d.nuevo(1, 5000))

    def test_lejos_es_otra_fruta(self):
        d = Antiduplicados(tolerancia_cuentas=80)
        self.assertTrue(d.nuevo(0, 5000))
        self.assertTrue(d.nuevo(0, 5200))

    def test_duplicado_a_traves_del_desbordamiento(self):
        d = Antiduplicados(tolerancia_cuentas=80)
        self.assertTrue(d.nuevo(0, 0xFFFFFFF0))
        self.assertFalse(d.nuevo(0, 10))


if __name__ == "__main__":
    unittest.main()
