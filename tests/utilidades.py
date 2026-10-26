"""Ayudas comunes de los tests: rutas y un simulador de placa en un puerto libre."""
import os
import sys
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOFTWARE = os.path.join(RAIZ, "software")
if SOFTWARE not in sys.path:
    sys.path.insert(0, SOFTWARE)

import simulador  # noqa: E402


class SimuladorEnHilo:
    """Arranca el simulador de la placa en un puerto libre. Úsalo con `with`."""

    def __init__(self, vel_cps=2000):
        self.srv, self.sim = simulador.crear("127.0.0.1", 0, vel_cps, verbose=False)
        self.puerto = self.srv.getsockname()[1]
        self.destino = f"tcp://127.0.0.1:{self.puerto}"
        threading.Thread(target=simulador.atender, args=(self.srv, self.sim), daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.srv.close()
