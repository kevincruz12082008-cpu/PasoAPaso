"""Servidor HTTP de PasoAPaso.

Usa solo la biblioteca estándar: http.server + sqlite3. Sirve la API que
consume la app de escritorio, el portal web y el panel de administración.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import socketserver
import threading
import traceback
import urllib.parse
from datetime import datetime, timezone
from email.message import Message
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

from . import base_datos, config, seguridad, vistas

LOG = logging.getLogger("pasoapaso.servidor")


class ErrorHTTP(Exception):
    def __init__(self, codigo: int, mensaje: str, api: bool = False):
        super().__init__(mensaje)
        self.codigo = int(codigo)
        self.mensaje = mensaje
        self.api = api


class Peticion:
    def __init__(self, manejador: "Manejador"):
        self.manejador = manejador
        self.servidor = manejador.server
        self.metodo = manejador.command
        self.ruta_original = manejador.path
        partes = urllib.parse.urlsplit(manejador.path)
        self.ruta = urllib.parse.unquote(partes.path)
        self.consulta = urllib.parse.parse_qs(partes.query, keep_blank_values=True)
        self.cabeceras: Message = manejador.headers
        self.cookies = seguridad.leer_cookies(manejador.headers.get("Cookie", ""))
        self.cookies_salida: list[tuple[str, str, int, bool]] = []
        self.cuerpo = b""
        self.params: dict[str, str] = {}
        self.usuario: Optional[dict] = None
        self.admin: Optional[dict] = None
        self.ip = self._ip()
        self._form = None
        self._json = None

    def _ip(self) -> str:
        if config.PRODUCCION and config.PROXY:
            reenviado = self.cabeceras.get("X-Forwarded-For", "")
            if reenviado:
                return reenviado.split(",")[0].strip()
        return self.manejador.client_address[0] if self.manejador.client_address else "?"

    @property
    def es_api(self) -> bool:
        return self.ruta.startswith("/api/")

    @property
    def secure(self) -> bool:
        return seguridad.es_https(self.cabeceras)

    def dato(self, nombre: str, defecto: str = "") -> str:
        if self.metodo == "POST":
            valores = self.form().get(nombre)
            if valores:
                return valores[0]
        valores = self.consulta.get(nombre)
        return valores[0] if valores else defecto

    def entero(self, nombre: str, defecto: int = 0) -> int:
        try:
            return int(self.dato(nombre, str(defecto)))
        except (TypeError, ValueError):
            return defecto

    def form(self) -> dict:
        if self._form is not None:
            return self._form
        if self.metodo != "POST":
            self._form = {}
            return self._form
        tipo = self.cabeceras.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in tipo or "multipart/form-data" in tipo:
            try:
                self._form = urllib.parse.parse_qs(
                    self.cuerpo.decode("utf-8", "replace"), keep_blank_values=True
                )
            except Exception:
                self._form = {}
        else:
            self._form = {}
        return self._form

    def json(self) -> dict:
        if self._json is not None:
            return self._json
        if not self.cuerpo:
            self._json = {}
            return self._json
        try:
            datos = json.loads(self.cuerpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ErrorHTTP(400, "El cuerpo de la petición no es JSON válido.", api=True) from error
        if not isinstance(datos, dict):
            raise ErrorHTTP(400, "Se esperaba un objeto JSON.", api=True)
        self._json = datos
        return datos

    def poner_cookie(self, nombre: str, valor: str, segundos: int, http_only: bool = True) -> None:
        self.cookies_salida.append((nombre, valor, segundos, http_only))

    def borrar_cookie(self, nombre: str) -> None:
        self.poner_cookie(nombre, "", 0)

    def token_bearer(self) -> str:
        autorizacion = self.cabeceras.get("Authorization", "")
        if autorizacion.lower().startswith("bearer "):
            return autorizacion[7:].strip()
        return ""


class Respuesta:
    def __init__(
        self,
        codigo: int = 200,
        cuerpo: bytes = b"",
        tipo: str = "text/html; charset=utf-8",
        cabeceras: Optional[list[tuple[str, str]]] = None,
    ):
        self.codigo = int(codigo)
        self.cuerpo = cuerpo
        self.tipo = tipo
        self.cabeceras = cabeceras or []

    @classmethod
    def html(cls, contenido: str, codigo: int = 200) -> "Respuesta":
        return cls(codigo, contenido.encode("utf-8"), "text/html; charset=utf-8")

    @classmethod
    def json(cls, datos, codigo: int = 200) -> "Respuesta":
        cuerpo = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return cls(codigo, cuerpo, "application/json; charset=utf-8")

    @classmethod
    def texto(cls, contenido: str, codigo: int = 200) -> "Respuesta":
        return cls(codigo, contenido.encode("utf-8"), "text/plain; charset=utf-8")

    @classmethod
    def redirigir(cls, destino: str, codigo: int = 303) -> "Respuesta":
        return cls(codigo, b"", "text/plain; charset=utf-8", [("Location", destino)])

    @classmethod
    def archivo(
        cls,
        ruta: Path,
        tipo: Optional[str] = None,
        descargar: Optional[str] = None,
        cache: str = "public, max-age=3600",
    ) -> "Respuesta":
        datos = ruta.read_bytes()
        tipo = tipo or mimetypes.guess_type(str(ruta))[0] or "application/octet-stream"
        cabeceras = [("Cache-Control", cache)]
        if descargar:
            cabeceras.append(
                ("Content-Disposition", f'attachment; filename="{descargar}"')
            )
        return cls(200, datos, tipo, cabeceras)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, direccion, manejador, ruta_db: Optional[Path] = None):
        super().__init__(direccion, manejador)
        self.ruta_db = Path(ruta_db or config.RUTA_DB)
        self.inicio = datetime.now(timezone.utc)


class Manejador(BaseHTTPRequestHandler):
    server_version = f"PasoAPaso/{config.VERSION}"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # --- Entrada ---------------------------------------------------------
    def do_GET(self):
        self._atender()

    def do_POST(self):
        self._atender()

    def do_HEAD(self):
        self._atender()

    def _leer_cuerpo(self) -> bytes:
        try:
            largo = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            largo = 0
        if largo > config.MAX_CUERPO:
            raise ErrorHTTP(413, "La petición es demasiado grande.", api=self.path.startswith("/api/"))
        return self.rfile.read(largo) if largo > 0 else b""

    def _atender(self) -> None:
        try:
            peticion = Peticion(self)
            if self.command == "POST":
                peticion.cuerpo = self._leer_cuerpo()
            self._autenticar(peticion)
            respuesta = self._buscar_ruta(peticion)
        except ErrorHTTP as error:
            respuesta = self._respuesta_error(error)
        except Exception:
            LOG.exception("Error no controlado en %s %s", self.command, self.path)
            respuesta = self._respuesta_error(
                ErrorHTTP(500, "Ocurrió un error inesperado en el servidor.", self.path.startswith("/api/"))
            )
        else:
            if respuesta is None:
                respuesta = self._respuesta_error(
                    ErrorHTTP(404, "No encontré esa página.", self.path.startswith("/api/"))
                )
        try:
            self._enviar(peticion, respuesta)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _autenticar(self, peticion: Peticion) -> None:
        # Usuario: primero el token Bearer de la app, luego la cookie del portal.
        token = peticion.token_bearer() or peticion.cookies.get("pa_sesion", "")
        datos = seguridad.leer_token(token) if token else None
        if datos and datos.get("rol") == "usuario":
            try:
                usuario = base_datos.obtener_usuario(int(datos.get("sub", 0)))
            except (TypeError, ValueError):
                usuario = None
            if (
                usuario
                and int(usuario.get("activo", 0)) == 1
                and int(datos.get("v", 0)) == int(usuario.get("token_version", 0))
            ):
                peticion.usuario = usuario
        # Administrador: solo por cookie.
        token_admin = peticion.cookies.get("pa_admin", "")
        datos_admin = seguridad.leer_token(token_admin) if token_admin else None
        if datos_admin and datos_admin.get("rol") == "admin":
            try:
                admin = base_datos.obtener_admin(int(datos_admin.get("sub", 0)))
            except (TypeError, ValueError):
                admin = None
            if admin and int(datos_admin.get("v", 0)) == int(admin.get("token_version", 0)):
                peticion.admin = admin

    def _buscar_ruta(self, peticion: Peticion) -> Optional[Respuesta]:
        from .rutas import RUTAS

        for metodo, patron, funcion in RUTAS:
            if metodo != peticion.metodo and not (metodo == "GET" and peticion.metodo == "HEAD"):
                continue
            coincidencia = patron.fullmatch(peticion.ruta)
            if not coincidencia:
                continue
            peticion.params = coincidencia.groupdict()
            return funcion(peticion)
        if peticion.metodo in ("GET", "HEAD"):
            if peticion.ruta.startswith("/estatico/"):
                return self._estatico(peticion, config.DIR_ESTATICOS, "/estatico/")
            if peticion.ruta.startswith("/recursos/"):
                return self._estatico(peticion, config.DIR_RECURSOS, "/recursos/")
        return None

    def _estatico(self, peticion: Peticion, base: Path, prefijo: str) -> Respuesta:
        relativa = peticion.ruta[len(prefijo):]
        if not relativa or ".." in Path(relativa).parts:
            raise ErrorHTTP(404, "Archivo no encontrado.")
        destino = (base / relativa).resolve()
        try:
            destino.relative_to(base.resolve())
        except ValueError as error:
            raise ErrorHTTP(404, "Archivo no encontrado.") from error
        if not destino.is_file():
            raise ErrorHTTP(404, "Archivo no encontrado.")
        return Respuesta.archivo(destino)

    def _respuesta_error(self, error: ErrorHTTP) -> Respuesta:
        if error.api:
            return Respuesta.json({"ok": False, "error": error.mensaje}, error.codigo)
        html = vistas.pagina_error(error.codigo, error.mensaje)
        return Respuesta.html(html, error.codigo)

    def _enviar(self, peticion: Peticion, respuesta: Respuesta) -> None:
        self.send_response(respuesta.codigo)
        self.send_header("Content-Type", respuesta.tipo)
        self.send_header("Content-Length", str(len(respuesta.cuerpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header(
            "Permissions-Policy",
            "microphone=(), camera=(), geolocation=(), payment=()",
        )
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        if respuesta.tipo.startswith("text/html") or respuesta.tipo.startswith("application/json"):
            self.send_header("Cache-Control", "no-store")
        for nombre, valor in respuesta.cabeceras:
            self.send_header(nombre, valor)
        for nombre, valor, segundos, http_only in peticion.cookies_salida:
            cookie = seguridad.hacer_cookie(nombre, valor, segundos, peticion.secure)
            if not http_only:
                cookie = cookie.replace("; HttpOnly", "")
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(respuesta.cuerpo)

    # --- Registro --------------------------------------------------------
    def log_message(self, formato: str, *argumentos) -> None:
        LOG.info("%s - %s", self.address_string(), formato % argumentos)

    def log_error(self, formato: str, *argumentos) -> None:
        LOG.warning("%s - %s", self.address_string(), formato % argumentos)


# --- Decoradores de acceso --------------------------------------------------

def solo_usuario(funcion: Callable) -> Callable:
    def envoltura(peticion: Peticion) -> Respuesta:
        if not peticion.usuario:
            if peticion.es_api:
                raise ErrorHTTP(401, "Tu sesión venció. Vuelve a iniciar sesión.", api=True)
            destino = urllib.parse.quote(peticion.ruta, safe="/")
            return Respuesta.redirigir(f"/entrar?next={destino}")
        return funcion(peticion)

    envoltura.__name__ = funcion.__name__
    return envoltura


def solo_admin(funcion: Callable) -> Callable:
    def envoltura(peticion: Peticion) -> Respuesta:
        if not peticion.admin:
            if peticion.es_api:
                raise ErrorHTTP(401, "Se requiere sesión de administrador.", api=True)
            return Respuesta.redirigir("/admin/entrar")
        return funcion(peticion)

    envoltura.__name__ = funcion.__name__
    return envoltura


def csrf_valido(peticion: Peticion) -> None:
    enviado = peticion.form().get("_csrf", [""])[0]
    guardado = peticion.cookies.get("pa_csrf", "")
    if not enviado or not guardado or not seguridad.iguales(enviado, guardado):
        raise ErrorHTTP(403, "La página venció. Recarga e intenta de nuevo.")


def csrf_token(peticion: Peticion) -> str:
    token = peticion.cookies.get("pa_csrf", "")
    if not token or len(token) < 20:
        token = seguridad.nuevo_csrf()
        peticion.cookies["pa_csrf"] = token
        peticion.poner_cookie("pa_csrf", token, 12 * 3600)
    return token


# --- Arranque ---------------------------------------------------------------

def crear_servidor(
    host: str = config.HOST,
    puerto: int = config.PUERTO,
    ruta_db: Optional[Path] = None,
) -> Servidor:
    ruta = base_datos.inicializar(ruta_db)
    config.RUTA_DB = ruta
    servidor = Servidor((host, int(puerto)), Manejador, ruta)
    LOG.info("Base de datos: %s", ruta)
    return servidor


def iniciar_en_hilo(
    host: str = "127.0.0.1", puerto: int = config.PUERTO
) -> tuple[Servidor, threading.Thread, str]:
    servidor = crear_servidor(host, puerto)
    hilo = threading.Thread(target=servidor.serve_forever, name="pasoapaso-http", daemon=True)
    hilo.start()
    url = f"http://{host}:{servidor.server_address[1]}"
    LOG.info("Servidor escuchando en %s", url)
    return servidor, hilo, url


def servidor_activo(url: str, timeout: float = 1.2) -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(url.rstrip("/") + "/salud", timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
            return bool(datos.get("ok")) and datos.get("app") == config.NOMBRE_APP
    except Exception:
        return False
