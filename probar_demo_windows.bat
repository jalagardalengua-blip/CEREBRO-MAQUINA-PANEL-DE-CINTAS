@echo off
setlocal
cd /d "%~dp0"
title Demo de la triadora
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Primero abre instalar_windows.bat
  pause
  exit /b 1
)

rem Sin maquina: el simulador hace de placa y el detector inventa frutas.
cd software
start "Simulador de la placa - no cerrar" cmd /k "%PY%" simulador.py --silencio
timeout /t 2 /nobreak >nul
start "Servicio de linea - no cerrar" cmd /k "%PY%" linea.py --demo
timeout /t 3 /nobreak >nul
start "" http://localhost:8080

echo.
echo El panel se ha abierto en el navegador: http://localhost:8080
echo PIN del modo manual: 1234
echo.
echo Para terminar, cierra las dos ventanas negras: "Simulador de la placa" y "Servicio de linea".
pause
