"""Sesión, preferencias y cola de sincronización de la app."""

from __future__ import annotations

import base64
import binascii
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .. import configuracion as cfg


# --- Utilidades de archivos -------------------------------------------------

def _leer_json(ruta, defecto):
    try:
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return defecto


def _escribir_json(ruta, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, ruta)


# --- Token ------------------------------------------------------------------

def _payload_token(token: str) -> dict:
    try:
        partes = token.split(".")
        if len(partes) != 3:
            return {}
        cuerpo = partes[1] + "=" * (-len(partes[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(cuerpo).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return {}


# --- Sesión -----------------------------------------------------------------

@dataclass
class Sesion:
    token: str = ""
    usuario: dict = field(default_factory=dict)
    base_url: str = ""
    modo: str = "nube"

    @property
    def id(self) -> Optional[int]:
        valor = self.usuario.get("id")
        try:
            return int(valor) if valor is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def nombre(self) -> str:
        return str(self.usuario.get("nombre") or "amigo")

    @property
    def telefono(self) -> str:
        return str(self.usuario.get("telefono") or "")

    @property
    def es_local(self) -> bool:
        return self.modo == "local"

    def vigente(self) -> bool:
        if self.es_local:
            return True
        datos = _payload_token(self.token)
        if not datos:
            return False
        try:
            return int(datos.get("exp", 0)) > int(time.time()) + 30
        except (TypeError, ValueError):
            return False

    def guardar(self) -> None:
        if self.es_local:
            return
        _escribir_json(
            cfg.RUTA_SESION,
            {
                "token": self.token,
                "usuario": self.usuario,
                "base_url": self.base_url,
                "modo": self.modo,
                "guardada_en": time.time(),
            },
        )

    @classmethod
    def cargar(cls) -> Optional["Sesion"]:
        datos = _leer_json(cfg.RUTA_SESION, {})
        if not isinstance(datos, dict) or not datos.get("token"):
            return None
        sesion = cls(
            token=str(datos.get("token", "")),
            usuario=datos.get("usuario") if isinstance(datos.get("usuario"), dict) else {},
            base_url=str(datos.get("base_url") or cfg.URL_SERVIDOR),
            modo=str(datos.get("modo") or "nube"),
        )
        return sesion if sesion.vigente() else None

    @classmethod
    def borrar(cls) -> None:
        try:
            cfg.RUTA_SESION.unlink(missing_ok=True)
        except OSError:
            pass


# --- Preferencias -----------------------------------------------------------

def cargar_preferencias() -> dict:
    datos = _leer_json(cfg.RUTA_PREFERENCIAS, {})
    return datos if isinstance(datos, dict) else {}


def guardar_preferencias(datos: dict) -> None:
    actuales = cargar_preferencias()
    actuales.update(datos or {})
    try:
        _escribir_json(cfg.RUTA_PREFERENCIAS, actuales)
    except OSError:
        pass


# --- Cola de sincronización -------------------------------------------------

class Cola:
    """Guarda lo que no se pudo enviar al servidor y lo reintenta después."""

    MAXIMO = 200

    def __init__(self, ruta=None):
        self.ruta = ruta or cfg.RUTA_PENDIENTES
        self._cerrojo = threading.Lock()

    def _leer(self) -> list:
        datos = _leer_json(self.ruta, [])
        return datos if isinstance(datos, list) else []

    def _guardar(self, lista: list) -> None:
        try:
            _escribir_json(self.ruta, lista[-self.MAXIMO :])
        except OSError:
            pass

    def agregar(self, tipo: str, datos: dict) -> None:
        with self._cerrojo:
            lista = self._leer()
            lista.append(
                {
                    "id": uuid.uuid4().hex,
                    "tipo": tipo,
                    "datos": datos or {},
                    "creado_en": time.time(),
                }
            )
            self._guardar(lista)

    def pendientes(self) -> list:
        with self._cerrojo:
            return list(self._leer())

    def contar(self) -> int:
        return len(self.pendientes())

    def quitar(self, identificador: str) -> None:
        with self._cerrojo:
            self._guardar([p for p in self._leer() if p.get("id") != identificador])

    def sincronizar(self, cliente) -> tuple[int, int]:
        from .nube import ErrorNube

        enviados = 0
        for elemento in self.pendientes():
            tipo = elemento.get("tipo")
            datos = elemento.get("datos") or {}
            try:
                if tipo == "offline":
                    cliente.registrar_offline(**datos)
                elif tipo == "resultado":
                    cliente.reportar(**datos)
                elif tipo == "feedback":
                    cliente.feedback(**datos)
                else:
                    self.quitar(str(elemento.get("id")))
                    continue
            except ErrorNube as error:
                if error.sin_conexion or error.codigo in (401, 403):
                    # Sin conexión o sesión vencida: no perdemos lo pendiente.
                    break
                # Un error de datos no debe bloquear toda la cola.
                self.quitar(str(elemento.get("id")))
                continue
            except TypeError:
                self.quitar(str(elemento.get("id")))
                continue
            self.quitar(str(elemento.get("id")))
            enviados += 1
        return enviados, self.contar()
