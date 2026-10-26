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

## Triadora con cámara en directo (sin instalar nada)

**<https://jalagardalengua-blip.github.io/cerebro-maquina-panel-de-cintas/triadora/>**

App web que usa la cámara del móvil o del ordenador para clasificar cada naranja en tiempo real: **buenas** (a caja), **a revisar** y **malas** (a destrío), con una foto de cada mala, contadores del turno, calibre en milímetros y exportación a ZIP o CSV. Se puede instalar en el móvil («Añadir a pantalla de inicio») y funciona sin internet una vez abierta.

- Código: [`docs/triadora/index.html`](docs/triadora/index.html), un solo archivo sin dependencias.
- Visión: separa cada fruta del fondo, mide 17 rasgos de su piel en relación con su propio color y decide con dos modelos de árboles aprendidos con unas 4.500 fotos reales de naranjas (sanas y podridas) y 1.500 de otras frutas. En fotos que no vio al aprender: el 88–90 % de las buenas salen buenas y solo el 0,3–1,2 % van a destrío; se detectan el 80–90 % de las malas, y se ignora el 97–99 % de las otras frutas.
- Para que funcione bien: fondo liso gris, negro o blanco, buena luz y cámara fija a 40–60 cm.
- Es la base para `software/mi_detector.py`: las fotos que se corrijan y exporten desde la app sirven para entrenar el detector con vuestra fruta.

La portada [`docs/index.html`](docs/index.html) enlaza la triadora y la maqueta 3D. Se publica con GitHub Pages desde la carpeta `docs/` de la rama `main` (Settings → Pages).

## En Windows

Instala Python 3.10+ (marcando "Add python.exe to PATH") y haz doble clic en:

1. `instalar_windows.bat`: una vez.
2. `probar_demo_windows.bat`: el panel sin máquina, con PIN `1234`.
3. `arrancar_linea_windows.bat`: con la placa real (edita antes el puerto COM y el PIN).

Guía completa, incluida la instalación de Claude Code: [docs/windows.md](docs/windows.md).

## Empezar en 1 minuto (sin hardware, cualquier sistema)

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
| `*_windows.bat` | Instalar, probar y arrancar en Windows con doble clic |
| `docs/windows.md` | Guía de Windows: instalación, placa, tableta, arranque automático y Claude Code |
| `docs/protocolo.md` | Cómo se hablan PC y placa, y por qué |
| `docs/montaje_y_calibracion.md` | Cableado, calibración y paso a PLC |
| `docs/producto.md` | Plan para convertirlo en producto |
| `docs/maqueta_3d.html` | Maqueta 3D interactiva de la máquina (ábrela en el navegador) |
| `docs/triadora/` | Triadora con cámara en directo (app web, se publica en GitHub Pages) |
| `docs/index.html` | Portada de GitHub Pages |

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Prueban el protocolo contra el simulador (órdenes, órdenes que llegan tarde, duplicados, watchdog y modo manual), la API del panel (PIN, hombre muerto y cambio de modo) y los cálculos de calibración. También compilan el firmware con una imitación de Arduino si hay `g++`. En GitHub se ejecutan solas en cada subida, y además se compila el firmware para la ESP32 real (`.github/workflows/ci.yml`).

## Seguridad

Este sistema clasifica fruta. **No protege a las personas.** La parada de emergencia, los resguardos y la consignación para mantenimiento deben ir por hardware, independientes del PC y de la placa. Más detalles en [docs/protocolo.md](docs/protocolo.md#seguridad).
