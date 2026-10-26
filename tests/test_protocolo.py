"""Protocolo cerebro <-> placa contra el simulador: órdenes, tarde, fusión, watchdog y modo manual."""
import time
import unittest

from utilidades import SimuladorEnHilo
from triaje_link import Controlador, ErrorControlador


def esperar(condicion, segundos=3.0, ctl=None):
    """Espera a que se cumpla `condicion()`, manteniendo vivo el latido."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if ctl:
            ctl.vivo()
        if condicion():
            return True
        time.sleep(0.05)
    return False


class TestProtocolo(unittest.TestCase):
    def setUp(self):
        self.simulador = SimuladorEnHilo(vel_cps=2000)
        self.eventos = []
        self.ctl = Controlador(self.simulador.destino,
                               al_evento=lambda t, i, s: self.eventos.append((t, i, s)))
        self.ctl.configurar(offsets=[1000] * 4, pre=40, post=60, disparo_cada=0)
        self.ctl.modo_manual(False)

    def tearDown(self):
        try:
            self.ctl.marcha(False)
        except Exception:
            pass
        self.ctl.cerrar()
        self.simulador.__exit__()

    def tipos(self, id_orden):
        return [t for t, i, _ in self.eventos if i == id_orden]

    def arrancar(self):
        self.ctl.marcha(True)
        self.assertTrue(esperar(lambda: self.ctl.cuenta_ahora() is not None, ctl=self.ctl))

    def test_orden_a_tiempo_se_ejecuta(self):
        self.arrancar()
        id_orden = self.ctl.expulsar(1, self.ctl.cuenta_ahora())
        self.assertTrue(esperar(lambda: "DONE" in self.tipos(id_orden), ctl=self.ctl))
        self.assertNotIn(id_orden, self.ctl.pendientes)

    def test_la_trampilla_se_abre_y_se_cierra(self):
        self.arrancar()
        abiertas = []
        self.ctl.al_evento = lambda t, i, s: (self.eventos.append((t, i, s)),
                                              abiertas.append(s) if t == "D" else None)
        self.ctl.expulsar(2, self.ctl.cuenta_ahora())
        self.assertTrue(esperar(lambda: "D 2 1" in abiertas and "D 2 0" in abiertas, ctl=self.ctl))

    def test_orden_tardia_responde_late(self):
        self.arrancar()
        id_orden = self.ctl.expulsar(0, self.ctl.cuenta_ahora() - 5000)
        self.assertTrue(esperar(lambda: "LATE" in self.tipos(id_orden), ctl=self.ctl))

    def test_misma_fruta_se_fusiona(self):
        self.arrancar()
        c = self.ctl.cuenta_ahora()
        self.ctl.expulsar(1, c)
        self.ctl.expulsar(1, c + 20)
        self.assertTrue(esperar(lambda: self.ctl.estadisticas["fusionadas"] == 1, ctl=self.ctl))

    def test_watchdog_para_la_cinta_si_el_cerebro_se_cuelga(self):
        self.arrancar()
        time.sleep(1.0)  # sin llamar a vivo(): el latido se detiene
        self.assertTrue(any("WATCHDOG" in s for _, _, s in self.eventos))
        self.assertFalse(self.ctl.estado()["en_marcha"])

    def test_no_arranca_sin_latido(self):
        self.ctl.vivo_max = 0  # el latido no se envía nunca
        time.sleep(0.7)
        with self.assertRaises(ErrorControlador):
            self.ctl._orden("RUN 1")

    def test_manual_rechaza_al_detector(self):
        self.ctl.modo_manual(True)
        id_orden = self.ctl.expulsar(0, 123)
        self.assertTrue(esperar(lambda: any(t == "ERR" for t in self.tipos(id_orden)), ctl=self.ctl))
        self.assertTrue(self.ctl.estado()["manual"])

    def test_trampilla_a_mano_solo_en_manual(self):
        with self.assertRaises(ErrorControlador):
            self.ctl.trampilla(0, True)
        self.ctl.modo_manual(True)
        self.ctl.trampilla(0, True)
        self.assertTrue(esperar(lambda: self.ctl.trampillas[0], ctl=self.ctl))
        self.ctl.trampilla(0, False)
        self.assertTrue(esperar(lambda: not self.ctl.trampillas[0], ctl=self.ctl))

    def test_volver_a_automatico_cierra_y_para(self):
        self.ctl.modo_manual(True)
        self.ctl.trampilla(3, True)
        self.ctl.modo_manual(False)
        self.assertTrue(esperar(lambda: not self.ctl.trampillas[3], ctl=self.ctl))
        estado = self.ctl.estado()
        self.assertFalse(estado["manual"])
        self.assertFalse(estado["en_marcha"])

    def test_velocidad(self):
        self.ctl.velocidad(80)
        self.assertEqual(self.ctl.estado()["velocidad"], 80)
        self.ctl.velocidad(150)
        self.assertEqual(self.ctl.estado()["velocidad"], 100)


if __name__ == "__main__":
    unittest.main()
