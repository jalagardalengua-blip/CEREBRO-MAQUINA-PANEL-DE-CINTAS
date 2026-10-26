@echo off
setlocal
cd /d "%~dp0"
title Instalacion de la triadora
echo === Instalacion de la triadora ===
echo.

set "PYBASE="
where py >nul 2>nul && set "PYBASE=py -3"
if not defined PYBASE (
  where python >nul 2>nul && set "PYBASE=python"
)
if not defined PYBASE (
  echo No encuentro Python en este ordenador.
  echo Instalalo desde https://www.python.org/downloads/
  echo y en la primera pantalla marca la casilla "Add python.exe to PATH".
  echo Despues vuelve a abrir este archivo.
  pause
  exit /b 1
)

%PYBASE% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Hace falta Python 3.10 o mas reciente.
  echo Descargalo desde https://www.python.org/downloads/ y vuelve a abrir este archivo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando el entorno de Python en la carpeta .venv ...
  %PYBASE% -m venv .venv
  if errorlevel 1 goto error
)

echo Instalando dependencias ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo Instalacion terminada.
echo Siguiente paso: abre probar_demo_windows.bat para ver el panel sin maquina.
pause
exit /b 0

:error
echo.
echo Algo ha fallado. Lee el mensaje de arriba y comprueba la conexion a internet.
pause
exit /b 1
