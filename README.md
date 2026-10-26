# Triadora de cítricos por carriles

Máquina que sustituye el triaje manual de fruta: una cámara con IA inspecciona naranjas, mandarinas o limones sobre una cinta de 4 carriles, y unas trampillas neumáticas dejan caer la fruta mala.

```
 fruta ─► cinta lenta ─► separadores ─► cinta rápida ─► [cámara] ───────► trampillas ─► caja buena
           (embudo en V)  (4 carriles)   (abre huecos)     │                  ▲    │
                                                           │ fotos            │    └─► destrío
                                                           ▼                  │
                                              ┌──────── PC: linea.py ────────┐│
                                              │ tu detector (mi_detector.py) ││ órdenes por USB
                                              │ panel web auto / manual      │┘ (en cuentas del encoder)
                                              └──────────────────────────────┘
                                                           ▲
                                     placa ESP32: encoder, disparo de cámara, trampillas, watchdog
```

**Estado:** prototipo. El software se prueba automáticamente contra un simulador de la placa. El firmware compila, pero falta probarlo en una ESP32 real y calibrarlo con fruta.

## Empezar en 1 minuto (sin hardware)

Necesitas Python 3.10 o superior.

```bash
cd software
python simulador.py          # terminal 1: hace de placa
python linea.py --demo       # terminal 2: servicio de línea con detecciones inventadas
```

Abre <http://localhost:8080>. Verás el panel de control. El PIN de modo manual por defecto es `1234`: cámbialo en `config_linea.py` o arranca con `--pin`.

## Con la placa real

```bash
pip install -r requirements.txt
cd software
python linea.py --destino COM3 --pin 4821        # Windows
python linea.py --destino /dev/ttyUSB0 --pin 4821  # Linux
```

Antes, carga `firmware/controlador_trampillas` en la ESP32 con el IDE de Arduino (paquete de placas *esp32* de Espressif). El cableado y la calibración están en [docs/montaje_y_calibracion.md](docs/montaje_y_calibracion.md).

## Dónde va tu software de detección

En **`software/mi_detector.py`**, y solo ahí. Hay que rellenar dos funciones:

- `capturar_imagen(num_foto)`: devuelve la foto que la cámara hizo con ese disparo.
- `detectar(imagen)`: devuelve una lista de frutas con `x`, `y` (píxeles), `mala` (True/False) y `confianza` (de 0 a 1).

Todo lo demás ya está resuelto: pasar de píxeles a carril y posición en la cinta, no repetir órdenes de la misma fruta, el latido de seguridad y el panel.

## Estructura

| Ruta | Qué es |
|---|---|
| `software/mi_detector.py` | Tu modelo (lo único que tienes que escribir) |
| `software/config_linea.py` | Medidas de la línea (calibración) y PIN de mantenimiento |
| `software/linea.py` | Servicio de línea: une detector, placa y panel. Es lo que se arranca en la máquina |
| `software/panel/index.html` | Panel de control web, modo automático y manual |
| `software/triaje_link.py` | Librería de comunicación con la placa |
| `software/simulador.py` | Simulador de la placa para probar sin hardware |
| `software/ejemplo_detector.py` | Ejemplo mínimo sin panel |
| `firmware/controlador_trampillas/` | Programa de la placa ESP32 |
| `tests/` | Pruebas automáticas |
| `docs/protocolo.md` | Cómo se hablan PC y placa, y por qué |
| `docs/montaje_y_calibracion.md` | Cableado, calibración y paso a PLC |
| `docs/producto.md` | Plan para convertirlo en producto |
| `docs/maqueta_3d.html` | Maqueta 3D interactiva de la máquina (ábrela en el navegador) |

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Prueban el protocolo contra el simulador (órdenes, órdenes que llegan tarde, duplicados, watchdog y modo manual), la API del panel (PIN, hombre muerto y cambio de modo) y los cálculos de calibración. También compilan el firmware con una imitación de Arduino si hay `g++`. En GitHub se ejecutan solas en cada subida, y además se compila el firmware para la ESP32 real (`.github/workflows/ci.yml`).

## Seguridad

Este sistema clasifica fruta. **No protege a las personas.** La parada de emergencia, los resguardos y la consignación para mantenimiento deben ir por hardware, independientes del PC y de la placa. Más detalles en [docs/protocolo.md](docs/protocolo.md#seguridad).
