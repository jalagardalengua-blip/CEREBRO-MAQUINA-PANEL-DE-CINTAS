# CLAUDE.md

Guía para trabajar en este repositorio con Claude Code.

## Qué es

Triadora de cítricos por carriles: una cámara con IA detecta fruta mala sobre una cinta de 4 carriles y una placa ESP32 abre trampillas neumáticas para expulsarla. Sustituye el triaje manual en almacenes. Es un prototipo: el software está probado contra un simulador, y el firmware aún no se ha probado en hardware real.

El código, los comentarios, los mensajes y la documentación están en **español**. Mantén ese idioma en todo lo que añadas.

## Arquitectura

- `software/linea.py`: **servicio de línea**, el único proceso que abre la conexión con la placa (un puerto serie solo admite un programa). Ejecuta el bucle de detección, sirve el panel web y aplica las reglas de los modos automático y manual. API HTTP: `GET /api/estado`, `POST /api/<accion>`.
- `software/mi_detector.py`: el código del usuario (`capturar_imagen`, `detectar`). No lo reescribas sin que te lo pidan; el modo `demo` inventa detecciones.
- `software/triaje_link.py`: cliente del protocolo (`Controlador`), más `Calibracion` (píxeles a carril y cuenta) y `Antiduplicados`.
- `software/simulador.py`: imita la placa por TCP con el mismo protocolo.
- `software/panel/index.html`: panel en un solo archivo (HTML, CSS y JS sin dependencias). Si no encuentra el servicio, entra en modo demostración con un backend simulado en JS (`Demo`).
- `firmware/controlador_trampillas/controlador_trampillas.ino`: firmware de la ESP32 (Arduino).
- `config_linea.py`: calibración y PIN.
- `docs/triadora/`: app web independiente (GitHub Pages) que clasifica naranjas con la cámara en directo del navegador. `index.html` lleva todo: motor de visión, modelo aprendido (árboles en JSON), seguimiento, panel, capturas y exportación ZIP propia. `sw.js` y `manifest.webmanifest` la hacen instalable y usable sin conexión; si cambias los archivos que guarda, sube la versión de `CACHE` en `sw.js`. No usa el servicio de línea ni la placa.

## Invariantes: no romper

1. **Las órdenes de expulsión van en cuentas del encoder, nunca en tiempo.** `EJ <id> <carril> <cuenta_ref>` indica cuándo pasó la fruta por la línea de referencia de la cámara. La placa añade el offset y abre en su momento. No añadas órdenes del tipo "abre ahora" para el modo automático.
2. **Las cuentas son `uint32` y dan la vuelta.** Compara siempre con la diferencia con signo (`dif()` en C y Python). Nunca uses `<` directo entre cuentas.
3. **Cualquier cambio de protocolo se hace en cuatro sitios a la vez:** el firmware, `simulador.py`, `triaje_link.py` y `docs/protocolo.md`. También en el `Demo` del panel si afecta a lo que ve el usuario. Añade un test en `tests/test_protocolo.py`.
4. **Seguridad:**
   - El watchdog (sin `PING` en 500 ms → parada, trampillas cerradas y órdenes borradas) debe seguir funcionando.
   - `Controlador.vivo()` lo llama el bucle de detección: si el detector se cuelga, el latido se detiene a propósito.
   - Ninguna función de seguridad de personas depende de la IA ni del software. La parada de emergencia es hardware.
5. **Modo manual:**
   - Al entrar y al salir se para la cinta.
   - En manual, la placa rechaza las órdenes `EJ` (`ERR MANUAL`).
   - La cinta solo se mueve con hombre muerto: `jog` renovado cada 150 ms y parada si pasan más de `JOG_MAX_S`.
   - Una trampilla abierta a mano se cierra sola a los 10 s.
6. **Concurrencia en `linea.py`:** `_evento_placa` corre en el hilo lector de la conexión. No cojas `Linea.lock` ahí: una acción del panel puede estar esperando una respuesta de la placa con ese candado cogido y habría un bloqueo.
7. Sin dependencias nuevas sin motivo. El software usa solo la biblioteca estándar más `pyserial`, y el panel no carga nada salvo una fuente de Google con alternativa del sistema.

## Comandos

```bash
python -m unittest discover -s tests -v      # todas las pruebas (unos 15 s)
cd software && python simulador.py           # placa simulada en tcp://127.0.0.1:5555
cd software && python linea.py --demo        # servicio + panel en http://localhost:8080 (PIN 1234)
```

En Windows, el usuario trabaja con los `.bat` de la raíz (`instalar_windows.bat`, `probar_demo_windows.bat`, `arrancar_linea_windows.bat` y `buscar_puerto_windows.bat`) y con `docs/windows.md`. Si cambias los argumentos de `linea.py` o de `simulador.py`, actualiza también esos archivos. Escribe sus mensajes sin tildes, para evitar problemas con la página de códigos de la consola.

Ejecuta las pruebas después de cada cambio. `tests/test_firmware.py` compila el `.ino` con g++ y la imitación de `tests/stub_arduino/Arduino.h`. Si usas una función nueva de Arduino en el firmware, añádela también a esa imitación. La CI de GitHub (`.github/workflows/ci.yml`) además compila para `esp32:esp32:esp32`.

## Estilo

- Python 3.10+, nombres en español y docstrings que expliquen el porqué.
- Firmware sin memoria dinámica y sin `delay()` en el bucle principal.
- Mensajes al usuario claros, en español, diciendo qué pasó y qué hacer.
