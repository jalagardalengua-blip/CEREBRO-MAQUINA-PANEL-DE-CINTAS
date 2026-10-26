"""
Ejemplo mínimo: tu detector conectado al controlador, sin panel.
Para la línea completa con panel de control usa linea.py.

Probar sin hardware:
    python simulador.py                    # en una terminal
    python ejemplo_detector.py --demo      # en otra
"""
import argparse
import time

import config_linea as cfg
import mi_detector
from triaje_link import Antiduplicados, Controlador


def al_evento(tipo, id_orden, texto):
    if tipo == "LATE":
        print(f"[!] orden {id_orden} llegó tarde: la fruta ya había pasado. Revisa la latencia de tu modelo.")
    elif tipo == "FULL":
        print(f"[!] cola llena en el controlador (orden {id_orden}).")
    elif tipo == "ERR":
        print(f"[!] controlador: {texto}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="tcp://127.0.0.1:5555")
    ap.add_argument("--demo", action="store_true", help="usar detecciones inventadas")
    ap.add_argument("--segundos", type=float, default=0, help="parar tras N segundos (0 = sin fin)")
    args = ap.parse_args()

    with Controlador(args.destino, al_evento=al_evento) as ctl:
        ctl.configurar(offsets=cfg.OFFSETS_CARRIL, pre=cfg.PRE, post=cfg.POST, disparo_cada=cfg.DISPARO_CADA)
        ctl.modo_manual(False)  # por si la placa se quedó en manual
        dup = Antiduplicados(tolerancia_cuentas=80)
        ctl.marcha(True)
        print("Cinta en marcha. Ctrl+C para parar.")
        inicio = time.monotonic()
        try:
            while not args.segundos or time.monotonic() - inicio < args.segundos:
                ctl.vivo()                               # latido: "el cerebro sigue funcionando"
                foto = ctl.esperar_foto(timeout=0.2)
                if foto is None:
                    continue
                num_foto, cuenta_foto = foto
                imagen = mi_detector.capturar_imagen(num_foto)
                for f in mi_detector.detectar(imagen, demo=args.demo):
                    if not f["mala"] and f["confianza"] >= cfg.CONFIANZA_MINIMA:
                        continue                         # buena: sigue hacia la caja
                    carril = cfg.CAL.carril(f["y"])
                    if carril is None:
                        continue
                    ref = cfg.CAL.cuenta_referencia(cuenta_foto, f["x"])
                    if dup.nuevo(carril, ref):
                        ctl.expulsar(carril, ref, info={"foto": num_foto})
        except KeyboardInterrupt:
            pass
        finally:
            ctl.marcha(False)
        e = ctl.estadisticas
        print(f"Órdenes enviadas {e['enviadas']} · expulsadas {e['DONE']} · misma fruta {e['fusionadas']} · "
              f"tarde {e['LATE']} · errores {e['ERR']} · aún en camino al parar {len(ctl.pendientes)}")


if __name__ == "__main__":
    main()
