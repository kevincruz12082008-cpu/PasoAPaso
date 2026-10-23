"""Cliente de la API de PasoAPaso.

La app de escritorio usa este módulo para hablar con el servidor (local o
en internet). Solo usa la biblioteca estándar. Si el servidor no responde,
la app puede seguir funcionando con las reglas locales y guardar lo que
pasó para sincronizarlo después.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from .. import configuracion as cfg


class ErrorNube(Exception):
    def __init__(self, mensaje: str, codigo: int = 0, sin_conexion: bool = False):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.sin_conexion = sin_conexion

    def __str__(self) -> str:
        return self.mensaje


@dataclass
class Respuesta:
    datos: dict = field(default_factory=dict)

    def __getitem__(self, clave):
        return self.datos.get(clave)


class ClienteNube:
    def __init__(self, base_url: Optional[str] = None, token: str = "", timeout: Optional[float] = None):
        self.base_url = (base_url or cfg.URL_SERVIDOR).rstrip("/")
        self.token = token or ""
        self.timeout = timeout or cfg.TIEMPO_ESPERA_NUBE

    # --- Interno ---------------------------------------------------------
    def _pedir(
        self,
        metodo: str,
        ruta: str,
        datos: Optional[dict] = None,
        con_token: bool = True,
        timeout: Optional[float] = None,
    ) -> dict:
        url = self.base_url + ruta
        cuerpo = None
        cabeceras = {"Accept": "application/json", "User-Agent": f"PasoAPaso/{cfg.VERSION}"}
        if datos is not None:
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            cabeceras["Content-Type"] = "application/json; charset=utf-8"
        if con_token and self.token:
            cabeceras["Authorization"] = "Bearer " + self.token
        solicitud = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(solicitud, timeout=timeout or self.timeout) as respuesta:
                contenido = respuesta.read()
        except urllib.error.HTTPError as error:
            mensaje = f"El servidor respondió con error {error.code}."
            try:
                crudo = error.read().decode("utf-8", "replace")
                datos_error = json.loads(crudo)
                mensaje = datos_error.get("error") or mensaje
            except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                pass
            raise ErrorNube(mensaje, error.code, sin_conexion=False) from error
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as error:
            raise ErrorNube(
                "No pude conectar con el servidor. Revisa tu internet o inténtalo más tarde.",
                0,
                sin_conexion=True,
            ) from error

        if not contenido:
            return {}
        try:
            return json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ErrorNube("El servidor envió una respuesta que no entendí.") from error

    # --- Público ---------------------------------------------------------
    def disponible(self) -> bool:
        try:
            datos = self._pedir("GET", "/api/estado", con_token=False)
            return bool(datos.get("ok"))
        except ErrorNube:
            return False

    def estado(self) -> dict:
        return self._pedir("GET", "/api/estado", con_token=False)

    def registrar(
        self,
        telefono: str,
        nombre: str,
        clave: str,
        edad=None,
        ciudad: str = "",
        experiencia: str = "poco",
        como_nos_conocio: str = "",
        consentimiento: bool = True,
    ) -> dict:
        datos = self._pedir(
            "POST",
            "/api/registro",
            {
                "telefono": telefono,
                "nombre": nombre,
                "clave": clave,
                "clave2": clave,
                "edad": edad if edad not in (None, "") else None,
                "ciudad": ciudad,
                "experiencia": experiencia,
                "como_nos_conocio": como_nos_conocio,
                "consentimiento": bool(consentimiento),
            },
            con_token=False,
        )
        if datos.get("token"):
            self.token = datos["token"]
        return datos

    def entrar(self, telefono: str, clave: str) -> dict:
        datos = self._pedir(
            "POST",
            "/api/login",
            {"telefono": telefono, "clave": clave},
            con_token=False,
        )
        if datos.get("token"):
            self.token = datos["token"]
        return datos

    def perfil(self) -> dict:
        return self._pedir("GET", "/api/perfil")

    def interpretar(self, texto: str, origen: str = "texto") -> dict:
        return self._pedir(
            "POST",
            "/api/interpretar",
            {"texto": texto, "origen": origen},
            # Gemini puede tardar más que las demás peticiones; con 8 s la app
            # se rendía antes y caía al modo local sin usar la IA.
            timeout=max(self.timeout, 35.0),
        )

    def reportar(
        self,
        prompt_id: int,
        estado: str,
        error: str = "",
        duracion_ms: int = 0,
        acciones=None,
    ) -> dict:
        return self._pedir(
            "POST",
            f"/api/prompts/{int(prompt_id)}/resultado",
            {
                "estado": estado,
                "error": error,
                "duracion_ms": int(duracion_ms),
                "acciones": acciones or [],
            },
        )

    def registrar_offline(
        self,
        texto: str,
        origen: str,
        estado: str,
        ordenes,
        creado_en: str,
        duracion_ms: int = 0,
        error: str = "",
    ) -> dict:
        return self._pedir(
            "POST",
            "/api/prompts/offline",
            {
                "texto": texto,
                "origen": origen,
                "estado": estado,
                "ordenes": ordenes or [],
                "creado_en": creado_en,
                "duracion_ms": int(duracion_ms),
                "error": error,
            },
        )

    def historial(self, limite: int = 30) -> dict:
        return self._pedir("GET", f"/api/historial?limite={int(limite)}")

    def feedback(self, prompt_id: int, util: bool, comentario: str = "") -> dict:
        return self._pedir(
            "POST",
            "/api/feedback",
            {"prompt_id": int(prompt_id), "util": bool(util), "comentario": comentario},
        )

    def url_admin(self) -> str:
        return self.base_url + "/admin"
