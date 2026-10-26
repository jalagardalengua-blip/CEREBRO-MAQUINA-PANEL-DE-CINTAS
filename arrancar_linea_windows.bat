@echo off
setlocal
rem ================== AJUSTA ESTOS VALORES ==================
rem Puerto de la placa ESP32. Averigualo con buscar_puerto_windows.bat
set "PUERTO=COM3"
rem PIN para pasar a modo manual. Cambialo por uno tuyo.
set "PIN=1234"
rem RED=si para abrir el panel desde una tableta en la misma wifi
set "RED=no"
rem DEMO=si para probar la placa real con frutas inventadas,
rem mientras aun no has conectado tu modelo en software\mi_detector.py
set "DEMO=no"
rem ==========================================================

cd /d "%~dp0"
title Triadora - linea
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Primero abre instalar_windows.bat
  pause
  exit /b 1
)

set "EXTRA="
if /i "%RED%"=="si" set "EXTRA=%EXTRA% --red"
if /i "%DEMO%"=="si" set "EXTRA=%EXTRA% --demo"

cd software
start "Servicio de linea - no cerrar" cmd /k "%PY%" linea.py --destino %PUERTO% --pin %PIN%%EXTRA%
timeout /t 4 /nobreak >nul
start "" http://localhost:8080

echo.
echo Panel: http://localhost:8080
if /i "%RED%"=="si" echo Desde la tableta: http://IP-DE-ESTE-PC:8080  - la IP la ves con el comando ipconfig
echo Si la ventana "Servicio de linea" muestra un error, revisa el puerto %PUERTO% y el cable USB.
pause
