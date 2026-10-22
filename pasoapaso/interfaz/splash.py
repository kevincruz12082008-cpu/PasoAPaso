"""Pantalla de inicio con el logo de PasoAPaso."""

from __future__ import annotations

import tkinter as tk

from .. import configuracion as cfg
from . import tema


class VentanaSplash:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.ventana = tk.Toplevel(raiz)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.configure(bg=tema.FONDO)
        self._animacion = None
        self._posicion = 0
        self._cerrada = False
        self._construir()
        self._centrar()
        self.ventana.attributes("-alpha", 0.0)
        self._fundido(0.0)

    def _construir(self) -> None:
        ancho, alto = 620, 400
        self.ventana.geometry(f"{ancho}x{alto}")
        marco = tk.Frame(self.ventana, bg=tema.FONDO, padx=40, pady=30)
        marco.pack(fill="both", expand=True)

        cabecera = tk.Frame(marco, bg=tema.FONDO)
        cabecera.pack(fill="x")
        tk.Label(
            cabecera,
            text="2.0",
            font=tema.fuente(10, "bold"),
            fg=tema.ACENTO,
            bg=tema.ACENTO_CLARO,
            padx=10,
            pady=3,
        ).pack(side="right")

        try:
            self._logo = tk.PhotoImage(file=str(cfg.RUTA_LOGO_256))
            tk.Label(marco, image=self._logo, bg=tema.FONDO).pack(pady=(14, 8))
        except tk.TclError:
            tk.Label(marco, text="PasoAPaso", font=tema.fuente(30, "bold"), fg=tema.ACENTO, bg=tema.FONDO).pack(
                pady=(30, 14)
            )

        tk.Label(
            marco,
            text=cfg.NOMBRE_APP,
            font=tema.fuente(32, "bold"),
            fg=tema.ACENTO,
            bg=tema.FONDO,
        ).pack()
        tk.Label(
            marco,
            text=cfg.LEMA,
            font=tema.fuente(12),
            fg=tema.SUAVE,
            bg=tema.FONDO,
        ).pack(pady=(3, 20))

        self.estado = tk.Label(
            marco,
            text="Preparando todo para ti…",
            font=tema.fuente(11),
            fg=tema.TEXTO,
            bg=tema.FONDO,
        )
        self.estado.pack()

        self.barra = tk.Canvas(
            marco,
            width=420,
            height=8,
            bg=tema.PROGRESO_FONDO,
            highlightthickness=0,
            bd=0,
        )
        self.barra.pack(pady=(12, 0))
        self._segmento = self.barra.create_rectangle(0, 0, 0, 8, fill=tema.ACENTO, width=0)
        self._animar()

        tk.Label(
            marco,
            text="Hecho para aprender sin miedo a la computadora",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
        ).pack(side="bottom")

    def _centrar(self) -> None:
        self.ventana.update_idletasks()
        ancho = self.ventana.winfo_reqwidth()
        alto = self.ventana.winfo_reqheight()
        x = (self.ventana.winfo_screenwidth() - max(ancho, 620)) // 2
        y = (self.ventana.winfo_screenheight() - max(alto, 400)) // 3
        self.ventana.geometry(f"{max(ancho, 620)}x{max(alto, 400)}+{x}+{y}")

    def _animar(self) -> None:
        if self._cerrada:
            return
        ancho = 420
        segmento = 120
        self._posicion = (self._posicion + 14) % (ancho + segmento)
        inicio = max(0, self._posicion - segmento)
        fin = min(ancho, self._posicion)
        self.barra.coords(self._segmento, inicio, 0, fin, 8)
        self._animacion = self.ventana.after(28, self._animar)

    def _fundido(self, alpha: float) -> None:
        if self._cerrada:
            return
        alpha = min(1.0, alpha + 0.08)
        try:
            self.ventana.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if alpha < 1.0:
            self.ventana.after(24, lambda: self._fundido(alpha))

    def actualizar(self, texto: str) -> None:
        try:
            self.estado.config(text=texto)
            self.ventana.update_idletasks()
            self.ventana.update()
        except tk.TclError:
            pass

    def mostrar(self) -> None:
        try:
            self.ventana.deiconify()
            self.ventana.lift()
            self.ventana.update()
        except tk.TclError:
            pass

    def cerrar(self) -> None:
        self._cerrada = True
        if self._animacion:
            try:
                self.ventana.after_cancel(self._animacion)
            except tk.TclError:
                pass
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass
