from pathlib import Path

from ..utilidades.normalizador import normalizar
from ..utilidades.plataforma import carpeta_conocida, es_windows

RESOLUTORES = {
    "escritorio": (0x10, ("Desktop", "Escritorio")),
    "documentos": (0x05, ("Documents", "Documentos")),
    "imagenes": (0x27, ("Pictures", "Imágenes", "Imagenes")),
    "descargas": (None, ("Downloads", "Descargas")),
}

ETIQUETAS = {
    "escritorio": "el Escritorio",
    "documentos": "Documentos",
    "imagenes": "Imágenes",
    "descargas": "Descargas",
}

ALIAS = {
    "escritorio": "escritorio",
    "desktop": "escritorio",
    "documentos": "documentos",
    "mis documentos": "documentos",
    "descargas": "descargas",
    "mis descargas": "descargas",
    "imagenes": "imagenes",
    "mis imagenes": "imagenes",
    "fotos": "imagenes",
    "mis fotos": "imagenes",
}


def clave_ubicacion(texto):
    return ALIAS.get(texto.strip())


def ruta_ubicacion(clave):
    csidl, alternativas = RESOLUTORES[clave]
    if csidl is not None and es_windows():
        try:
            ruta = carpeta_conocida(csidl)
            if ruta and Path(ruta).is_dir():
                return Path(ruta)
        except Exception:
            pass
    for nombre in alternativas:
        candidata = Path.home() / nombre
        if candidata.is_dir():
            return candidata
    return Path.home()


def _subcarpetas(base):
    try:
        return [e for e in base.iterdir() if e.is_dir() and not e.name.startswith(".")]
    except OSError:
        return []


def buscar_carpeta(nombre, clave=None):
    objetivo = normalizar(nombre).strip()
    claves = [clave] if clave else list(RESOLUTORES)
    bases = [ruta_ubicacion(c) for c in claves]
    hijas = [hija for base in bases for hija in _subcarpetas(base)]
    for hija in hijas:
        if normalizar(hija.name) == objetivo:
            return hija
    for hija in hijas:
        if objetivo and objetivo in normalizar(hija.name):
            return hija
    for hija in hijas:
        for nieta in _subcarpetas(hija):
            if normalizar(nieta.name) == objetivo:
                return nieta
    return None
