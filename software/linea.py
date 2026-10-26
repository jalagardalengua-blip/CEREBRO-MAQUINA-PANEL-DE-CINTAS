"""
Servicio de línea: el único programa que habla con la placa.

Une en un solo proceso:
    · tu detector (mi_detector.py), que en AUTOMÁTICO decide qué fruta se expulsa,
    · la placa de las trampillas (a través de triaje_link),
    · el panel de control web (panel/index.html), con modo AUTOMÁTICO y MANUAL.

Hace falta un solo programa porque el puerto USB solo lo puede abrir uno a la vez.

Uso:
    python simulador.py                                  # sin hardware (otra terminal)
    python linea.py --demo                               # detecciones inventadas
    python linea.py --destino COM3 --pin 4821            # con la placa y tu detector

Y abre el panel en  http://localhost:8080
Para usarlo desde una tableta en la misma red:  python linea.py --red   (y abre http://<ip-del-pc>:8080)
"""
import argparse
import collections
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config_linea as cfg
import mi_detector
from triaje_link import Antiduplicados, Controlador, ErrorControlador

CARPETA_PANEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel")
JOG_MAX_S = 0.4  # hombre muerto: si el panel deja de mantener pulsado, la cinta se para


class Rechazo(Exception):
    """Acción no permitida en el estado actual. El texto se muestra en el panel."""


