# Protocolo entre el PC (cerebro) y la placa (músculo)

## La idea clave: órdenes en cuentas del encoder, no en tiempo

El PC tiene retrasos impredecibles: el modelo tarda más en unas fotos que en otras y Windows o Linux pueden pausar el programa unos milisegundos. Por eso **el cerebro nunca dice "abre ahora"**. Dice:

> "La fruta que pasó por la línea de referencia de la cámara cuando el encoder marcaba 18 342, en el carril 2, es mala."

El controlador sabe que la trampilla del carril 2 está 3 000 cuentas más adelante y la abre cuando el encoder marque 18 342 + 3 000. Así acierta aunque el detector tarde, y aunque la cinta acelere o frene.

El único límite es que la orden llegue antes de que la fruta alcance la trampilla. Si llega tarde, el controlador responde `LATE` y tu programa lo sabe. Con la trampilla a 75 cm de la cámara y la cinta a 0,5 m/s tienes 1,5 s de margen.

## Flujo

1. El controlador dispara la cámara cada N cuentas y envía `F <foto> <cuenta>`.
2. Tu programa recoge esa foto, la analiza y, por cada fruta mala, calcula su carril (por la posición vertical en la imagen) y su cuenta de referencia (por la posición horizontal).
3. Envía `EJ <id> <carril> <cuenta>`. El controlador responde `ACK`.
4. Cuando la fruta pasa, la trampilla se abre y se cierra, y el controlador envía `DONE <id>`.

La misma fruta sale en varias fotos. La librería filtra los duplicados, y el controlador además fusiona las órdenes que se solapan, así que una fruta nunca abre la trampilla dos veces.

## Seguridad

- **Latido (watchdog).** Tu programa llama a `ctl.vivo()` en cada vuelta de su bucle y la librería envía `PING` 10 veces por segundo. Si tu programa se cuelga, el controlador deja de recibirlos y a los 500 ms para la cinta, cierra las trampillas, borra las órdenes y envía `ERR WATCHDOG`. Así no pasa fruta sin inspeccionar.
- **Tiempo máximo abierta.** Ninguna trampilla queda abierta más de 1,5 s, aunque la cinta se pare encima.
- **La parada de emergencia no pasa por aquí.** La seta y las protecciones deben cortar la alimentación de la cinta y de las electroválvulas directamente por hardware. Este sistema es para clasificar, no para proteger a las personas.

## Protocolo

Texto ASCII, una orden por línea, a 115 200 baudios. Las cuentas son enteros de 32 bits sin signo que dan la vuelta al llegar a 4 294 967 295; ambos lados ya lo tienen en cuenta.

**Del PC al controlador**

| Orden | Respuesta | Para qué |
|---|---|---|
| `PING` | `PONG <cuenta>` | Latido; obligatorio al menos cada 500 ms con la cinta en marcha |
| `EJ <id> <carril> <cuenta_ref>` | `ACK <id>`, `ACK <id> <id_fusionada>`, `LATE <id>` o `FULL <id>` | Expulsar una fruta. Carril de 0 a 3 |
| `RUN 1` / `RUN 0` | `OK` o `ERR SIN_PING` | Arrancar o parar la cinta |
| `SET OFFSET <carril> <cuentas>` | `OK` | Distancia de la línea de referencia a la trampilla |
| `SET PRE <cuentas>` / `SET POST <cuentas>` | `OK` | Margen de apertura antes y después del centro de la fruta |
| `SET TRIG <cuentas>` | `OK` | Disparar la cámara cada N cuentas (0 = sin disparo) |
| `SET MAXMS <ms>` / `SET WD <ms>` | `OK` | Tiempo máximo abierta y tiempo del watchdog |
| `TEST <carril>` | `OK` | Abre la trampilla 300 ms para comprobar el cableado |
| `MODE MAN` / `MODE AUTO` | `OK` | Cambia de modo; en los dos casos para la cinta |
| `DOOR <carril> <1\|0>` | `OK` o `ERR NO_MANUAL` | Solo en manual: abre o cierra una trampilla |
| `SPEED <0-100>` | `OK` | Consigna de velocidad para el variador |
| `CLEAR` | `OK` | Borra todas las órdenes pendientes |
| `ST` | `ST run=1 cuenta=… modo=AUTO v=50 q=0,2,0,1 d=0100` | Estado: marcha, cuenta, modo, velocidad, cola por carril y trampillas abiertas |

**Del controlador al PC, sin que se lo pidan**

| Mensaje | Significado |
|---|---|
| `READY triaje 1` | La placa acaba de arrancar |
| `C <cuenta>` | Cuenta actual, cada 20 ms |
| `F <foto> <cuenta>` | Se ha disparado la cámara con esa cuenta |
| `DONE <id>` | La trampilla se abrió y se cerró para esa orden |
| `D <carril> <1\|0>` | Una trampilla se acaba de abrir o cerrar |
| `ERR MANUAL <id>` | Orden del detector rechazada porque la placa está en manual |
| `ERR TIEMPO_MANUAL <carril>` | Trampilla abierta a mano cerrada sola a los 10 s |
| `ERR WATCHDOG` | Parada segura por falta de latido |
| `ERR TIEMPO <id>` | Se canceló la orden por superar el tiempo máximo abierta |

## Modo automático y modo manual

**Automático** (el normal). El detector manda: decide qué trampilla se abre. El operario solo arranca, para y ajusta la velocidad.

**Manual** (mecánicos y mantenimiento). Se entra con nombre y PIN, que quedan en el registro. Al entrar:
- la cinta se para y se borran las órdenes pendientes;
- la placa rechaza cualquier orden del detector (`ERR MANUAL`), aunque el detector siga mirando;
- la cinta solo se mueve **mientras se mantiene pulsado** el botón (hombre muerto). Si se suelta, se pierde la wifi o se cierra la pestaña, se para en menos de medio segundo;
- cada trampilla se puede abrir, cerrar o probar con un pulso de 0,3 s. Una trampilla abierta a mano se cierra sola a los 10 s.

Al volver a automático se cierran todas las trampillas y la cinta queda parada hasta que alguien pulse Arrancar.

El PIN evita que alguien pase a manual sin querer. No es una protección de seguridad: para trabajar dentro de la máquina hay que cortar la energía y bloquear el seccionador (consignación), como en cualquier máquina.
