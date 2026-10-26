# De prototipo a producto

## Qué se vende

Ya existen calibradoras ópticas de cítricos de fabricantes grandes, que venden líneas completas y caras. La propuesta más realista es un **módulo de cámara, IA y trampillas que se monta sobre las cintas que el almacén ya tiene**, a un precio pensado para almacenes pequeños y medianos que hoy triando a mano.

## Fase 1: prototipo que funciona (estado actual)

- Un carril con la ESP32, la cámara y el modelo, instalado en un almacén piloto.
- Medir la fruta mala detectada y la fruta buena perdida, comparado con el triaje manual.
- Reunir miles de fotos etiquetadas en ese almacén para entrenar el modelo.

## Fase 2: producto piloto

**Hardware industrial**
- Sustituir la ESP32 por un PLC (Siemens, Omron…) con contador rápido o por un PC industrial. El protocolo de `docs/protocolo.md` se mantiene; solo cambia la clase `Controlador`.
- Cámara industrial con disparo hardware (Basler, IDS…).
- Cuadro eléctrico según EN 60204-1. Componentes IP65 y acero inoxidable en las zonas húmedas.

**Software**
- Este repositorio, con pruebas automáticas en cada cambio.
- `linea.py` instalado como servicio del sistema, para que arranque solo con la máquina.
- Registros guardados en disco, sistema de actualizaciones y usuarios con permisos en lugar de un PIN compartido.
- El panel web ya funciona en la pantalla de la máquina, en tableta y en móvil. Se puede convertir en app instalable (PWA) sin reescribirlo.

## Fase 3: venta

**Marcado CE (obligatorio)**
- Reglamento (UE) 2023/1230 de máquinas, aplicable desde el 20 de enero de 2027.
- Evaluación de riesgos (ISO 12100), funciones de seguridad (ISO 13849), expediente técnico y declaración de conformidad.
- Materiales en contacto con la fruta conformes al Reglamento (CE) 1935/2004.
- Conviene contar con una consultora de marcado CE desde el diseño.

**IA**
- El reglamento europeo de IA trata como alto riesgo la IA que actúa como componente de seguridad. El acuerdo provisional del "Omnibus digital" (mayo de 2026) aclara que la IA de control de calidad no es de alto riesgo solo por ir dentro de una máquina; está pendiente de publicación formal.
- Por eso el diseño separa funciones: **la IA clasifica fruta y nunca protege a personas**. La seguridad va por hardware.

**Empresa**
- Registro de marca (OEPM o EUIPO). Código y modelo como secreto empresarial.
- Financiación a explorar: CDTI (programa NEOTEC), ENISA, EIT Food.
- Equipo mínimo: software e IA, automatización y cuadros eléctricos, y un taller mecánico de inoxidable.

## Siguiente paso recomendado

Conseguir un almacén piloto antes de invertir en hardware industrial. Una prueba de un carril con números reales (fruta mala detectada, buena perdida, coste frente al triaje manual) es lo que abre la puerta a clientes, financiación y socios.
