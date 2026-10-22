import subprocess
from datetime import datetime

import pyautogui

from .. import configuracion as cfg
from ..datos.ubicaciones import ruta_ubicacion


def tomar_captura(guia, orden):
    guia.decir(
        "Vamos a tomar una captura de pantalla",
        "Una captura es una foto de lo que se ve en tu pantalla en este momento.",
        tipo="info",
    )
    guia.pausar(3)
    guia.decir(
        "Así lo harías tú solo",
        "Presiona estas teclas al mismo tiempo y elige qué parte de la pantalla guardar.",
        teclas=("win", "shift", "s"),
    )
    guia.pausar(4.5)
    guia.decir(
        "Ahora lo hago yo por ti",
        "Voy a esconder esta guía para que no salga en la foto.",
        tipo="info",
    )
    guia.pausar(2.5)
    for numero in ("3", "2", "1"):
        guia.decir(f"Captura en {numero}...", tipo="info")
        guia.pausar(1)
    guia.ocultar_panel()
    imagen = pyautogui.screenshot()
    guia.mostrar_panel()
    carpeta = ruta_ubicacion("imagenes") / cfg.CARPETA_CAPTURAS
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"Captura {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    imagen.save(ruta)
    guia.decir(
        "¡Captura guardada!",
        f"La guardé en Imágenes, dentro de la carpeta «{cfg.CARPETA_CAPTURAS}».",
        tipo="ok",
    )
    guia.pausar(2.5)
    if not guia.instantaneo:
        subprocess.Popen(f'explorer /select,"{ruta}"')
        guia.pausar(2.5)
