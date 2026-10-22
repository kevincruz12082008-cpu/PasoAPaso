"""Salida de voz (leer los pasos en voz alta) usando Windows.

No usa librerías externas: abre un proceso de Windows PowerShell que
mantiene el sintetizador de voz de Windows escuchando líneas de texto.
Si la voz no está disponible, la app sigue funcionando en silencio.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path

from .. import configuracion as cfg
from .plataforma import es_windows

SCRIPT = Path(__file__).with_name("hablar.ps1")


class VozSalida:
    def __init__(self):
        self._cola: queue.Queue = queue.Queue()
        self._proceso = None
        self._hilo = None
        self._activa = False
        self._cerrada = False
        self._cerrojo = threading.Lock()
        self._ultimo = ""
        self._fallos = 0

    def disponible(self) -> bool:
        return es_windows() and SCRIPT.exists()

    def activar(self, activa: bool) -> None:
        self._activa = bool(activa)
        if not activa:
            self.detener()

    def _asegurar_proceso(self) -> bool:
        if self._proceso and self._proceso.poll() is None:
            return True
        try:
            banderas = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                banderas = subprocess.CREATE_NO_WINDOW
            self._proceso = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=banderas,
            )
            return True
        except OSError:
            self._fallos += 1
            return False

    def _trabajar(self) -> None:
        while not self._cerrada:
            try:
                texto = self._cola.get(timeout=0.3)
            except queue.Empty:
                continue
            if texto is None:
                break
            if not texto or texto == self._ultimo:
                continue
            if not self._asegurar_proceso():
                continue
            try:
                self._proceso.stdin.write(texto.replace("\n", " ").strip()[:300] + "\n")
                self._proceso.stdin.flush()
                self._ultimo = texto
            except (OSError, ValueError):
                self._detener_proceso()

    def _detener_proceso(self) -> None:
        proceso = self._proceso
        self._proceso = None
        if not proceso:
            return
        try:
            if proceso.poll() is None:
                proceso.terminate()
                try:
                    proceso.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proceso.kill()
        except OSError:
            pass

    def _iniciar_hilo(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        self._hilo = threading.Thread(target=self._trabajar, name="pasoapaso-voz", daemon=True)
        self._hilo.start()

    def decir(self, texto: str) -> None:
        if not self._activa or not self.disponible() or not (texto or "").strip():
            return
        self._iniciar_hilo()
        try:
            self._cola.put_nowait(str(texto).strip()[:300])
        except queue.Full:
            pass

    def detener(self) -> None:
        """Vacía lo que falta por decir y corta la frase actual."""
        while True:
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break
        self._detener_proceso()
        self._ultimo = ""

    def cerrar(self) -> None:
        self._cerrada = True
        self._activa = False
        self.detener()
        try:
            self._cola.put_nowait(None)
        except queue.Full:
            pass
