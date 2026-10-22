import re
import unicodedata


def _simplificar(caracter):
    base = "".join(
        parte
        for parte in unicodedata.normalize("NFD", caracter)
        if not unicodedata.combining(parte)
    )
    return (base or caracter).lower()[:1]


def normalizar(texto):
    return "".join(_simplificar(caracter) for caracter in texto)


def limpiar_nombre_archivo(texto):
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto)
    limpio = re.sub(r"\s+", " ", limpio).strip(" .")
    return limpio[:100]
