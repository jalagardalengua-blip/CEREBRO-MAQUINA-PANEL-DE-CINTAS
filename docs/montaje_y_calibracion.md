# Montaje y calibración

## Cableado del prototipo

| Pieza | Conexión |
|---|---|
| Encoder incremental en el eje del rodillo motriz (p. ej. 1 000 pulsos/vuelta) | Canales A y B a GPIO 34 y 35. Los encoders industriales van a 24 V: usa un optoacoplador o un adaptador de nivel a 3,3 V, con resistencias de pull-up |
| Cámara industrial con entrada de disparo | GPIO 25, a través de un optoacoplador si la cámara usa 24 V |
| Marcha de la cinta | GPIO 26 a un relé o a la entrada de marcha del variador |
| Velocidad de la cinta | GPIO 27 (PWM) a un convertidor PWM → 0-10 V, a la entrada analógica del variador |
| 4 electroválvulas de los cilindros de las trampillas (24 V) | GPIO 16 a 19, cada uno a un driver con MOSFET o a un módulo de relés de estado sólido, con diodo de protección en la bobina |
| ESP32 | USB al PC, que también le da alimentación |

Si cambias los pines, edítalos al principio del firmware. Se carga con el IDE de Arduino y el paquete de placas ESP32.

## Calibración (una vez, con la cinta montada)

1. **Cuentas por milímetro.** Marca la cinta con una tiza, avanza un metro y lee la cuenta con `ST`. Por ejemplo, 4 000 cuentas por metro son 4 cuentas por mm.
2. **Línea de referencia.** Elige una columna de la imagen, por ejemplo el centro (`x_ref_px`).
3. **Cuentas por píxel.** Pon una regla en la cinta bajo la cámara: si 100 mm ocupan 160 píxeles, `cuentas_por_px` = 4 × 100 / 160 = 2,5.
4. **Offset de cada carril.** Mide la distancia de la línea de referencia al centro de cada trampilla y multiplícala por las cuentas por mm. Ajústalo después con fruta real hasta que caiga centrada.
5. **Límites de carril.** Anota las filas de la imagen donde están los separadores (`limites_carril_px`).
6. **PRE y POST.** Marcan cuánto antes y cuánto después del centro de la fruta está abierta la trampilla. Empieza con PRE 40 y POST 60 y ajústalos con fruta real: si la fruta mala no llega a caer, auméntalos; si caen también las vecinas, redúcelos o abre más hueco entre frutas.

## Paso a un PLC industrial

Para la máquina definitiva, la ESP32 puede sustituirse por un PLC (Siemens, Omron…) con una tarjeta de contador rápido. El protocolo sigue siendo el mismo, normalmente por TCP en lugar de USB. Solo cambia la clase `Controlador` de `software/triaje_link.py`; tu código de detección no se toca.