class Linea:
    def __init__(self, ctl: Controlador, demo: bool, pin: str):
        self.ctl = ctl
        self.demo = demo
        self.pin = pin
        self.lock = threading.RLock()
        self.manual = False
        self.en_marcha = False
        self.velocidad = cfg.VELOCIDAD_INICIAL
        self.alarma = None
        self.responsable_manual = None
        self.eventos = collections.deque(maxlen=80)
        self.cont = collections.Counter()
        self.jog_activo = False
        self.ultimo_jog = 0.0
        self.estado_placa = {}
        self._fin = threading.Event()
        self._vistas = Antiduplicados(tolerancia_cuentas=80)  # para contar cada fruta una sola vez
        self._malas = Antiduplicados(tolerancia_cuentas=80)

        ctl.al_evento = self._evento_placa
        ctl.configurar(offsets=cfg.OFFSETS_CARRIL, pre=cfg.PRE, post=cfg.POST,
                       disparo_cada=cfg.DISPARO_CADA)
        ctl.modo_manual(False)
        ctl.velocidad(self.velocidad)
        self.registrar("Servicio arrancado en modo automático")

        for objetivo in (self._bucle_deteccion, self._bucle_hombre_muerto, self._bucle_estado):
            threading.Thread(target=objetivo, daemon=True).start()

    def detener(self):
        """Para la cinta y los hilos del servicio. La conexión con la placa la cierra quien la abrió."""
        try:
            self.ctl.marcha(False)
        except Exception:
            pass
        self._fin.set()

    # ------------------------------------------------------------ registro

    def registrar(self, texto, nivel="info"):
        self.eventos.appendleft({"hora": time.strftime("%H:%M:%S"), "texto": texto, "nivel": nivel})
        print(f"{time.strftime('%H:%M:%S')} [{nivel}] {texto}")

    def _evento_placa(self, tipo, id_orden, texto):
        if tipo == "DONE":
            self.cont["expulsadas"] += 1
        elif tipo == "LATE":
            self.cont["tarde"] += 1
            self.registrar("Una fruta mala pasó antes de que llegara la orden. Revisa la latencia del detector.", "aviso")
        elif tipo == "FULL":
            self.registrar(f"Cola de órdenes llena en la placa (orden {id_orden})", "aviso")
        elif tipo == "ERR":
            # Sin self.lock aquí: este aviso llega por el hilo que entrega las respuestas de la placa,
            # y una acción del panel puede estar esperando una de ellas con el candado cogido.
            if "WATCHDOG" in texto:
                self.en_marcha = False
                self.jog_activo = False
                self.alarma = "El detector dejó de responder. La cinta se ha parado sola."
                self.registrar(self.alarma, "alarma")
            elif "TIEMPO_MANUAL" in texto:
                c = texto.split()[-1]
                self.registrar(f"Trampilla {int(c) + 1} cerrada sola tras 10 s abierta", "aviso")
            elif "MANUAL" in texto:
                pass  # orden del detector rechazada por estar en manual: normal
            elif "conexión perdida" in texto:
                self.en_marcha = False
                self.alarma = "Se ha perdido la conexión con la placa."
                self.registrar(self.alarma, "alarma")
            else:
                self.registrar(f"Placa: {texto}", "aviso")

    # ------------------------------------------------------------ bucles

    def _bucle_deteccion(self):
        while not self._fin.is_set():
            self.ctl.vivo()  # latido: si este bucle se cuelga, la placa para la cinta
            foto = self.ctl.esperar_foto(timeout=0.2)
            if foto is None:
                continue
            num_foto, cuenta_foto = foto
            try:
                imagen = mi_detector.capturar_imagen(num_foto)
                frutas = mi_detector.detectar(imagen, demo=self.demo)
            except Exception as e:
                self.registrar(f"Error en el detector: {e}", "alarma")
                time.sleep(1)
                continue
            for f in frutas:
                carril = cfg.CAL.carril(f["y"])
                if carril is None:
                    continue
                ref = cfg.CAL.cuenta_referencia(cuenta_foto, f["x"])
                if self._vistas.nuevo(carril, ref):
                    self.cont["inspeccionadas"] += 1
                dudosa = f["confianza"] < cfg.CONFIANZA_MINIMA
                if not f["mala"] and not dudosa:
                    continue
                if not self._malas.nuevo(carril, ref):
                    continue
                self.cont["malas" if f["mala"] else "dudosas"] += 1
                if self.manual:
                    continue  # en manual el detector mira pero no manda
                try:
                    self.ctl.expulsar(carril, ref, info={"foto": num_foto, "defecto": f.get("defecto")})
                except Exception as e:
                    self.registrar(f"No se pudo enviar la orden: {e}", "alarma")

    def _bucle_hombre_muerto(self):
        while not self._fin.is_set():
            time.sleep(0.05)
            with self.lock:
                if self.jog_activo and time.monotonic() - self.ultimo_jog > JOG_MAX_S:
                    self.jog_activo = False
                    try:
                        self.ctl.marcha(False)
                    except Exception:
                        pass

    def _bucle_estado(self):
        while not self._fin.is_set():
            try:
                self.estado_placa = self.ctl.estado()
            except Exception:  # placa ocupada o desconectada: se reintenta
                pass
            self._fin.wait(0.5)

    # ------------------------------------------------------------ acciones del panel

    def _solo_manual(self):
        if not self.manual:
            raise Rechazo("Esta acción solo está disponible en modo manual.")

    def accion(self, nombre, datos):
        try:
            return self._accion(nombre, datos)
        finally:
            if nombre not in ("jog", "velocidad"):
                try:
                    self.estado_placa = self.ctl.estado()  # que el panel vea el cambio al instante
                except ErrorControlador:
                    pass

    def _accion(self, nombre, datos):
        with self.lock:
            if nombre == "modo":
                return self._cambiar_modo(datos)
            if nombre == "marcha":
                if self.manual:
                    raise Rechazo("En manual la cinta se mueve con el botón de mantener pulsado.")
                if datos.get("on") and self.alarma:
                    raise Rechazo("Hay una alarma activa. Revisa la causa y pulsa Rearmar.")
                self.ctl.marcha(bool(datos.get("on")))
                self.en_marcha = bool(datos.get("on"))
                self.registrar("Cinta en marcha" if self.en_marcha else "Cinta parada")
                return
            if nombre == "parar":  # siempre permitido
                self.jog_activo = False
                self.ctl.marcha(False)
                self.en_marcha = False
                self.registrar("Cinta parada desde el panel")
                return
            if nombre == "jog":
                self._solo_manual()
                if self.alarma:
                    raise Rechazo("Hay una alarma activa. Pulsa Rearmar primero.")
                self.ultimo_jog = time.monotonic()
                if not self.jog_activo:
                    self.ctl.marcha(True)
                    self.jog_activo = True
                return
            if nombre == "jog_fin":
                if self.jog_activo:
                    self.jog_activo = False
                    self.ctl.marcha(False)
                return
            if nombre == "trampilla":
                self._solo_manual()
                c, abierta = int(datos["carril"]), bool(datos["abierta"])
                self.ctl.trampilla(c, abierta)
                self.registrar(f"Trampilla {c + 1} {'abierta' if abierta else 'cerrada'} a mano")
                return
            if nombre == "probar":
                self._solo_manual()
                c = int(datos["carril"])
                self.ctl.probar_trampilla(c)
                self.registrar(f"Prueba de trampilla {c + 1}")
                return
            if nombre == "velocidad":
                v = max(0, min(100, int(datos["valor"])))
                self.ctl.velocidad(v)
                self.velocidad = v
                return
            if nombre == "rearmar":
                if self.alarma:
                    self.registrar("Alarma rearmada")
                self.alarma = None
                return
            if nombre == "contadores_a_cero":
                self.cont.clear()
                self.registrar("Contadores a cero")
                return
            raise Rechazo(f"Acción desconocida: {nombre}")

    def _cambiar_modo(self, datos):
        quiere_manual = datos.get("modo") == "manual"
        if quiere_manual == self.manual:
            return
        if quiere_manual:
            if str(datos.get("pin", "")) != self.pin:
                self.registrar("Intento de pasar a manual con PIN incorrecto", "aviso")
                raise Rechazo("PIN incorrecto.")
            nombre = (datos.get("nombre") or "sin nombre").strip()[:40]
            self.ctl.modo_manual(True)
            self.manual, self.en_marcha, self.jog_activo = True, False, False
            self.responsable_manual = nombre
            self.registrar(f"Modo MANUAL · responsable: {nombre}. Cinta parada, detector sin mando.", "aviso")
        else:
            self.ctl.modo_manual(False)
            self.manual, self.en_marcha, self.jog_activo = False, False, False
            self.registrar(f"Vuelta a AUTOMÁTICO (manual de {self.responsable_manual}). Pulsa Arrancar.")
            self.responsable_manual = None

    def estado(self):
        st = self.estado_placa
        return {
            "conectado": True,
            "demo": self.demo,
            "modo": "manual" if self.manual else "automatico",
            "responsable": self.responsable_manual,
            "en_marcha": bool(st.get("en_marcha", self.en_marcha)),
            "velocidad": self.velocidad,
            "cuenta": self.ctl.cuenta,
            "trampillas": list(self.ctl.trampillas),
            "cola": st.get("cola", [0] * cfg.N_CARRILES),
            "alarma": self.alarma,
            "contadores": {k: self.cont[k] for k in ("inspeccionadas", "malas", "dudosas", "expulsadas", "tarde")},
            "eventos": list(self.eventos)[:30],
        }


