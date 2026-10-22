import os
import sys


def mostrar_error(mensaje):
    from tkinter import Tk, messagebox

    raiz = Tk()
    raiz.withdraw()
    messagebox.showerror("PasoAPaso", mensaje)
    raiz.destroy()


def principal():
    from pasoapaso import configuracion as cfg
    from pasoapaso.utilidades.plataforma import activar_nitidez, es_windows

    if not es_windows():
        mostrar_error("PasoAPaso funciona en Windows 10 y Windows 11.")
        return 1

    try:
        import pyautogui  # noqa: F401
    except ImportError:
        mostrar_error(
            "Falta instalar un componente.\n\n"
            "Abre una terminal en esta carpeta y escribe:\n\n"
            "python -m pip install -r requirements.txt"
        )
        return 1

    try:
        cfg.preparar_entorno()
        if not os.environ.get("PASOAPASO_DATOS"):
            os.environ["PASOAPASO_DATOS"] = str(cfg.CARPETA_DATOS / "datos")
        os.environ.setdefault("PASOAPASO_HOST", cfg.HOST_LOCAL)
        os.environ.setdefault("PASOAPASO_PORT", str(cfg.PUERTO_LOCAL))
        activar_nitidez()
        from pasoapaso.interfaz.arranque import arrancar

        arrancar()
    except Exception as error:
        import logging

        logging.getLogger("pasoapaso").exception("Error fatal al iniciar la app")
        mostrar_error(
            "PasoAPaso no pudo iniciarse.\n\n"
            f"{error}\n\n"
            "Revisa el archivo de registro en:\n"
            f"{cfg.RUTA_REGISTRO}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
