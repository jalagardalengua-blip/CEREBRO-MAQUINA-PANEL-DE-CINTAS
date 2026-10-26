# Instalar y usar en Windows

Para Windows 10 u 11. Todo se hace con archivos que se abren con **doble clic**; no hace falta saber usar la consola.

## 1. Instalar Python (una vez)

1. Descarga Python desde <https://www.python.org/downloads/> (versión 3.10 o más reciente).
2. En la primera pantalla del instalador **marca "Add python.exe to PATH"** y pulsa *Install Now*.

## 2. Descargar el proyecto

Elige una de estas dos formas:

- **Sin Git:** en la página del repositorio en GitHub pulsa **Code → Download ZIP** y descomprímelo, por ejemplo en `C:\triadora`.
- **Con Git** (recomendado si vas a usar Claude Code): instala [Git for Windows](https://git-scm.com/downloads/win) y ejecuta:
  ```
  git clone https://github.com/jalagardalengua-blip/CEREBRO-MAQUINA-PANEL-DE-CINTAS.git C:\triadora
  ```

Mejor una carpeta corta y sin tildes, como `C:\triadora`.

## 3. Instalar el software (una vez)

Doble clic en **`instalar_windows.bat`**. Crea un entorno de Python propio en la carpeta `.venv` e instala lo necesario. Tarda un minuto.

## 4. Probarlo sin máquina

Doble clic en **`probar_demo_windows.bat`**.

- Se abren dos ventanas negras, *Simulador de la placa* y *Servicio de línea*. No las cierres mientras lo uses.
- El navegador abre el panel en <http://localhost:8080>.
- El PIN del modo manual es `1234`.

Para terminar, cierra las dos ventanas negras.

## 5. Con la placa ESP32 real

**Cargar el firmware (una vez por placa)**
1. Instala el [IDE de Arduino](https://www.arduino.cc/en/software).
2. En *Herramientas → Placa → Gestor de placas*, busca **esp32** (de Espressif Systems) e instálalo.
3. Conecta la placa por USB. Si Windows no la reconoce, instala el driver del chip USB de tu placa: **CP210x** (Silicon Labs) o **CH340**, según el modelo.
4. Abre `firmware\controlador_trampillas\controlador_trampillas.ino`, elige tu placa ESP32 y su puerto COM, y pulsa *Subir*.
5. Cierra el monitor serie del IDE de Arduino: si lo dejas abierto, ocupa el puerto y la línea no podrá conectarse.

**Arrancar la línea**
1. Doble clic en **`buscar_puerto_windows.bat`** y apunta el COM de la placa, por ejemplo `COM4`.
2. Abre **`arrancar_linea_windows.bat`** con el Bloc de notas (clic derecho → *Editar*) y cambia los valores del principio:
   - `PUERTO=COM4`
   - `PIN=` un PIN tuyo
   - `RED=si` si quieres usar el panel desde una tableta
   - `DEMO=si` para probar la placa con frutas inventadas mientras aún no has conectado tu modelo
3. Guarda y haz doble clic en `arrancar_linea_windows.bat`.

El cableado y la calibración están en [montaje_y_calibracion.md](montaje_y_calibracion.md).

## 6. Usar el panel desde una tableta

Con `RED=si`, la primera vez Windows preguntará si permite el acceso de Python a la red: elige **Redes privadas** y pulsa *Permitir*. Después, en la tableta conectada a la misma wifi, abre `http://IP-DEL-PC:8080`. La IP del PC la ves escribiendo `ipconfig` en la consola: es la *Dirección IPv4*, por ejemplo `192.168.1.35`.

## 7. Que arranque solo al encender el PC

1. Pulsa `Windows + R`, escribe `shell:startup` y pulsa Enter.
2. En la carpeta que se abre, crea un **acceso directo** a `arrancar_linea_windows.bat`: clic derecho → *Nuevo → Acceso directo* y elige el archivo.

Así la línea arranca cuando alguien inicia sesión en el PC.

## 8. Usar Claude Code en Windows

Claude Code necesita una cuenta Pro, Max, Team, Enterprise o Console.

1. Instala Git for Windows (paso 2). Es opcional, pero recomendado para Claude Code.
2. Abre **PowerShell** y ejecuta:
   ```
   irm https://claude.ai/install.ps1 | iex
   ```
   Si usas la consola clásica (CMD) en lugar de PowerShell:
   ```
   curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
   ```
3. Abre una consola nueva y comprueba que funciona con `claude --version`.
4. Entra en la carpeta del proyecto y arráncalo:
   ```
   cd C:\triadora
   claude
   ```
   La primera vez te pedirá iniciar sesión en el navegador. Claude Code leerá `CLAUDE.md` y ya sabrá cómo está montado el proyecto.

Si prefieres no usar la consola, también puedes usar Claude Code desde la app de escritorio de Claude para Windows.

## Problemas frecuentes

| Qué pasa | Qué hacer |
|---|---|
| "No encuentro Python" | Reinstala Python marcando "Add python.exe to PATH" y reinicia el PC |
| Se abre la Microsoft Store al instalar | Desactiva los alias: *Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de aplicaciones*, apaga los de `python.exe` |
| "No se puede conectar con la placa" | Revisa el COM con `buscar_puerto_windows.bat` y cierra el monitor serie de Arduino |
| El panel dice "Sin conexión con el servicio" | Se ha cerrado la ventana *Servicio de línea*: vuelve a abrir el `.bat` |
| La tableta no abre el panel | Comprueba `RED=si`, la misma wifi y el permiso del cortafuegos para Python |
