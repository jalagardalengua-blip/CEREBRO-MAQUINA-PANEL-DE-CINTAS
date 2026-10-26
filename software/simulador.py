"""
Simulador del controlador de trampillas.

Habla exactamente el mismo protocolo que la placa ESP32, pero por TCP, para que
puedas probar tu software de detección sin hardware:

    python simulador.py                 # escucha en 127.0.0.1:5555
    python simulador.py --vel 3000      # cinta más rápida (cuentas por segundo)

Y en tu programa:  Controlador("tcp://127.0.0.1:5555")
"""
import argparse
import socket
import threading
import time

N_CARRILES = 4
MASCARA = 0xFFFFFFFF


def dif(a, b):
    """Diferencia con signo de 32 bits, igual que en el firmware."""
    return ((a - b + 2**31) & MASCARA) - 2**31


class ControladorSimulado:
    def __init__(self, vel_cps, verbose):
        self.vel = vel_cps
        self.verbose = verbose
        self.offset = [3000] * N_CARRILES
        self.pre, self.post = 40, 60
        self.max_ms, self.trig, self.wd_ms = 1500, 0, 500
        self.cuenta_f = 0.0
        self.en_marcha = False
        self.ordenes = [[] for _ in range(N_CARRILES)]  # dicts: id, abrir, cerrar, abierta
        self.abierta = [False] * N_CARRILES
        self.abierta_desde = [0.0] * N_CARRILES
        self.prueba_hasta = [0.0] * N_CARRILES
        self.manual = False
        self.manual_abierta = [False] * N_CARRILES
        self.vel_pct = 50              # consigna de velocidad; vel_cps corresponde al 50 %
        self.ultimo_ping = 0.0
        self.num_foto = 0
        self.prox_disparo = 0
        self.lock = threading.Lock()
        self.salida = None
        self.aperturas = 0

    @property
    def cuenta(self):
        return int(self.cuenta_f) & MASCARA

    def tx(self, texto):
        if self.salida:
            try:
                self.salida.sendall((texto + "\n").encode())
            except OSError:
                self.salida = None

    def log(self, texto):
        if self.verbose:
            print(f"{time.strftime('%H:%M:%S')} {texto}")

    # --------------- órdenes ---------------
    def procesar(self, linea):
        p = linea.split()
        if not p:
            return
        cmd = p[0]
        ahora_ms = time.monotonic() * 1000
        if cmd == "PING":
            self.ultimo_ping = ahora_ms
            self.tx(f"PONG {self.cuenta}")
        elif cmd == "EJ":
            if len(p) < 4:
                return self.tx("ERR SINTAXIS EJ")
            self.expulsar(int(p[1]), int(p[2]), int(p[3]))
        elif cmd == "RUN":
            if len(p) > 1 and p[1] == "1":
                if ahora_ms - self.ultimo_ping > self.wd_ms:
                    return self.tx("ERR SIN_PING")
                self.en_marcha = True
                self.prox_disparo = (self.cuenta + self.trig) & MASCARA
                self.log("cinta EN MARCHA")
            else:
                self.en_marcha = False
                self.log("cinta PARADA")
            self.tx("OK")
        elif cmd == "SET":
            try:
                clave = p[1]
                if clave == "OFFSET":
                    c = int(p[2])
                    if not 0 <= c < N_CARRILES:
                        raise ValueError
                    self.offset[c] = int(p[3])
                elif clave == "PRE":
                    self.pre = int(p[2])
                elif clave == "POST":
                    self.post = int(p[2])
                elif clave == "MAXMS":
                    self.max_ms = int(p[2])
                elif clave == "TRIG":
                    self.trig = int(p[2])
                    self.prox_disparo = (self.cuenta + self.trig) & MASCARA
                elif clave == "WD":
                    self.wd_ms = int(p[2])
                else:
                    return self.tx("ERR CLAVE")
            except (IndexError, ValueError):
                return self.tx("ERR SINTAXIS SET")
            self.tx("OK")
        elif cmd == "TEST":
            c = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else -1
            if not 0 <= c < N_CARRILES:
                return self.tx("ERR CARRIL")
            self.prueba_hasta[c] = ahora_ms + 300
            self.tx("OK")
        elif cmd == "MODE":
            if len(p) < 2 or p[1] not in ("MAN", "AUTO"):
                return self.tx("ERR SINTAXIS MODE")
            self.en_marcha = False
            if p[1] == "MAN":
                self.ordenes = [[] for _ in range(N_CARRILES)]
                self.manual = True
            else:
                self.manual_abierta = [False] * N_CARRILES
                self.prueba_hasta = [0.0] * N_CARRILES
                self.manual = False
            self.log(f"modo {'MANUAL' if self.manual else 'AUTOMÁTICO'}")
            self.tx("OK")
        elif cmd == "DOOR":
            if not self.manual:
                return self.tx("ERR NO_MANUAL")
            try:
                c, v = int(p[1]), int(p[2])
                if not 0 <= c < N_CARRILES:
                    raise ValueError
            except (IndexError, ValueError):
                return self.tx("ERR CARRIL")
            self.manual_abierta[c] = v == 1
            self.tx("OK")
        elif cmd == "SPEED":
            try:
                self.vel_pct = max(0, min(100, int(p[1])))
            except (IndexError, ValueError):
                return self.tx("ERR SINTAXIS SPEED")
            self.tx("OK")
        elif cmd == "CLEAR":
            self.ordenes = [[] for _ in range(N_CARRILES)]
            self.tx("OK")
        elif cmd == "ST":
            q = ",".join(str(len(o)) for o in self.ordenes)
            d = "".join("1" if a else "0" for a in self.abierta)
            self.tx(f"ST run={1 if self.en_marcha else 0} cuenta={self.cuenta} "
                    f"modo={'MAN' if self.manual else 'AUTO'} v={self.vel_pct} q={q} d={d}")
        else:
            self.tx("ERR ORDEN")

    def expulsar(self, id_orden, carril, ref):
        if not 0 <= carril < N_CARRILES:
            return self.tx(f"ERR CARRIL {id_orden}")
        if self.manual:
            return self.tx(f"ERR MANUAL {id_orden}")
        centro = (ref + self.offset[carril]) & MASCARA
        abrir, cerrar = (centro - self.pre) & MASCARA, (centro + self.post) & MASCARA
        if dif(cerrar, self.cuenta) <= 0:
            self.log(f"orden {id_orden} carril {carril}: TARDE")
            return self.tx(f"LATE {id_orden}")
        for o in self.ordenes[carril]:
            if dif(abrir, o["cerrar"]) <= 0 and dif(o["abrir"], cerrar) <= 0:
                if dif(abrir, o["abrir"]) < 0:
                    o["abrir"] = abrir
                if dif(cerrar, o["cerrar"]) > 0:
                    o["cerrar"] = cerrar
                return self.tx(f"ACK {id_orden} {o['id']}")
        if len(self.ordenes[carril]) >= 24:
            return self.tx(f"FULL {id_orden}")
        self.ordenes[carril].append({"id": id_orden, "abrir": abrir, "cerrar": cerrar, "abierta": False})
        faltan = dif(abrir, self.cuenta)
        self.log(f"orden {id_orden} carril {carril}: abrirá dentro de {faltan} cuentas")
        self.tx(f"ACK {id_orden}")

    # --------------- tiempo real ---------------
    def paso(self, dt):
        ahora_ms = time.monotonic() * 1000
        if self.en_marcha and ahora_ms - self.ultimo_ping > self.wd_ms:
            self.en_marcha = False
            self.ordenes = [[] for _ in range(N_CARRILES)]
            self.prueba_hasta = [0.0] * N_CARRILES
            self.manual_abierta = [False] * N_CARRILES
            self.log("WATCHDOG: el cerebro no responde -> parada segura")
            self.tx("ERR WATCHDOG")
        if self.en_marcha:
            self.cuenta_f += self.vel * (self.vel_pct / 50) * dt
        ahora = self.cuenta

        if self.en_marcha and self.trig and dif(ahora, self.prox_disparo) >= 0:
            self.num_foto += 1
            self.tx(f"F {self.num_foto} {ahora}")
            self.prox_disparo = (self.prox_disparo + self.trig) & MASCARA
            if dif(ahora, self.prox_disparo) >= 0:
                self.prox_disparo = (ahora + self.trig) & MASCARA

        for c in range(N_CARRILES):
            abrir = False
            vivas = []
            for o in self.ordenes[c]:
                if dif(ahora, o["cerrar"]) >= 0:
                    self.tx(f"DONE {o['id']}")
                    continue
                if dif(ahora, o["abrir"]) >= 0:
                    abrir = True
                    o["abierta"] = True
                vivas.append(o)
            self.ordenes[c] = vivas
            if self.prueba_hasta[c]:
                if ahora_ms < self.prueba_hasta[c]:
                    abrir = True
                else:
                    self.prueba_hasta[c] = 0
            if self.manual:
                abrir = abrir or self.manual_abierta[c]
                if abrir and self.abierta[c] and ahora_ms - self.abierta_desde[c] > 10000:
                    self.manual_abierta[c] = False
                    self.prueba_hasta[c] = 0
                    abrir = False
                    self.tx(f"ERR TIEMPO_MANUAL {c}")
            elif abrir and self.abierta[c] and ahora_ms - self.abierta_desde[c] > self.max_ms:
                for o in [o for o in self.ordenes[c] if o["abierta"]]:
                    self.tx(f"ERR TIEMPO {o['id']}")
                self.ordenes[c] = [o for o in self.ordenes[c] if not o["abierta"]]
                self.prueba_hasta[c] = 0
                abrir = False
            if abrir != self.abierta[c]:
                self.abierta[c] = abrir
                if abrir:
                    self.abierta_desde[c] = ahora_ms
                    self.aperturas += 1
                self.tx(f"D {c} {1 if abrir else 0}")
                self.log(f"trampilla {c} {'ABIERTA' if abrir else 'cerrada'} (cuenta {ahora})")

    def bucle(self):
        ultimo = time.monotonic()
        ultimo_envio = 0.0
        while True:
            time.sleep(0.001)
            t = time.monotonic()
            with self.lock:
                self.paso(t - ultimo)
                if t - ultimo_envio >= 0.02:
                    ultimo_envio = t
                    self.tx(f"C {self.cuenta}")
            ultimo = t


