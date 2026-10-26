"""
triaje_link: conecta tu software de detección (el cerebro) con el controlador
de trampillas (el músculo).

Tu programa solo tiene que hacer tres cosas:
    ctl = Controlador("/dev/ttyUSB0")     # o "COM3" en Windows, o "tcp://127.0.0.1:5555" con el simulador
    ctl.vivo()                            # en cada vuelta de tu bucle de detección
    ctl.expulsar(carril, cuenta_ref)      # por cada fruta mala

La idea clave: no le digas al controlador "abre AHORA" (el PC tiene retrasos
impredecibles). Dile "la fruta que estaba en la línea de referencia de la cámara
cuando el encoder marcaba N es mala". El controlador sabe cuánto falta hasta la
trampilla y la abre en el momento exacto, vaya la cinta a la velocidad que vaya.
"""
from __future__ import annotations

import collections
import itertools
import queue
import socket
import threading
import time

MASCARA = 0xFFFFFFFF  # el controlador cuenta con 32 bits sin signo


class ErrorControlador(Exception):
    pass


class Controlador:
    """Conexión con el controlador de trampillas por USB-serie o TCP (simulador)."""

    def __init__(self, destino: str, baudios: int = 115200, ping_cada: float = 0.1,
                 vivo_max: float = 0.3, al_evento=None):
        """
        destino:   puerto serie ("/dev/ttyUSB0", "COM3") o "tcp://host:puerto".
        ping_cada: cada cuánto se envía el latido al controlador (segundos).
        vivo_max:  si tu bucle no llama a vivo() en este tiempo, se dejan de
                   enviar latidos y el controlador hace una parada segura.
        al_evento: función opcional f(tipo, id_orden, texto) que recibe
                   DONE, LATE, FULL y ERR.
        """
        self._lock_tx = threading.Lock()
        self._lock_orden = threading.Lock()  # una orden con respuesta cada vez (panel y detector comparten conexión)
        self._abrir(destino, baudios)
        self.ping_cada = ping_cada
        self.vivo_max = vivo_max
        self.al_evento = al_evento

        self.trampillas = [False] * 4           # estado real de cada trampilla (lo avisa el controlador)
        self.cuenta: int | None = None          # última cuenta conocida del encoder
        self.cuenta_recibida_en = 0.0           # time.monotonic() de esa cuenta
        self._fotos: "queue.Queue[tuple[int, int]]" = queue.Queue(maxsize=200)
        self._respuestas: "queue.Queue[str]" = queue.Queue()
        self._ids = itertools.count(1)
        self.pendientes: dict[int, dict] = {}   # órdenes enviadas y aún no terminadas
        self.estadisticas = collections.Counter()
        self._ultimo_vivo = time.monotonic()
        self._fin = threading.Event()
        self._listo = threading.Event()

        threading.Thread(target=self._bucle_lectura, daemon=True).start()
        if not self._listo.wait(4.0):
            # Algunas placas no se reinician al abrir el puerto: comprobamos con un PING.
            self._enviar("PING")
            if not self._listo.wait(1.0):
                self.cerrar()
                raise ErrorControlador("El controlador no responde. Revisa el cable y el puerto.")
        threading.Thread(target=self._bucle_latido, daemon=True).start()
        # Empezar limpio: órdenes de una sesión anterior podrían tener los mismos ids.
        self._orden("CLEAR")

    # ------------------------------------------------------------------ API

    def vivo(self) -> None:
        """Llámalo en cada vuelta de tu bucle de detección.
        Si tu programa se cuelga, deja de llamarse, se dejan de enviar latidos
        y el controlador para la cinta y cierra las trampillas."""
        self._ultimo_vivo = time.monotonic()

    def marcha(self, en_marcha: bool) -> None:
        """Arranca o para la cinta."""
        self.vivo()
        self._enviar("PING")
        self._orden(f"RUN {1 if en_marcha else 0}")

    def expulsar(self, carril: int, cuenta_ref: int, info: dict | None = None) -> int:
        """Ordena expulsar la fruta del carril `carril` (0 = primero) que estaba en la
        línea de referencia de la cámara cuando el encoder marcaba `cuenta_ref`.
        Devuelve el id de la orden. La respuesta llega después como evento:
        DONE (expulsada), LATE (llegó tarde, la fruta ya pasó) o FULL (cola llena)."""
        id_orden = next(self._ids) & MASCARA
        self.pendientes[id_orden] = {"carril": carril, "cuenta": cuenta_ref & MASCARA,
                                     "enviada": time.monotonic(), **(info or {})}
        self._enviar(f"EJ {id_orden} {carril} {cuenta_ref & MASCARA}")
        self.estadisticas["enviadas"] += 1
        return id_orden

    def esperar_foto(self, timeout: float = 1.0) -> tuple[int, int] | None:
        """Con disparo hardware: espera la siguiente foto y devuelve (num_foto, cuenta)
        con la cuenta exacta del encoder en el instante del disparo."""
        try:
            return self._fotos.get(timeout=timeout)
        except queue.Empty:
            return None

    def cuenta_ahora(self) -> int | None:
        """Sin disparo hardware: cuenta estimada en este instante.
        Es menos precisa (la cuenta llega cada 20 ms), úsala solo para pruebas."""
        return self.cuenta

    def configurar(self, offsets=None, pre=None, post=None, disparo_cada=None,
                   max_abierta_ms=None, watchdog_ms=None) -> None:
        """Envía la configuración al controlador. Todos los valores en cuentas del encoder
        salvo los que acaban en _ms."""
        if offsets is not None:
            for carril, valor in enumerate(offsets):
                self._orden(f"SET OFFSET {carril} {int(valor)}")
        if pre is not None:
            self._orden(f"SET PRE {int(pre)}")
        if post is not None:
            self._orden(f"SET POST {int(post)}")
        if disparo_cada is not None:
            self._orden(f"SET TRIG {int(disparo_cada)}")
        if max_abierta_ms is not None:
            self._orden(f"SET MAXMS {int(max_abierta_ms)}")
        if watchdog_ms is not None:
            self._orden(f"SET WD {int(watchdog_ms)}")

    def probar_trampilla(self, carril: int) -> None:
        """Abre la trampilla un momento para comprobar el cableado."""
        self._orden(f"TEST {carril}")

    def modo_manual(self, manual: bool) -> None:
        """Cambia entre automático y manual. En los dos casos el controlador para la cinta.
        En manual rechaza las órdenes del detector (ERR MANUAL) y acepta trampilla()."""
        self._orden("MODE MAN" if manual else "MODE AUTO")

    def trampilla(self, carril: int, abierta: bool) -> None:
        """Solo en manual: abre o cierra una trampilla (se cierra sola a los 10 s)."""
        self._orden(f"DOOR {carril} {1 if abierta else 0}")

    def velocidad(self, porcentaje: int) -> None:
        """Consigna de velocidad de la cinta para el variador, de 0 a 100 %."""
        self._orden(f"SPEED {int(porcentaje)}")

    def borrar_ordenes(self) -> None:
        self._orden("CLEAR")
        self.pendientes.clear()

    def estado(self) -> dict:
        """Pregunta al controlador: en marcha, cuenta, modo, velocidad, órdenes en cola
        y trampillas abiertas."""
        resp = self._orden("ST", espera="ST")
        datos = dict(p.split("=", 1) for p in resp.split()[1:] if "=" in p)
        return {"en_marcha": datos.get("run") == "1",
                "cuenta": int(datos.get("cuenta", 0)),
                "manual": datos.get("modo") == "MAN",
                "velocidad": int(datos.get("v", 0)),
                "cola": [int(x) for x in datos.get("q", "").split(",") if x],
                "trampillas": [ch == "1" for ch in datos.get("d", "")]}

    def cerrar(self) -> None:
        self._fin.set()
        try:
            if self._es_tcp:
                self._sock.close()
            else:
                self._ser.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.marcha(False)
        except Exception:
            pass
        self.cerrar()

    # ------------------------------------------------------------ interno

    def _abrir(self, destino: str, baudios: int) -> None:
        self._es_tcp = destino.startswith("tcp://")
        if self._es_tcp:
            host, puerto = destino[6:].rsplit(":", 1)
            self._sock = socket.create_connection((host, int(puerto)), timeout=3)
            self._sock.settimeout(0.2)
            self._buf = b""
        else:
            import serial  # pip install pyserial
            self._ser = serial.Serial(destino, baudios, timeout=0.2)

    def _leer_linea(self) -> str | None:
        if self._es_tcp:
            while b"\n" not in self._buf:
                try:
                    trozo = self._sock.recv(4096)
                except socket.timeout:
                    return None
                if not trozo:
                    raise ConnectionError("conexión cerrada")
                self._buf += trozo
            linea, self._buf = self._buf.split(b"\n", 1)
        else:
            linea = self._ser.readline()
            if not linea:
                return None
        return linea.decode("ascii", "replace").strip()

    def _enviar(self, texto: str) -> None:
        datos = (texto + "\n").encode("ascii")
        with self._lock_tx:
            if self._es_tcp:
                self._sock.sendall(datos)
            else:
                self._ser.write(datos)

    def _orden(self, texto: str, espera: str = "OK", timeout: float = 1.0) -> str:
        """Envía una orden y espera su respuesta (OK, ST...) o un ERR."""
        with self._lock_orden:
            while not self._respuestas.empty():
                self._respuestas.get_nowait()
            self._enviar(texto)
            limite = time.monotonic() + timeout
            while time.monotonic() < limite:
                try:
                    resp = self._respuestas.get(timeout=max(0.01, limite - time.monotonic()))
                except queue.Empty:
                    break
                if resp.startswith(espera):
                    return resp
                if resp.startswith("ERR"):
                    raise ErrorControlador(f"{texto!r} -> {resp}")
            raise ErrorControlador(f"Sin respuesta a {texto!r}")

    def _evento(self, tipo: str, id_orden: int | None, texto: str) -> None:
        self.estadisticas[tipo] += 1
        if self.al_evento:
            try:
                self.al_evento(tipo, id_orden, texto)
            except Exception as e:  # un fallo en tu función no debe tumbar la conexión
                print("al_evento falló:", e)

    def _bucle_lectura(self) -> None:
        while not self._fin.is_set():
            try:
                linea = self._leer_linea()
            except Exception as e:
                if not self._fin.is_set():
                    self._evento("ERR", None, f"conexión perdida: {e}")
                return
            if not linea:
                continue
            partes = linea.split()
            tipo = partes[0]
            if tipo in ("C", "PONG") and len(partes) > 1:
                self.cuenta = int(partes[1])
                self.cuenta_recibida_en = time.monotonic()
                self._listo.set()
            elif tipo == "READY":
                self._listo.set()
            elif tipo == "D" and len(partes) > 2:
                c = int(partes[1])
                if 0 <= c < len(self.trampillas):
                    self.trampillas[c] = partes[2] == "1"
                self._evento("D", None, linea)
            elif tipo == "F" and len(partes) > 2:
                try:
                    self._fotos.put_nowait((int(partes[1]), int(partes[2])))
                except queue.Full:
                    pass
            elif tipo == "ACK":
                # Recibida. Si trae un segundo id, era la misma fruta que otra orden ya en cola
                # y se ha fusionado con ella: su resultado llegará con el id de esa otra orden.
                if len(partes) > 2:
                    self.pendientes.pop(int(partes[1]), None)
                    self.estadisticas["fusionadas"] += 1
            elif tipo in ("DONE", "LATE", "FULL"):
                id_orden = int(partes[1]) if len(partes) > 1 else None
                self.pendientes.pop(id_orden, None)
                self._evento(tipo, id_orden, linea)
            elif tipo == "ERR":
                asincrono = len(partes) > 1 and partes[1] in ("WATCHDOG", "TIEMPO_MANUAL")
                id_orden = (int(partes[2]) if not asincrono and len(partes) > 2 and partes[2].isdigit()
                            else None)
                if id_orden is not None:
                    self.pendientes.pop(id_orden, None)
                elif not asincrono:
                    self._respuestas.put(linea)  # error de una orden que estamos esperando
                self._evento("ERR", id_orden, linea)
            else:  # OK, ST...
                self._respuestas.put(linea)

    def _bucle_latido(self) -> None:
        while not self._fin.is_set():
            if time.monotonic() - self._ultimo_vivo <= self.vivo_max:
                try:
                    self._enviar("PING")
                except Exception:
                    return
            time.sleep(self.ping_cada)


