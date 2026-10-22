import queue
import threading
import time

import pyautogui

from .. import configuracion as cfg
from ..datos.teclas import etiqueta
from ..utilidades.escritura import escribir_caracter


class Cancelado(Exception):
    pass


class Guia:
    def __init__(self):
        self.eventos = queue.Queue()
        self.cancelar = threading.Event()
        self.velocidad = cfg.VELOCIDAD_INICIAL
        self.instantaneo = False
        self.avisos = []
        self.memoria = {}
        self.paso = 0
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

    def preparar(self, velocidad, instantaneo):
        self.cancelar.clear()
        self.velocidad = velocidad
        self.instantaneo = instantaneo
        self.avisos = []
        self.paso = 0

    def _emitir(self, evento, **datos):
        self.eventos.put((evento, datos))

    def verificar(self):
        if self.cancelar.is_set():
            raise Cancelado()

    def _dormir(self, segundos):
        restante = segundos
        while restante > 0:
            self.verificar()
            espera = min(0.05, restante)
            time.sleep(espera)
            restante -= espera
        self.verificar()

    def pausar(self, segundos):
        if self.instantaneo:
            self.verificar()
            return
        self._dormir(segundos / self.velocidad)

    def esperar(self, segundos):
        if self.instantaneo:
            self._dormir(segundos * cfg.FACTOR_ESPERA_INSTANTANEA)
        else:
            self._dormir(segundos / self.velocidad)

    def plan(self, resumenes):
        if not self.instantaneo:
            self._emitir("plan", resumenes=list(resumenes))

    def iniciar_tarea(self, numero, total, resumen):
        self.paso = 0
        if not self.instantaneo:
            self._emitir("tarea", numero=numero, total=total, resumen=resumen)
        self.pausar(1.8)

    def decir(self, titulo, detalle="", teclas=(), tipo="paso"):
        self.verificar()
        if self.instantaneo:
            if tipo == "aviso":
                self.avisos.append(titulo)
            return
        if tipo == "paso":
            self.paso += 1
        self._emitir(
            "mensaje",
            titulo=titulo,
            detalle=detalle,
            teclas=tuple(etiqueta(t) for t in teclas),
            tipo=tipo,
            paso=self.paso,
        )

    def tecla(self, nombre, titulo, detalle="", espera=1.8, despues=0.8):
        self.decir(titulo, detalle, teclas=(nombre,))
        self.pausar(espera)
        pyautogui.press(nombre)
        self.esperar(despues)

    def teclas(self, *combinacion, titulo, detalle="", espera=2.0, despues=0.8):
        self.decir(titulo, detalle, teclas=combinacion)
        self.pausar(espera)
        pyautogui.hotkey(*combinacion)
        self.esperar(despues)

    def escribir(self, texto, titulo, detalle=""):
        self.decir(titulo, detalle)
        self.pausar(1.2)
        escrito = ""
        for caracter in texto:
            self.verificar()
            if caracter == "\n":
                pyautogui.press("enter")
            else:
                escribir_caracter(caracter)
            escrito += caracter
            if self.instantaneo:
                time.sleep(cfg.PAUSA_ESCRITURA_INSTANTANEA)
            else:
                self._emitir("escritura", texto=escrito)
                self.pausar(cfg.PAUSA_ESCRITURA)
        self.pausar(0.8)

    def mover_y_clic(self, fraccion_x, fraccion_y, titulo, detalle=""):
        self.decir(titulo, detalle)
        self.pausar(1.5)
        ancho, alto = pyautogui.size()
        duracion = 0.15 if self.instantaneo else cfg.DURACION_MOVIMIENTO_MOUSE / self.velocidad
        pyautogui.moveTo(
            ancho * fraccion_x,
            alto * fraccion_y,
            duration=duracion,
            tween=pyautogui.easeInOutQuad,
        )
        self.pausar(0.8)
        pyautogui.click()
        self.pausar(0.8)

    def ocultar_panel(self):
        if self.instantaneo:
            time.sleep(0.3)
            return
        self._emitir("ocultar")
        time.sleep(0.7)

    def mostrar_panel(self):
        if self.instantaneo:
            return
        self._emitir("mostrar")
        time.sleep(0.2)

    def finalizar(self, completado):
        self._emitir(
            "fin",
            completado=completado,
            instantaneo=self.instantaneo,
            avisos=list(self.avisos),
        )
