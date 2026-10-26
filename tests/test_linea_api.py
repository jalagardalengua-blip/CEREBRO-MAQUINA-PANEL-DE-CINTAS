"""Servicio de línea: API del panel en modo automático y manual, contra el simulador."""
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from utilidades import SimuladorEnHilo
import linea
from triaje_link import Controlador

PIN = "4821"


class TestLineaAPI(unittest.TestCase):
    def setUp(self):
        self.simulador = SimuladorEnHilo(vel_cps=2000)
        self.ctl = Controlador(self.simulador.destino)
        self.linea = linea.Linea(self.ctl, demo=True, pin=PIN)
        self.srv = linea.crear_servidor(self.linea, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.linea.detener()
        self.ctl.cerrar()
        self.simulador.__exit__()

    # ---------------- ayudas ----------------
    def post(self, accion, datos=None):
        req = urllib.request.Request(f"{self.base}/api/{accion}", data=json.dumps(datos or {}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def estado(self):
        with urllib.request.urlopen(f"{self.base}/api/estado", timeout=3) as r:
            return json.load(r)

    def entrar_en_manual(self):
        codigo, r = self.post("modo", {"modo": "manual", "pin": PIN, "nombre": "Pepe"})
        self.assertEqual(codigo, 200, r)

    # ---------------- tests ----------------
    def test_sirve_el_panel(self):
        with urllib.request.urlopen(self.base + "/", timeout=3) as r:
            html = r.read().decode()
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("Mando de línea", html)

    def test_arranca_en_automatico_y_parado(self):
        e = self.estado()
        self.assertEqual(e["modo"], "automatico")
        self.assertFalse(e["en_marcha"])

    def test_marcha_y_paro_en_automatico(self):
        self.assertEqual(self.post("marcha", {"on": True})[0], 200)
        self.assertTrue(self.estado()["en_marcha"])
        self.assertEqual(self.post("parar")[0], 200)
        self.assertFalse(self.estado()["en_marcha"])

    def test_en_automatico_no_se_tocan_trampillas(self):
        codigo, r = self.post("trampilla", {"carril": 0, "abierta": True})
        self.assertEqual(codigo, 409)
        self.assertIn("manual", r["error"])

    def test_pin_incorrecto(self):
        codigo, r = self.post("modo", {"modo": "manual", "pin": "0000", "nombre": "Pepe"})
        self.assertEqual(codigo, 409)
        self.assertEqual(self.estado()["modo"], "automatico")

    def test_manual_para_la_cinta_y_registra_responsable(self):
        self.post("marcha", {"on": True})
        self.entrar_en_manual()
        e = self.estado()
        self.assertEqual(e["modo"], "manual")
        self.assertEqual(e["responsable"], "Pepe")
        self.assertFalse(e["en_marcha"])

    def test_en_manual_no_hay_marcha_continua(self):
        self.entrar_en_manual()
        self.assertEqual(self.post("marcha", {"on": True})[0], 409)

    def test_trampilla_a_mano(self):
        self.entrar_en_manual()
        self.assertEqual(self.post("trampilla", {"carril": 2, "abierta": True})[0], 200)
        time.sleep(0.2)
        self.assertTrue(self.estado()["trampillas"][2])
        self.post("trampilla", {"carril": 2, "abierta": False})
        time.sleep(0.2)
        self.assertFalse(self.estado()["trampillas"][2])

    def test_hombre_muerto(self):
        self.entrar_en_manual()
        for _ in range(4):  # el panel renueva cada 150 ms mientras se mantiene pulsado
            self.assertEqual(self.post("jog")[0], 200)
            time.sleep(0.15)
        self.assertTrue(self.estado()["en_marcha"])
        time.sleep(linea.JOG_MAX_S + 0.4)  # se suelta: se debe parar sola
        self.assertFalse(self.estado()["en_marcha"])

    def test_vuelta_a_automatico_cierra_todo(self):
        self.entrar_en_manual()
        self.post("trampilla", {"carril": 1, "abierta": True})
        self.assertEqual(self.post("modo", {"modo": "automatico"})[0], 200)
        time.sleep(0.2)
        e = self.estado()
        self.assertEqual(e["modo"], "automatico")
        self.assertFalse(any(e["trampillas"]))
        self.assertFalse(e["en_marcha"])

    def test_produccion_cuenta_y_expulsa(self):
        self.post("marcha", {"on": True})
        limite = time.monotonic() + 6
        while time.monotonic() < limite and self.estado()["contadores"]["expulsadas"] == 0:
            time.sleep(0.2)
        c = self.estado()["contadores"]
        self.assertGreater(c["inspeccionadas"], 0)
        self.assertGreater(c["expulsadas"], 0)

    def test_accion_desconocida(self):
        self.assertEqual(self.post("volar")[0], 409)


if __name__ == "__main__":
    unittest.main()
