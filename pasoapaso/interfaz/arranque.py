"""Arranque de la app: splash, servidor local y acceso."""

from __future__ import annotations

import logging
import os
import time
import tkinter as tk

from .. import configuracion as cfg
from ..nucleo.nube import ClienteNube, ErrorNube
from ..nucleo.sesion import Sesion
from .acceso import VentanaAcceso
from .splash import VentanaSplash

LOG = logging.getLogger("pasoapaso.arranque")
_servidor_local = None


def configurar_registro() -> None:
    cfg.preparar_entorno()
    logger = logging.getLogger("pasoapaso")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    try:
        archivo = logging.FileHandler(cfg.RUTA_REGISTRO, encoding="utf-8")
        archivo.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s")
        )
        logger.addHandler(archivo)
    except OSError:
        pass


def iniciar_servidor_local() -> bool:
    """Inicia el servidor dentro de la misma app si no hay uno en la nube."""
    global _servidor_local
    if not cfg.USAR_SERVIDOR_LOCAL:
        LOG.info("Usando servidor en la nube: %s", cfg.URL_SERVIDOR)
        return True

    cfg.preparar_entorno()
    if not os.environ.get("PASOAPASO_DATOS"):
        os.environ["PASOAPASO_DATOS"] = str(cfg.CARPETA_DATOS / "datos")
    os.environ.setdefault("PASOAPASO_HOST", cfg.HOST_LOCAL)
    os.environ.setdefault("PASOAPASO_PORT", str(cfg.PUERTO_LOCAL))

    try:
        from servidor import servidor as srv
    except Exception:
        LOG.exception("No pude cargar el servidor local")
        return False

    base = f"http://{cfg.HOST_LOCAL}:{cfg.PUERTO_LOCAL}"
    if srv.servidor_activo(base):
        cfg.URL_SERVIDOR = base
        LOG.info("Ya había un servidor de PasoAPaso en %s", base)
        return True

    for puerto in range(cfg.PUERTO_LOCAL, cfg.PUERTO_LOCAL + 12):
        try:
            servidor, _hilo, url = srv.iniciar_en_hilo(cfg.HOST_LOCAL, puerto)
        except OSError:
            continue
        except Exception:
            LOG.exception("No pude iniciar el servidor local en el puerto %s", puerto)
            continue
        _servidor_local = servidor
        cfg.URL_SERVIDOR = url
        LOG.info("Servidor local escuchando en %s", url)
        return True

    LOG.error("No encontré un puerto libre para el servidor local")
    return False


def auto_sesion() -> Sesion | None:
    sesion = Sesion.cargar()
    if not sesion:
        return None
    if sesion.base_url != cfg.URL_SERVIDOR:
        sesion.base_url = cfg.URL_SERVIDOR
    cliente = ClienteNube(cfg.URL_SERVIDOR, sesion.token, timeout=4)
    try:
        datos = cliente.perfil()
    except ErrorNube as error:
        if error.codigo in (401, 403):
            Sesion.borrar()
        LOG.info("No pude validar la sesión guardada: %s", error)
        return None
    except Exception:
        LOG.exception("Error validando la sesión guardada")
        return None
    if datos.get("usuario"):
        sesion.usuario = datos["usuario"]
        try:
            sesion.guardar()
        except OSError:
            pass
    return sesion


def _pedir_sesion(raiz: tk.Tk) -> Sesion | None:
    acceso = VentanaAcceso(raiz)
    return acceso.mostrar()


def arrancar() -> None:
    configurar_registro()
    cfg.preparar_entorno()

    raiz = tk.Tk()
    raiz.withdraw()
    splash = VentanaSplash(raiz)
    splash.mostrar()
    raiz.update()

    splash.actualizar("Iniciando el servidor de PasoAPaso…")
    try:
        iniciar_servidor_local()
    except Exception:
        LOG.exception("Fallo al iniciar el servidor local")
    time.sleep(0.4)
    raiz.update()

    splash.actualizar("Revisando tu cuenta…")
    raiz.update()
    sesion = auto_sesion()

    splash.cerrar()
    if sesion is None:
        sesion = _pedir_sesion(raiz)
    try:
        raiz.destroy()
    except tk.TclError:
        pass
    if not sesion:
        return

    from .ventana_principal import AplicacionPrincipal

    while True:
        app = AplicacionPrincipal(sesion)
        app.ejecutar()
        if not app.reiniciar_sesion:
            break
        raiz_nueva = tk.Tk()
        raiz_nueva.withdraw()
        sesion = _pedir_sesion(raiz_nueva)
        try:
            raiz_nueva.destroy()
        except tk.TclError:
            pass
        if not sesion:
            break
