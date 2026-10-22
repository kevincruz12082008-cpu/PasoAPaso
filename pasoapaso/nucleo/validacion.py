"""Validación de las órdenes que devuelve la IA.

La IA nunca ejecuta nada directamente: solo propone órdenes. Este módulo
comprueba que cada orden use una acción permitida, que los datos tengan
el tipo correcto y que no se pueda salir del catálogo. Si algo no cumple,
se descarta. Es la barrera de seguridad entre Gemini y la computadora.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from ..datos.catalogo_apps import CATALOGO
from ..datos.ubicaciones import ETIQUETAS, clave_ubicacion
from ..utilidades.normalizador import limpiar_nombre_archivo, normalizar
from .interprete import Orden

TIPOS = {
    "abrir_app",
    "crear_carpeta",
    "abrir_carpeta",
    "abrir_ultima",
    "captura",
    "buscar_web",
    "youtube",
    "sitio",
    "volumen",
    "escritorio",
    "cerrar_ventana",
    "escribir",
}

CAMPOS = {
    "abrir_app": {"clave", "termino"},
    "crear_carpeta": {"nombre", "ubicacion"},
    "abrir_carpeta": {"nombre", "ubicacion"},
    "abrir_ultima": set(),
    "captura": set(),
    "buscar_web": {"consulta", "navegador"},
    "youtube": {"consulta", "reproducir"},
    "sitio": {"direccion", "nombre"},
    "volumen": {"accion"},
    "escritorio": set(),
    "cerrar_ventana": set(),
    "escribir": {"texto"},
}

NAVEGADORES = {"chrome", "edge", "firefox"}
ACCIONES_VOLUMEN = {"subir", "bajar", "silenciar"}

_SOLO_TEXTO = re.compile(r"[^\w\s\.\-áéíóúüñÁÉÍÓÚÜÑ()]", re.UNICODE)
_DOMINIO = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)


def _texto(valor, maximo: int) -> str:
    if valor is None:
        return ""
    texto = str(valor).replace("\x00", " ")
    texto = "".join(c for c in texto if c in "\n\t" or ord(c) >= 32)
    return re.sub(r"[ \t]+", " ", texto).strip()[:maximo]


def _ubicacion(valor) -> str:
    texto = normalizar(_texto(valor, 40))
    if not texto:
        return ""
    directa = clave_ubicacion(texto)
    if directa:
        return directa
    for clave, etiqueta in ETIQUETAS.items():
        if normalizar(etiqueta.split()[-1]) in texto:
            return clave
    for clave in ("escritorio", "documentos", "descargas", "imagenes"):
        if clave in texto:
            return clave
    return ""


def _termino(valor) -> str:
    texto = _texto(valor, 80)
    texto = _SOLO_TEXTO.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip(" .")


def _resumen(valor, respaldo: str) -> str:
    texto = _texto(valor, 160)
    return texto or respaldo


def _url(valor) -> tuple[str, str]:
    direccion = _texto(valor, 300)
    if not direccion:
        return "", ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", direccion):
        direccion = "https://" + direccion
    try:
        partes = urlparse(direccion)
    except ValueError:
        return "", ""
    if partes.scheme not in ("http", "https"):
        return "", ""
    host = (partes.hostname or "").strip().lower()
    if not host or len(host) > 253 or not _DOMINIO.match(host):
        return "", ""
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return "", ""
    if re.match(r"^(127\.|10\.|0\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host):
        return "", ""
    if host in {"::1", "0:0:0:0:0:0:0:1"}:
        return "", ""
    if any(c in direccion for c in "\r\n\t \"'<>"):
        return "", ""
    try:
        puerto = partes.port
    except ValueError:
        return "", ""
    # Reconstruimos sin usuario/contraseña para no abrir direcciones engañosas.
    limpia = f"{partes.scheme}://{host}"
    if puerto:
        limpia += f":{puerto}"
    limpia += partes.path or "/"
    if partes.query:
        limpia += "?" + partes.query
    return limpia[:300], host


def validar_ordenes(lista, texto_usuario: str = "", maximo: int = 8) -> list[Orden]:
    """Convierte la respuesta cruda de la IA en órdenes seguras.

    Lanza ValueError si no queda ninguna orden válida.
    """
    if not isinstance(lista, list):
        raise ValueError("La IA no devolvió una lista de órdenes.")
    ordenes: list[Orden] = []
    for elemento in lista[:maximo]:
        if not isinstance(elemento, dict):
            continue
        tipo = str(elemento.get("tipo", "")).strip().lower()
        if tipo not in TIPOS:
            continue
        datos_entrada = elemento.get("datos") or {}
        if not isinstance(datos_entrada, dict):
            datos_entrada = {}
        # Solo dejamos pasar los campos permitidos para cada acción.
        datos = {k: v for k, v in datos_entrada.items() if k in CAMPOS[tipo]}
        resumen = _resumen(elemento.get("resumen"), "")

        if tipo == "abrir_app":
            clave = _texto(datos.get("clave"), 40).lower()
            termino = _termino(datos.get("termino"))
            if clave in CATALOGO:
                datos = {"clave": clave}
                resumen = resumen or f"Abrir {CATALOGO[clave].nombre}"
            elif termino:
                datos = {"termino": termino}
                resumen = resumen or f"Abrir «{termino}»"
            else:
                continue

        elif tipo == "crear_carpeta":
            nombre = limpiar_nombre_archivo(_texto(datos.get("nombre"), 100)) or "Nueva carpeta"
            ubicacion = _ubicacion(datos.get("ubicacion")) or "escritorio"
            datos = {"nombre": nombre, "ubicacion": ubicacion}
            resumen = resumen or f"Crear la carpeta «{nombre}» en {ETIQUETAS[ubicacion]}"

        elif tipo == "abrir_carpeta":
            nombre = limpiar_nombre_archivo(_texto(datos.get("nombre"), 100))
            ubicacion = _ubicacion(datos.get("ubicacion"))
            datos = {}
            if nombre:
                datos["nombre"] = nombre
            if ubicacion:
                datos["ubicacion"] = ubicacion
            if not datos:
                resumen = resumen or "Abrir el Explorador de archivos"
            else:
                resumen = resumen or (
                    f"Abrir la carpeta «{nombre}»" if nombre else f"Abrir {ETIQUETAS[ubicacion]}"
                )

        elif tipo == "buscar_web":
            consulta = _texto(datos.get("consulta"), 200)
            navegador = _texto(datos.get("navegador"), 20).lower()
            if navegador not in NAVEGADORES:
                navegador = "chrome"
            if not consulta:
                continue
            datos = {"consulta": consulta, "navegador": navegador}
            resumen = resumen or f"Buscar «{consulta}» en internet"

        elif tipo == "youtube":
            consulta = _texto(datos.get("consulta"), 200)
            reproducir = bool(datos.get("reproducir"))
            if not consulta and not reproducir:
                continue
            datos = {"consulta": consulta, "reproducir": reproducir}
            if consulta:
                resumen = resumen or (
                    f"Reproducir «{consulta}» en YouTube"
                    if reproducir
                    else f"Buscar «{consulta}» en YouTube"
                )
            else:
                resumen = resumen or "Abrir YouTube"

        elif tipo == "sitio":
            direccion, host = _url(datos.get("direccion"))
            if not direccion:
                continue
            nombre = _texto(datos.get("nombre"), 80) or host
            datos = {"direccion": direccion, "nombre": nombre}
            resumen = resumen or f"Abrir la página {host}"

        elif tipo == "volumen":
            accion = _texto(datos.get("accion"), 20).lower()
            if accion not in ACCIONES_VOLUMEN:
                continue
            datos = {"accion": accion}
            resumen = resumen or {
                "subir": "Subir el volumen",
                "bajar": "Bajar el volumen",
                "silenciar": "Silenciar el sonido",
            }[accion]

        elif tipo == "escribir":
            contenido = _texto(datos.get("texto"), 500)
            if not contenido:
                continue
            datos = {"texto": contenido}
            resumen = resumen or f"Escribir «{contenido[:60]}»"

        elif tipo == "abrir_ultima":
            resumen = resumen or "Abrir la carpeta que acabo de crear"

        elif tipo == "captura":
            resumen = resumen or "Tomar una captura de pantalla"

        elif tipo == "escritorio":
            resumen = resumen or "Mostrar el escritorio"

        elif tipo == "cerrar_ventana":
            resumen = resumen or "Cerrar la ventana actual"

        ordenes.append(
            Orden(
                tipo=tipo,
                datos=datos,
                resumen=resumen[:160],
                texto=texto_usuario,
            )
        )
    if not ordenes:
        raise ValueError("La IA no devolvió ninguna acción válida.")
    return ordenes