def crear_servidor(linea: Linea, host: str, puerto: int):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, codigo, obj):
            datos = json.dumps(obj).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                with open(os.path.join(CARPETA_PANEL, "index.html"), "rb") as f:
                    datos = (b'<!doctype html><html lang="es"><head><meta charset="utf-8">'
                             b'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                             b'</head><body>' + f.read() + b'</body></html>')
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)
            elif self.path == "/api/estado":
                self._json(200, linea.estado())
            else:
                self._json(404, {"ok": False, "error": "No encontrado"})

        def do_POST(self):
            if not self.path.startswith("/api/"):
                return self._json(404, {"ok": False, "error": "No encontrado"})
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                datos = json.loads(self.rfile.read(largo) or b"{}")
                linea.accion(self.path[5:], datos)
                self._json(200, {"ok": True})
            except Rechazo as e:
                self._json(409, {"ok": False, "error": str(e)})
            except ErrorControlador as e:
                self._json(502, {"ok": False, "error": f"La placa no aceptó la orden ({e})"})
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                self._json(400, {"ok": False, "error": f"Petición incorrecta: {e}"})

    return ThreadingHTTPServer((host, puerto), Manejador)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="tcp://127.0.0.1:5555", help="puerto de la placa o tcp:// del simulador")
    ap.add_argument("--demo", action="store_true", help="detecciones inventadas en lugar de tu modelo")
    ap.add_argument("--pin", default=cfg.PIN_MANUAL, help="PIN para pasar a modo manual")
    ap.add_argument("--puerto", type=int, default=8080)
    ap.add_argument("--red", action="store_true", help="aceptar conexiones de otros equipos (tableta)")
    args = ap.parse_args()

    try:
        ctl = Controlador(args.destino)
    except Exception as e:  # puerto inexistente, ocupado por otro programa, placa sin firmware...
        print(f"\nNo se puede conectar con la placa en {args.destino}: {e}\n"
              "Comprueba que el cable USB está conectado, que el puerto es el correcto "
              "(en Windows: buscar_puerto_windows.bat) y que ningún otro programa lo tiene abierto, "
              "por ejemplo el monitor serie del IDE de Arduino.")
        raise SystemExit(1)
    linea = Linea(ctl, args.demo, args.pin)
    host = "0.0.0.0" if args.red else "127.0.0.1"
    srv = crear_servidor(linea, host, args.puerto)
    print(f"Panel en http://localhost:{args.puerto}" + ("  (abierto a la red local)" if args.red else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        linea.detener()
        ctl.cerrar()


if __name__ == "__main__":
    main()
