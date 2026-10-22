"""Entrada de voz para la app de escritorio.

Usa SpeechRecognition (reconocimiento en línea de Google) y, si está
instalado, sounddevice para grabar sin PyAudio. Si faltan los componentes,
la app sigue funcionando con el teclado.
"""

from __future__ import annotations

import array
import math
import time
from typing import Optional

from .. import configuracion as cfg


class ErrorVoz(Exception):
    pass


class VozNoDisponible(ErrorVoz):
    pass


class NoEntendido(ErrorVoz):
    pass


def _rms(datos: bytes) -> float:
    if not datos:
        return 0.0
    muestras = array.array("h")
    try:
        muestras.frombytes(datos)
    except ValueError:
        return 0.0
    if not muestras:
        return 0.0
    return sum(abs(muestra) for muestra in muestras) / len(muestras)


class EntradaVoz:
    def __init__(self):
        self._sr = None
        self._sd = None
        self._motivo = ""
        self._revisado = False

    # --- Disponibilidad --------------------------------------------------
    def _cargar(self):
        if self._revisado:
            if self._sr is None:
                raise VozNoDisponible(self._motivo)
            return self._sr
        self._revisado = True
        try:
            import speech_recognition as sr  # type: ignore
        except ImportError:
            self._motivo = (
                "Para hablar necesitas instalar dos componentes. Abre una terminal "
                "en la carpeta de PasoAPaso y escribe:\n\n"
                "python -m pip install SpeechRecognition sounddevice\n\n"
                "Mientras tanto, puedes usar la pestaña «Escribir»."
            )
            raise VozNoDisponible(self._motivo)
        self._sr = sr
        try:
            import sounddevice  # type: ignore

            self._sd = sounddevice
        except ImportError:
            self._sd = None
        return sr

    def disponible(self) -> bool:
        try:
            self._cargar()
            return True
        except VozNoDisponible:
            return False

    def motivo(self) -> str:
        if not self._revisado:
            try:
                self._cargar()
            except VozNoDisponible:
                pass
        if self._sr is not None:
            return ""
        return self._motivo

    def descripcion(self) -> str:
        self._cargar()
        if self._sd is not None:
            return "Micrófono listo (sounddevice)"
        try:
            import pyaudio  # noqa: F401

            return "Micrófono listo (PyAudio)"
        except ImportError:
            return "Falta el grabador de audio"

    # --- Grabación -------------------------------------------------------
    def _grabar_sounddevice(self, sd) -> bytes:
        frecuencia = 16000
        bloque = 1600  # 0,1 segundos
        ambiente = []
        muestras = bytearray()
        hablando = False
        silencio = 0.0
        inicio_voz = 0.0
        inicio = time.monotonic()

        with sd.RawInputStream(
            samplerate=frecuencia,
            blocksize=bloque,
            channels=1,
            dtype="int16",
        ) as flujo:
            # Calibrar el ruido de la habitación.
            for _ in range(6):
                datos, _ = flujo.read(bloque)
                ambiente.append(_rms(bytes(datos)))
            ruido = sorted(ambiente)[len(ambiente) // 2] if ambiente else 0
            umbral = max(180.0, ruido * 2.4)

            while time.monotonic() - inicio < cfg.ESPERA_MAXIMA_VOZ:
                datos, _ = flujo.read(bloque)
                crudo = bytes(datos)
                nivel = _rms(crudo)
                if not hablando:
                    if nivel > umbral:
                        hablando = True
                        inicio_voz = time.monotonic()
                        muestras.extend(crudo)
                    elif time.monotonic() - inicio > 5.5:
                        break
                    continue
                muestras.extend(crudo)
                if nivel < umbral * 0.75:
                    silencio += bloque / frecuencia
                    if silencio >= 1.1 and time.monotonic() - inicio_voz > 0.45:
                        break
                else:
                    silencio = 0.0

        if len(muestras) < 8000:  # menos de medio segundo de voz
            raise NoEntendido("No escuché nada. Acércate al micrófono y vuelve a intentarlo.")
        return bytes(muestras)

    def _grabar_microfono(self, sr) -> "sr.AudioData":
        reconocedor = sr.Recognizer()
        reconocedor.dynamic_energy_threshold = True
        try:
            with sr.Microphone() as fuente:
                reconocedor.adjust_for_ambient_noise(fuente, duration=0.5)
                return reconocedor.listen(fuente, timeout=7, phrase_time_limit=10)
        except OSError as error:
            raise VozNoDisponible(
                "No pude abrir el micrófono. Revisa que esté conectado y que Windows "
                "permita usarlo."
            ) from error

    # --- Reconocimiento --------------------------------------------------
    def escuchar(self) -> str:
        sr = self._cargar()
        reconocedor = sr.Recognizer()
        audio: Optional[object] = None
        if self._sd is not None:
            try:
                crudo = self._grabar_sounddevice(self._sd)
                audio = sr.AudioData(crudo, 16000, 2)
            except NoEntendido:
                raise
            except Exception as error:
                # Si sounddevice falla, probamos con el micrófono clásico.
                if "Microphone" in str(error):
                    raise
                audio = None
        if audio is None:
            audio = self._grabar_microfono(sr)

        try:
            texto = reconocedor.recognize_google(audio, language=cfg.IDIOMA_VOZ)
        except sr.UnknownValueError as error:
            raise NoEntendido(
                "No entendí lo que dijiste. Habla un poco más despacio y vuelve a intentarlo."
            ) from error
        except sr.RequestError as error:
            raise ErrorVoz(
                "No pude conectarme para reconocer tu voz. Revisa tu internet o escribe la orden."
            ) from error
        except Exception as error:
            raise ErrorVoz(f"No pude reconocer tu voz: {error}") from error

        texto = (texto or "").strip()
        if not texto:
            raise NoEntendido("No escuché ninguna palabra. Inténtalo otra vez.")
        return texto
