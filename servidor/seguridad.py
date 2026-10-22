"""Contraseñas, tokens, cookies y validaciones de seguridad.

Se usa solo la biblioteca estándar. Los tokens son JWT firmados con
HMAC-SHA256 y las claves se guardan con PBKDF2-SHA256 y sal aleatoria.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from typing import Optional

from . import config

_ITERACIONES = 260_000


# --- Texto y teléfonos ------------------------------------------------------

def limpiar_texto(texto, maximo: int = 500) -> str:
    if texto is None:
        return ""
    texto = str(texto).replace("\x00", " ")
    texto = "".join(
        caracter
        for caracter in texto
        if caracter in "\n\t" or ord(caracter) >= 32
    )
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()[:maximo]


def limpiar_nombre(texto, maximo: int = 80) -> str:
    texto = limpiar_texto(texto, maximo)
    texto = re.sub(r"\s+", " ", texto)
    return texto[:maximo].strip()


def normalizar_telefono(texto) -> str:
    if texto is None:
        return ""
    digitos = re.sub(r"\D", "", str(texto))
    if digitos.startswith("00"):
        digitos = digitos[2:]
    return digitos[:15]


def telefono_valido(telefono: str) -> bool:
    return 8 <= len(telefono) <= 15


def normalizar_pin(texto) -> str:
    if texto is None:
        return ""
    return re.sub(r"\D", "", str(texto))


def pin_valido(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{4,8}", pin or ""))


def validar_clave_admin(clave: str) -> Optional[str]:
    if not clave or len(clave) < 8:
        return "La clave del administrador debe tener al menos 8 caracteres."
    if len(clave) > 128:
        return "La clave del administrador es demasiado larga."
    return None


def normalizar_experiencia(valor: str) -> str:
    valor = (valor or "").strip().lower()
    return valor if valor in config.EXPERIENCIAS else "poco"


def normalizar_origen(valor: str) -> str:
    valor = (valor or "").strip().lower()
    return valor if valor in config.ORIGENES else "texto"


def normalizar_estado(valor: str) -> str:
    valor = (valor or "").strip().lower()
    return valor if valor in config.ESTADOS else "pendiente"


# --- Claves -----------------------------------------------------------------

def _b64e(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def _b64d(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, _ITERACIONES)
    return f"pbkdf2_sha256${_ITERACIONES}${_b64e(sal)}${_b64e(derivada)}"


def verificar_clave(clave: str, guardada: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperada = (guardada or "").split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256",
            (clave or "").encode("utf-8"),
            _b64d(sal),
            int(iteraciones),
        )
        return hmac.compare_digest(_b64e(derivada), esperada)
    except (ValueError, TypeError, binascii.Error):
        return False


def nuevo_pin(cantidad: int = 4) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(cantidad))


# --- Tokens JWT -------------------------------------------------------------

def _firmar(contenido: str) -> str:
    firma = hmac.new(
        config.SECRETO.encode("utf-8"), contenido.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64e(firma)


def crear_token(payload: dict, horas: int) -> str:
    ahora = int(time.time())
    datos = dict(payload)
    datos.setdefault("iat", ahora)
    datos["exp"] = ahora + int(horas * 3600)
    cabecera = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = _b64e(json.dumps(datos, separators=(",", ":"), ensure_ascii=False).encode())
    contenido = f"{cabecera}.{cuerpo}"
    return f"{contenido}.{_firmar(contenido)}"


def leer_token(token: str) -> Optional[dict]:
    if not token or token.count(".") != 2:
        return None
    try:
        cabecera, cuerpo, firma = token.split(".")
        if not hmac.compare_digest(_firmar(f"{cabecera}.{cuerpo}"), firma):
            return None
        datos = json.loads(_b64d(cuerpo).decode("utf-8"))
        if int(datos.get("exp", 0)) < int(time.time()):
            return None
        return datos
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
        return None


def token_usuario(usuario_id: int, version: int = 0) -> str:
    return crear_token(
        {"sub": str(usuario_id), "rol": "usuario", "v": int(version)},
        config.SESION_HORAS,
    )


def token_admin(admin_id: int, version: int = 0) -> str:
    return crear_token(
        {"sub": str(admin_id), "rol": "admin", "v": int(version)},
        config.ADMIN_SESION_HORAS,
    )


# --- Cookies ----------------------------------------------------------------

def leer_cookies(cabecera: str) -> dict:
    cookies = {}
    if not cabecera:
        return cookies
    try:
        analizador = SimpleCookie()
        analizador.load(cabecera)
        for clave, morsel in analizador.items():
            cookies[clave] = morsel.value
    except Exception:
        pass
    return cookies


def es_https(cabeceras) -> bool:
    if config.PRODUCCION and config.PROXY:
        reenviado = cabeceras.get("X-Forwarded-Proto", "")
        if reenviado:
            return reenviado.split(",")[0].strip().lower() == "https"
    return False


def hacer_cookie(nombre: str, valor: str, segundos: int, secure: bool) -> str:
    partes = [
        f"{nombre}={valor}",
        "Path=/",
        f"Max-Age={int(segundos)}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        partes.append("Secure")
    return "; ".join(partes)


def borrar_cookie(nombre: str, secure: bool) -> str:
    return hacer_cookie(nombre, "", 0, secure)


def nuevo_csrf() -> str:
    return secrets.token_urlsafe(24)


def iguales(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


# --- Límite de intentos -----------------------------------------------------

class Limitador:
    """Límite sencillo en memoria para los intentos de acceso."""

    def __init__(self, maximo: int, ventana_segundos: int):
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._fallos: dict[str, list[float]] = {}
        self._cerrojo = threading.Lock()

    def _limpiar(self, clave: str) -> None:
        ahora = time.time()
        lista = [t for t in self._fallos.get(clave, []) if ahora - t < self.ventana]
        if lista:
            self._fallos[clave] = lista
        else:
            self._fallos.pop(clave, None)

    def permitido(self, clave: str) -> bool:
        with self._cerrojo:
            self._limpiar(clave)
            return len(self._fallos.get(clave, [])) < self.maximo

    def fallo(self, clave: str) -> None:
        with self._cerrojo:
            self._limpiar(clave)
            self._fallos.setdefault(clave, []).append(time.time())

    def limpiar(self, clave: str) -> None:
        with self._cerrojo:
            self._fallos.pop(clave, None)

    def faltan(self, clave: str) -> int:
        with self._cerrojo:
            self._limpiar(clave)
            return max(0, self.maximo - len(self._fallos.get(clave, [])))
