from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env() -> None:
    """Lee .env sin sobrescribir las variables del sistema."""
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

NOMBRE_APP = "PasoAPaso"
LEMA = "Tu ayudante para aprender a usar la computadora"
VERSION = "2.0.0"
CLASES = ("Programación", "Diseño Web")
INTEGRANTES = (
    "Kevin Cruz",
    "Eduardo Antonio",
    "Kevin Betanzo",
    "Daniela Portillo",
    "Yilber Padilla",
)

# --- Ritmo de la demostración ----------------------------------------------
VELOCIDAD_INICIAL = 0.8
VELOCIDAD_MIN = 0.5
VELOCIDAD_MAX = 2.0
PAUSA_ESCRITURA = 0.13
PAUSA_ESCRITURA_INSTANTANEA = 0.01
FACTOR_ESPERA_INSTANTANEA = 0.45
DURACION_MOVIMIENTO_MOUSE = 1.2

REPRODUCIR_PRIMER_RESULTADO = True
POSICION_PRIMER_VIDEO = (0.30, 0.36)
CARPETA_CAPTURAS = "Capturas PasoAPaso"

# --- Servidor ---------------------------------------------------------------
URL_SERVIDOR = (os.environ.get("PASOAPASO_API_URL") or "http://127.0.0.1:8765").rstrip("/")
USAR_SERVIDOR_LOCAL = not bool((os.environ.get("PASOAPASO_API_URL") or "").strip())
PUERTO_LOCAL = int(os.environ.get("PASOAPASO_PORT") or "8765")
HOST_LOCAL = "127.0.0.1"
TIEMPO_ESPERA_NUBE = float(os.environ.get("PASOAPASO_TIMEOUT") or "8")
MAX_TEXTO = 600

# --- Datos locales ----------------------------------------------------------
CARPETA_DATOS = Path(os.environ.get("APPDATA") or str(Path.home())) / "PasoAPaso"
RUTA_SESION = CARPETA_DATOS / "sesion.json"
RUTA_PENDIENTES = CARPETA_DATOS / "pendientes.json"
RUTA_PREFERENCIAS = CARPETA_DATOS / "preferencias.json"
RUTA_REGISTRO = CARPETA_DATOS / "pasoapaso.log"

# --- Recursos ---------------------------------------------------------------
RUTA_RECURSOS = RAIZ / "recursos"
RUTA_LOGO = RUTA_RECURSOS / "logo.png"
RUTA_LOGO_256 = RUTA_RECURSOS / "logo_256.png"
RUTA_LOGO_128 = RUTA_RECURSOS / "logo_128.png"
RUTA_LOGO_64 = RUTA_RECURSOS / "logo_64.png"
RUTA_ICONO = RUTA_RECURSOS / "favicon.ico"
PAGINA_SOPORTE = RAIZ / "soporte" / "index.html"
RUTA_ZIP = RUTA_RECURSOS / "PasoAPaso.zip"

# --- Voz --------------------------------------------------------------------
VOZ_ENTRADA_POR_DEFECTO = True
VOZ_SALIDA_POR_DEFECTO = True
HABLAR_PASOS = True
IDIOMA_VOZ = os.environ.get("PASOAPASO_IDIOMA_VOZ") or "es-MX"
ESPERA_MAXIMA_VOZ = 10.0

# --- Comportamiento ---------------------------------------------------------
EXPERIENCIAS = {
    "nunca": "Nunca he usado una computadora",
    "poco": "La uso poco y con ayuda",
    "seguido": "La uso seguido",
}


def preparar_entorno() -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    (CARPETA_DATOS / "datos").mkdir(parents=True, exist_ok=True)
