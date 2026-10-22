@echo off
setlocal
cd /d "%~dp0"
title PasoAPaso - Servidor
echo.
echo  Servidor de PasoAPaso
echo  Dejalo abierto mientras uses la app o el panel.
echo  Para detenerlo, cierra esta ventana o presiona Ctrl+C.
echo.
python -m servidor --host 0.0.0.0 --port 8765 --abrir
pause
