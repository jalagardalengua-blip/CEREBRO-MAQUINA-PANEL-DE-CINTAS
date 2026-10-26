"""Ajustes de tu línea. Se miden en la calibración (ver docs/montaje_y_calibracion.md)."""
from triaje_link import Calibracion

N_CARRILES = 4
OFFSETS_CARRIL = [3000, 3000, 3000, 3000]  # cuentas de la línea de referencia a cada trampilla
PRE, POST = 40, 60                         # margen de apertura antes y después del centro de la fruta
DISPARO_CADA = 400                         # una foto cada 400 cuentas (0 = sin disparo hardware)
CAL = Calibracion(x_ref_px=640, cuentas_por_px=2.5,
                  limites_carril_px=[0, 180, 360, 540, 720])
CONFIANZA_MINIMA = 0.80                    # por debajo, la fruta se expulsa por si acaso
VELOCIDAD_INICIAL = 50                     # % de la consigna del variador

# PIN para pasar a modo manual. Cámbialo, o mejor pásalo al arrancar: python linea.py --pin 4821
PIN_MANUAL = "1234"