class Calibracion:
    """Pasa de píxeles de la imagen a carril y cuenta del encoder.

    x_ref_px:          columna de la imagen que corresponde a la línea de referencia
                       (la misma desde la que mides el offset a cada trampilla).
    cuentas_por_px:    cuentas del encoder que avanza la cinta por cada píxel.
    limites_carril_px: filas de la imagen que separan los carriles, de borde a borde.
                       Para 4 carriles: [y0, y1, y2, y3, y4].
    sentido:           +1 si la fruta avanza hacia x crecientes en la imagen, -1 si no.
    """

    def __init__(self, x_ref_px: float, cuentas_por_px: float,
                 limites_carril_px: list[float], sentido: int = 1):
        self.x_ref_px = x_ref_px
        self.cuentas_por_px = cuentas_por_px
        self.limites = sorted(limites_carril_px)
        self.sentido = sentido

    def carril(self, y_px: float) -> int | None:
        for i in range(len(self.limites) - 1):
            if self.limites[i] <= y_px < self.limites[i + 1]:
                return i
        return None  # fuera de los carriles

    def cuenta_referencia(self, cuenta_foto: int, x_px: float) -> int:
        """Cuenta del encoder a la que esta fruta pasó (o pasará) por la línea de referencia.
        Una fruta que en la foto ya está más adelante de la línea pasó antes por ella."""
        avance = (x_px - self.x_ref_px) * self.sentido * self.cuentas_por_px
        return int(round(cuenta_foto - avance)) & MASCARA


class Antiduplicados:
    """La misma fruta sale en varias fotos seguidas. Esto evita mandar varias órdenes
    para ella. (El controlador también fusiona órdenes solapadas, así que es una
    segunda protección.)"""

    def __init__(self, tolerancia_cuentas: int = 80, memoria: int = 400):
        self.tol = tolerancia_cuentas
        self.recientes: collections.deque = collections.deque(maxlen=memoria)

    def nuevo(self, carril: int, cuenta_ref: int) -> bool:
        for c, ref in self.recientes:
            d = ((cuenta_ref - ref + 2**31) & MASCARA) - 2**31  # diferencia con signo de 32 bits
            if c == carril and abs(d) <= self.tol:
                return False
        self.recientes.append((carril, cuenta_ref))
        return True
