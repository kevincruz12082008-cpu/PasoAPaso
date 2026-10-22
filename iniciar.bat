@echo off
setlocal
cd /d "%~dp0"
title PasoAPaso

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  No encontre Python en esta computadora.
  echo  Descargalo de https://www.python.org/downloads/
  echo  y marca la casilla "Add Python to PATH" al instalarlo.
  echo.
  pause
  exit /b 1
)

echo  Comprobando los componentes de PasoAPaso...
python -c "import pyautogui, PIL, speech_recognition, sounddevice" >nul 2>nul
if errorlevel 1 (
  echo  Instalando lo que falta. La primera vez puede tardar un poco...
  python -m pip install -r requirements.txt --disable-pip-version-check
  if errorlevel 1 (
    echo.
    echo  No se pudieron instalar todos los componentes.
    echo  La app puede abrirse igual, pero quizas sin voz.
    echo  Revisa tu conexion a internet y vuelve a intentarlo.
    echo.
    timeout /t 4 >nul
  )
)

start "" pythonw main.py
exit /b 0
