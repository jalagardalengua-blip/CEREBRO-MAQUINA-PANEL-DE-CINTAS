@echo off
setlocal
cd /d "%~dp0"
title Buscar el puerto de la placa
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Primero abre instalar_windows.bat
  pause
  exit /b 1
)
echo Puertos serie conectados a este ordenador:
echo.
"%PY%" -m serial.tools.list_ports -v
echo.
echo La placa ESP32 suele aparecer como "Silicon Labs CP210x" o "USB-SERIAL CH340".
echo Si no aparece nada, instala el driver USB de tu placa y vuelve a conectarla.
echo Escribe su COM, por ejemplo COM3, en arrancar_linea_windows.bat
pause
