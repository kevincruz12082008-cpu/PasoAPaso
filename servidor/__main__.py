"""Arranca el servidor de PasoAPaso.

Ejemplos:
    python -m servidor
    python -m servidor --host 0.0.0.0 --port 8000
    python -m servidor --abrir
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import webbrowser
from pathlib import Path


def _argumentos() -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m servidor",
        description="Servidor web, base de datos y panel de PasoAPaso.",
    )
    analizador.add_argument("--host", default=os.environ.get("PASOAPASO_HOST", "127.0.0.1"))
    analizador.add_argument(
        "--port",
        "--puerto",
        dest="puerto",
        type=int,
        default=int(os.environ.get("PASOAPASO_PORT", os.environ.get("PORT", "8765"))),
    )
    analizador.add_argument(
        "--datos",
        default=os.environ.get("PASOAPASO_DATOS", ""),
        help="Carpeta donde guardar la base de datos (por defecto: ./datos).",
    )
    analizador.add_argument(
        "--abrir",
        action="store_true",
        help="Abrir el panel de administración en el navegador al iniciar.",
    )
    analizador.add_argument(
        "--reset-admin",
        action="store_true",
        help="Volver a poner la clave de administrador indicada en el entorno.",
    )
    analizador.add_argument(
        "--sin-registro",
        action="store_true",
        help="Cerrar el registro de cuentas nuevas.",
    )
    analizador.add_argument("--silencioso", action="store_true", help="Menos mensajes en consola.")
    return analizador.parse_args()


def main() -> int:
    argumentos = _argumentos()
    if argumentos.datos:
        os.environ["PASOAPASO_DATOS"] = str(Path(argumentos.datos).expanduser().resolve())
    os.environ["PASOAPASO_HOST"] = argumentos.host
    os.environ["PASOAPASO_PORT"] = str(argumentos.puerto)
    if argumentos.reset_admin:
        os.environ["PASOAPASO_ADMIN_RESET"] = "1"
    if argumentos.sin_registro:
        os.environ["PASOAPASO_REGISTRO"] = "0"

    # La configuración se importa después de aplicar los argumentos.
    from . import config, base_datos
    from .servidor import crear_servidor

    config.DIR_DATOS.mkdir(parents=True, exist_ok=True)
    registro = logging.getLogger("pasoapaso")
    registro.setLevel(logging.DEBUG if not argumentos.silencioso else logging.WARNING)
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s", "%H:%M:%S")
    )
    registro.addHandler(manejador)
    if config.LOG_ARCHIVO:
        archivo = logging.FileHandler(config.LOG_ARCHIVO, encoding="utf-8")
        archivo.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s")
        )
        registro.addHandler(archivo)

    servidor = crear_servidor(argumentos.host, argumentos.puerto)
    url = f"http://{argumentos.host}:{servidor.server_address[1]}"
    if argumentos.host in ("0.0.0.0", "::"):
        url_visible = f"http://127.0.0.1:{servidor.server_address[1]}"
    else:
        url_visible = url

    print("")
    print("  PasoAPaso " + config.VERSION)
    print("  Servidor: " + url_visible)
    print("  Panel:    " + url_visible + "/admin")
    print("  Usuario:  " + config.ADMIN_USUARIO)
    if base_datos.admin_usa_clave_defecto():
        print("  Clave:    " + config.ADMIN_CLAVE_DEFECTO + "   (cámbiala al entrar)")
    print("  Datos:    " + str(config.RUTA_DB))
    print("  Detén con Ctrl+C.")
    print("")

    if argumentos.abrir:
        webbrowser.open(url_visible + "/admin")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando PasoAPaso…")
    finally:
        servidor.shutdown()
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
