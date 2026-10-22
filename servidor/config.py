"""Configuración del servidor de PasoAPaso.

Todo se puede cambiar con variables de entorno o con un archivo .env
en la carpeta del proyecto. No se necesita ninguna librería externa.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION = "2.0.0"
NOMBRE_APP = "PasoAPaso"
LEMA = "Tu ayudante para aprender a usar la computadora"


def _cargar_env() -> None:
    """Lee .env sin sobrescribir lo que ya venga del sistema."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


_cargar_env()


def env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


def env_bool(nombre: str, defecto: bool = True) -> bool:
    valor = env(nombre, "1" if defecto else "0").lower()
    return valor not in ("0", "false", "no", "off", "")


def env_int(nombre: str, defecto: int) -> int:
    try:
        return int(env(nombre, str(defecto)))
    except ValueError:
        return defecto


# --- Servidor ---------------------------------------------------------------
HOST = env("PASOAPASO_HOST", "127.0.0.1") or "127.0.0.1"
PUERTO = env_int("PASOAPASO_PORT", env_int("PORT", 8765))
PRODUCCION = env_bool("PASOAPASO_PRODUCCION", False)
PROXY = env_bool("PASOAPASO_PROXY", False)
URL_PUBLICA = env("PASOAPASO_URL", "").rstrip("/")
MAX_CUERPO = 512 * 1024
POR_PAGINA = 25
LOG_ARCHIVO = env("PASOAPASO_LOG", "")
ZONA_UTC = env_int("PASOAPASO_UTC_OFFSET", -6)

# --- Rutas -----------------------------------------------------------------
DIR_DATOS = Path(env("PASOAPASO_DATOS") or str(RAIZ / "datos")).expanduser()
RUTA_DB = DIR_DATOS / "pasoapaso.db"
DIR_PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
DIR_ESTATICOS = Path(__file__).resolve().parent / "estatico"
DIR_RECURSOS = RAIZ / "recursos"
RUTA_LOGO = DIR_RECURSOS / "logo.png"
RUTA_FAVICON = DIR_RECURSOS / "favicon.ico"
RUTA_LOGO_SVG = DIR_RECURSOS / "logo.svg"
RUTA_ZIP = DIR_RECURSOS / "PasoAPaso.zip"


def _leer_o_crear_secreto() -> str:
    valor = env("PASOAPASO_SECRETO")
    if valor:
        return valor
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_DATOS / "secreto.txt"
    try:
        if ruta.exists():
            existente = ruta.read_text(encoding="utf-8").strip()
            if existente:
                return existente
    except OSError:
        pass
    valor = secrets.token_urlsafe(48)
    try:
        ruta.write_text(valor, encoding="utf-8")
        os.chmod(ruta, 0o600)
    except OSError:
        pass
    return valor


SECRETO = _leer_o_crear_secreto()

# --- Cuentas ---------------------------------------------------------------
SESION_HORAS = env_int("PASOAPASO_SESION_HORAS", 24 * 7)
ADMIN_SESION_HORAS = env_int("PASOAPASO_ADMIN_SESION_HORAS", 12)
REGISTRO_ABIERTO = env_bool("PASOAPASO_REGISTRO", True)
PERMITIR_OFFLINE = env_bool("PASOAPASO_OFFLINE", True)
MAX_INTENTOS_LOGIN = env_int("PASOAPASO_MAX_INTENTOS", 6)
VENTANA_INTENTOS = env_int("PASOAPASO_VENTANA_INTENTOS", 300)

ADMIN_USUARIO = env("PASOAPASO_ADMIN_USUARIO") or "admin"
ADMIN_NOMBRE = env("PASOAPASO_ADMIN_NOMBRE") or "Administrador de PasoAPaso"
ADMIN_CLAVE_DEFECTO = "PasoAPaso2026"
ADMIN_CLAVE = env("PASOAPASO_ADMIN_CLAVE") or ADMIN_CLAVE_DEFECTO
ADMIN_RESET = env_bool("PASOAPASO_ADMIN_RESET", False)
ADMIN_CLAVE_ES_DEFECTO = ADMIN_CLAVE == ADMIN_CLAVE_DEFECTO

# --- Inteligencia artificial ------------------------------------------------
IA_ACTIVA = env_bool("PASOAPASO_IA", True)
GEMINI_API_KEY = env("GEMINI_API_KEY", "") or env("PASOAPASO_IA_CLAVE", "")
GEMINI_MODELO = env("GEMINI_MODELO") or "gemini-2.5-flash"
IA_TIMEOUT = env_int("PASOAPASO_IA_TIMEOUT", 15)
IA_MAX_ORDENES = 8
IA_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={clave}"

# --- Contenido --------------------------------------------------------------
MAX_TEXTO = 600
MAX_NOMBRE = 80
MAX_CIUDAD = 60
EXPERIENCIAS = {
    "nunca": "Nunca he usado una computadora",
    "poco": "La uso poco y con ayuda",
    "seguido": "La uso seguido",
}
ORIGENES = {"texto", "voz", "voz_web", "offline"}
ESTADOS = {"pendiente", "completado", "detenido", "error", "sin_entender"}