def crear(host="127.0.0.1", puerto=5555, vel_cps=2000, verbose=True):
    """Crea el simulador y su socket de escucha. Con puerto=0 elige uno libre (útil en tests).
    Devuelve (srv, sim); después llama a atender(srv, sim), normalmente en un hilo."""
    sim = ControladorSimulado(vel_cps, verbose)
    threading.Thread(target=sim.bucle, daemon=True).start()
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, puerto))
    srv.listen(1)
    return srv, sim


def atender(srv, sim):
    """Atiende conexiones una detrás de otra (como la placa: un solo cerebro a la vez)."""
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return  # socket cerrado
        if sim.verbose:
            print("Cerebro conectado")
        with sim.lock:
            sim.salida = conn
            sim.tx("READY triaje 1")
        buf = b""
        try:
            while True:
                trozo = conn.recv(4096)
                if not trozo:
                    break
                buf += trozo
                while b"\n" in buf:
                    linea, buf = buf.split(b"\n", 1)
                    with sim.lock:
                        sim.procesar(linea.decode(errors="replace").strip())
        except OSError:
            pass
        finally:
            conn.close()
        with sim.lock:
            sim.salida = None
            sim.en_marcha = False
            sim.ordenes = [[] for _ in range(N_CARRILES)]
            sim.manual_abierta = [False] * N_CARRILES
            sim.manual = False  # la placa real se reinicia al abrir el puerto y arranca en automático
        if sim.verbose:
            print(f"Cerebro desconectado · aperturas de trampilla en la sesión: {sim.aperturas}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--puerto", type=int, default=5555)
    ap.add_argument("--vel", type=float, default=2000, help="velocidad de la cinta en cuentas/segundo")
    ap.add_argument("--silencio", action="store_true", help="no mostrar cada apertura")
    args = ap.parse_args()

    srv, sim = crear(args.host, args.puerto, args.vel, verbose=not args.silencio)
    print(f"Simulador escuchando en tcp://{args.host}:{args.puerto} · cinta a {args.vel:.0f} cuentas/s")
    try:
        atender(srv, sim)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
