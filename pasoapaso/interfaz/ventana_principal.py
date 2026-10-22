"""Ventana principal de PasoAPaso 2.0.

La voz es el modo predeterminado. La app pide la interpretación al
servidor (que puede usar Gemini) y ejecuta las órdenes localmente con
pyautogui, manteniendo el panel que explica cada paso.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from tkinter import messagebox

from .. import configuracion as cfg
from ..nucleo.ejecutor import Ejecutor
from ..nucleo.guia import Guia
from ..nucleo.interprete import Orden, interpretar
from ..nucleo.nube import ClienteNube, ErrorNube
from ..nucleo.sesion import Cola, Sesion, cargar_preferencias, guardar_preferencias
from ..utilidades.habla import VozSalida
from ..utilidades.voz import EntradaVoz, ErrorVoz, VozNoDisponible
from . import tema
from .acerca_de import mostrar_acerca_de
from .historial import VentanaHistorial
from .panel_guia import PanelGuia

EJEMPLOS = (
    "abre la calculadora y el bloc de notas",
    "crea una carpeta llamada Tareas en el escritorio",
    "toma una captura de pantalla",
    "busca recetas de pupusas en google",
    "reproduce música de Juan Gabriel en youtube",
)


class AplicacionPrincipal:
    def __init__(self, sesion: Sesion):
        self.sesion = sesion
        self.preferencias = cargar_preferencias()
        self.raiz = tk.Tk()
        tema.iniciar(self.raiz)
        self.raiz.title(cfg.NOMBRE_APP)
        self.raiz.configure(bg=tema.FONDO)
        self.raiz.resizable(False, False)
        try:
            self._icono = tk.PhotoImage(file=str(cfg.RUTA_LOGO_64))
            self.raiz.iconphoto(True, self._icono)
        except tk.TclError:
            self._icono = None

        self.guia = Guia()
        self.panel = PanelGuia(self.raiz, self.guia)
        self.nube = ClienteNube(cfg.URL_SERVIDOR, sesion.token)
        self.cola = Cola()
        self.cola_ui: queue.Queue = queue.Queue()

        self.voz_salida = VozSalida()
        self.hablar = tk.BooleanVar(
            value=bool(self.preferencias.get("hablar", cfg.VOZ_SALIDA_POR_DEFECTO))
        )
        self.voz_salida.activar(self.hablar.get())
        self.entrada_voz = EntradaVoz()

        self.velocidad = tk.DoubleVar(value=cfg.VELOCIDAD_INICIAL)
        self.instantaneo = tk.BooleanVar(value=False)
        self.manos_libres = tk.BooleanVar(value=bool(self.preferencias.get("manos_libres", False)))

        self.ocupado = False
        self.modo = "voz"
        self.reiniciar_sesion = False
        self._escuchando = False
        self._animacion = None
        self._texto_pendiente = ""
        self._ultimo_prompt = None
        self._resultado: dict | None = None
        self._voz_disponible: bool | None = None
        self._motivo_voz = ""
        self._fin_recibido = False
        self._terminado = False
        self._cerrando = False

        self._construir()
        self._colocar()
        self._cambiar_modo("voz")
        self.entrada.focus_set()
        self.raiz.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.raiz.after(50, self._sondear)
        self.raiz.after(250, self._verificar_conexion)
        self.raiz.after(500, self._comprobar_voz)
        self.raiz.after(700, self._sincronizar)

    # --- Construcción ----------------------------------------------------
    def _boton(self, padre, texto, comando, fondo, activo, fg="#FFFFFF", tamano=11, padx=18, pady=8):
        boton = tk.Button(
            padre,
            text=texto,
            command=comando,
            bg=fondo,
            fg=fg,
            activebackground=activo,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=tema.px(padx),
            pady=tema.px(pady),
            font=tema.fuente(tamano, "bold"),
            cursor="hand2",
        )
        boton.bind("<Enter>", lambda _: boton.config(bg=activo))
        boton.bind("<Leave>", lambda _: boton.config(bg=fondo))
        return boton

    def _enlace(self, padre, texto, comando):
        etiqueta = tk.Label(
            padre,
            text=texto,
            font=tema.fuente(9, "underline"),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            cursor="hand2",
        )
        etiqueta.bind("<Button-1>", lambda _: comando())
        etiqueta.bind("<Enter>", lambda _: etiqueta.config(fg=tema.ACENTO))
        etiqueta.bind("<Leave>", lambda _: etiqueta.config(fg=tema.SUAVE))
        return etiqueta

    def _construir(self) -> None:
        marco = tk.Frame(self.raiz, bg=tema.FONDO, padx=tema.px(28), pady=tema.px(16))
        marco.pack(fill="both", expand=True)

        cabecera = tk.Frame(marco, bg=tema.FONDO)
        cabecera.pack(fill="x")
        izquierda = tk.Frame(cabecera, bg=tema.FONDO)
        izquierda.pack(side="left")
        try:
            self._logo = tk.PhotoImage(file=str(cfg.RUTA_LOGO_64))
            tk.Label(izquierda, image=self._logo, bg=tema.FONDO).pack(side="left", padx=(0, 10))
        except tk.TclError:
            pass
        textos = tk.Frame(izquierda, bg=tema.FONDO)
        textos.pack(side="left")
        tk.Label(
            textos,
            text=cfg.NOMBRE_APP,
            font=tema.fuente(19, "bold"),
            fg=tema.ACENTO,
            bg=tema.FONDO,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            textos,
            text=f"Hola, {self.sesion.nombre.split()[0] if self.sesion.nombre else 'amigo'}",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            anchor="w",
        ).pack(anchor="w")

        acciones = tk.Frame(cabecera, bg=tema.FONDO)
        acciones.pack(side="right")
        self.estado_conexion = tk.Label(
            acciones,
            text="● Comprobando",
            font=tema.fuente(9, "bold"),
            fg=tema.SUAVE,
            bg=tema.FONDO,
        )
        self.estado_conexion.pack(side="left", padx=(0, 12))
        self._enlace(acciones, "Mi historial", self._abrir_historial).pack(side="left", padx=6)
        self._enlace(acciones, "Acerca de", self._abrir_acerca).pack(side="left", padx=6)
        self._enlace(acciones, "Salir", self._cerrar_sesion).pack(side="left", padx=(6, 0))

        tk.Label(
            marco,
            text="¿Qué quieres hacer hoy?",
            font=tema.fuente(24, "bold"),
            fg=tema.TEXTO,
            bg=tema.FONDO,
            anchor="w",
        ).pack(fill="x", pady=(14, 2))
        tk.Label(
            marco,
            text="Háblame o escríbeme. Yo lo hago contigo y te explico cada paso.",
            font=tema.fuente(10),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        modos = tk.Frame(marco, bg=tema.FONDO)
        modos.pack(fill="x", pady=(0, 10))
        self.boton_modo_voz = tk.Button(
            modos,
            text="🎤  Hablar",
            command=lambda: self._cambiar_modo("voz"),
            font=tema.fuente(12, "bold"),
            relief="flat",
            bd=0,
            padx=tema.px(24),
            pady=tema.px(9),
            cursor="hand2",
        )
        self.boton_modo_voz.pack(side="left")
        self.boton_modo_texto = tk.Button(
            modos,
            text="⌨  Escribir",
            command=lambda: self._cambiar_modo("texto"),
            font=tema.fuente(12, "bold"),
            relief="flat",
            bd=0,
            padx=tema.px(24),
            pady=tema.px(9),
            cursor="hand2",
        )
        self.boton_modo_texto.pack(side="left", padx=(8, 0))
        self.etiqueta_modo = tk.Label(
            modos,
            text="Modo voz: presiona el micrófono y habla con naturalidad.",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
        )
        self.etiqueta_modo.pack(side="left", padx=(14, 0))

        self.area = tk.Frame(marco, bg=tema.FONDO)
        self.area.pack(fill="both", expand=True)
        self.panel_voz = tk.Frame(self.area, bg=tema.FONDO)
        self.panel_texto = tk.Frame(self.area, bg=tema.FONDO)
        self._construir_voz()
        self._construir_texto()

        controles = tk.Frame(marco, bg=tema.FONDO)
        controles.pack(fill="x", pady=(10, 0))
        fila1 = tk.Frame(controles, bg=tema.FONDO)
        fila1.pack(fill="x")
        tk.Label(
            fila1,
            text="Velocidad de la demostración",
            font=tema.fuente(9, "bold"),
            fg=tema.TEXTO,
            bg=tema.FONDO,
        ).pack(side="left")
        tk.Label(fila1, text="Más lento", font=tema.fuente(8), fg=tema.SUAVE, bg=tema.FONDO).pack(
            side="left", padx=(12, 0)
        )
        self.escala = tk.Scale(
            fila1,
            from_=cfg.VELOCIDAD_MIN,
            to=cfg.VELOCIDAD_MAX,
            resolution=0.1,
            orient="horizontal",
            showvalue=False,
            variable=self.velocidad,
            length=tema.px(150),
            bg=tema.FONDO,
            troughcolor=tema.BORDE,
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            activebackground=tema.ACENTO,
        )
        self.escala.pack(side="left", padx=6)
        tk.Label(fila1, text="Más rápido", font=tema.fuente(8), fg=tema.SUAVE, bg=tema.FONDO).pack(side="left")
        self.boton_instantaneo = tk.Button(
            fila1,
            text="⚡ Instantáneo",
            command=self._alternar_instantaneo,
            font=tema.fuente(9, "bold"),
            relief="flat",
            bd=0,
            padx=tema.px(12),
            pady=tema.px(5),
            cursor="hand2",
        )
        self.boton_instantaneo.pack(side="right")
        self._pintar_instantaneo()

        fila2 = tk.Frame(controles, bg=tema.FONDO)
        fila2.pack(fill="x", pady=(4, 0))
        self.check_hablar = tk.Checkbutton(
            fila2,
            text="🔊 Leer los pasos en voz alta",
            variable=self.hablar,
            command=self._alternar_hablar,
            bg=tema.FONDO,
            fg=tema.TEXTO,
            activebackground=tema.FONDO,
            activeforeground=tema.TEXTO,
            font=tema.fuente(9),
            cursor="hand2",
        )
        self.check_hablar.pack(side="left")
        self.check_manos = tk.Checkbutton(
            fila2,
            text="🔁 Manos libres (volver a escuchar al terminar)",
            variable=self.manos_libres,
            command=self._guardar_preferencias,
            bg=tema.FONDO,
            fg=tema.TEXTO,
            activebackground=tema.FONDO,
            activeforeground=tema.TEXTO,
            font=tema.fuente(9),
            cursor="hand2",
        )
        self.check_manos.pack(side="left", padx=(14, 0))

        self.estado = tk.Label(
            marco,
            text="Puedes pedirme varias cosas juntas, separadas por «y» o por comas.",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            anchor="w",
            justify="left",
            wraplength=tema.px(740),
        )
        self.estado.pack(fill="x", pady=(6, 0))
        tk.Label(
            marco,
            text="Para detener una demostración: botón «Detener» del panel o lleva el mouse a la esquina superior izquierda.",
            font=tema.fuente(8),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            anchor="w",
        ).pack(fill="x")

    def _construir_voz(self) -> None:
        caja = tk.Frame(
            self.panel_voz,
            bg=tema.TARJETA,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
            padx=tema.px(18),
            pady=tema.px(14),
        )
        caja.pack(fill="both", expand=True)

        self.canvas_mic = tk.Canvas(
            caja,
            width=tema.px(148),
            height=tema.px(148),
            bg=tema.TARJETA,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas_mic.pack(pady=(0, 4))
        self._anillo = self.canvas_mic.create_oval(
            tema.px(14), tema.px(14), tema.px(134), tema.px(134), fill=tema.VOZ_CLARO, outline=""
        )
        self._circulo = self.canvas_mic.create_oval(
            tema.px(30), tema.px(30), tema.px(118), tema.px(118), fill=tema.VOZ, outline=""
        )
        self._micro = self.canvas_mic.create_text(
            tema.px(74), tema.px(76), text="🎤", fill="#FFFFFF", font=tema.FUENTE_EMOJI
        )
        self.canvas_mic.bind("<Button-1>", lambda _: self._hablar_click())

        self.estado_voz = tk.Label(
            caja,
            text="Toca el micrófono y dime qué quieres hacer.",
            font=tema.fuente(13, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            wraplength=tema.px(560),
        )
        self.estado_voz.pack()

        self.caja_transcripcion = tk.Frame(caja, bg=tema.TARJETA_SUAVE, highlightthickness=0)
        self.transcripcion = tk.Label(
            self.caja_transcripcion,
            text="",
            font=tema.fuente(12),
            fg=tema.TEXTO,
            bg=tema.TARJETA_SUAVE,
            wraplength=tema.px(530),
            justify="left",
            padx=tema.px(12),
            pady=tema.px(9),
        )
        self.transcripcion.pack(fill="x")

        self.botones_voz = tk.Frame(caja, bg=tema.TARJETA)
        self.boton_confirmar = self._boton(
            self.botones_voz,
            "Sí, hazlo",
            self._confirmar_voz,
            tema.ACENTO,
            tema.ACENTO_OSCURO,
            tamano=10,
            padx=20,
            pady=8,
        )
        self.boton_confirmar.pack(side="left")
        self.boton_repetir = self._boton(
            self.botones_voz,
            "Volver a decir",
            self._repetir_voz,
            tema.TECLA,
            tema.BORDE,
            fg=tema.TEXTO,
            tamano=10,
            padx=20,
            pady=8,
        )
        self.boton_repetir.pack(side="left", padx=(8, 0))

        self.ayuda_voz = tk.Label(
            caja,
            text="Consejo: habla claro y de frente al micrófono. Si no te entiendo, puedes escribirme.",
            font=tema.fuente(8),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
            wraplength=tema.px(560),
            justify="center",
        )
        self.ayuda_voz.pack(pady=(8, 0))

    def _construir_texto(self) -> None:
        caja = tk.Frame(
            self.panel_texto,
            bg=tema.TARJETA,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
            padx=tema.px(20),
            pady=tema.px(16),
        )
        caja.pack(fill="both", expand=True)
        tk.Label(
            caja,
            text="Escribe lo que quieres hacer",
            font=tema.fuente(13, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
        ).pack(fill="x")
        fila = tk.Frame(caja, bg=tema.TARJETA)
        fila.pack(fill="x", pady=(6, 0))
        self.entrada = tk.Entry(
            fila,
            font=tema.fuente(14),
            relief="flat",
            bd=0,
            bg=tema.TARJETA_SUAVE,
            fg=tema.TEXTO,
            insertbackground=tema.TEXTO,
            highlightthickness=2,
            highlightbackground=tema.BORDE,
            highlightcolor=tema.ACENTO,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=tema.px(9))
        self.entrada.bind("<Return>", lambda _: self._enviar())
        self.boton_enviar = self._boton(
            fila, "Hazlo", self._enviar, tema.ACENTO, tema.ACENTO_OSCURO, tamano=11, padx=20, pady=8
        )
        self.boton_enviar.pack(side="left", padx=(8, 0))

        tk.Label(
            caja,
            text="Prueba con estos ejemplos",
            font=tema.fuente(9, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
        ).pack(fill="x", pady=(14, 3))
        for ejemplo in EJEMPLOS:
            enlace = tk.Label(
                caja,
                text="›  " + ejemplo,
                font=tema.fuente(10),
                fg=tema.ACENTO,
                bg=tema.TARJETA,
                cursor="hand2",
                anchor="w",
            )
            enlace.pack(fill="x", pady=1)
            enlace.bind("<Button-1>", lambda _, t=ejemplo: self._usar_ejemplo(t))
            enlace.bind(
                "<Enter>",
                lambda _, w=enlace: w.config(fg=tema.ACENTO_OSCURO, font=tema.fuente(10, "underline")),
            )
            enlace.bind(
                "<Leave>", lambda _, w=enlace: w.config(fg=tema.ACENTO, font=tema.fuente(10))
            )

    def _colocar(self) -> None:
        self.raiz.update_idletasks()
        ancho = max(tema.px(800), self.raiz.winfo_reqwidth())
        alto = max(tema.px(700), self.raiz.winfo_reqheight())
        x = (self.raiz.winfo_screenwidth() - ancho) // 2
        y = max(0, (self.raiz.winfo_screenheight() - alto) // 2 - 20)
        self.raiz.geometry(f"{ancho}x{alto}+{x}+{y}")

    # --- Modos y controles ----------------------------------------------
    def _cambiar_modo(self, modo: str) -> None:
        self.modo = modo
        activo = {"bg": tema.ACENTO, "fg": "#FFFFFF", "activebackground": tema.ACENTO_OSCURO}
        inactivo = {"bg": tema.FONDO, "fg": tema.TEXTO, "activebackground": tema.ACENTO_CLARO}
        self.boton_modo_voz.config(**(activo if modo == "voz" else inactivo))
        self.boton_modo_texto.config(**(activo if modo == "texto" else inactivo))
        self.panel_voz.pack_forget()
        self.panel_texto.pack_forget()
        if modo == "voz":
            self.panel_voz.pack(fill="both", expand=True)
            self.etiqueta_modo.config(text="Modo voz: presiona el micrófono y habla con naturalidad.")
        else:
            self.panel_texto.pack(fill="both", expand=True)
            self.etiqueta_modo.config(text="Modo texto: escribe tu orden y presiona «Hazlo».")
            self.raiz.after(50, self.entrada.focus_set)

    def _pintar_instantaneo(self) -> None:
        if self.instantaneo.get():
            self.boton_instantaneo.config(
                bg=tema.ACENTO,
                fg="#FFFFFF",
                activebackground=tema.ACENTO_OSCURO,
                activeforeground="#FFFFFF",
            )
            self.escala.config(state="disabled")
        else:
            self.boton_instantaneo.config(
                bg=tema.ACENTO_CLARO,
                fg=tema.ACENTO_OSCURO,
                activebackground=tema.BORDE,
                activeforeground=tema.ACENTO_OSCURO,
            )
            self.escala.config(state="normal")

    def _alternar_instantaneo(self) -> None:
        self.instantaneo.set(not self.instantaneo.get())
        self._pintar_instantaneo()
        if self.instantaneo.get():
            self._mensaje_estado("Modo instantáneo: haré todo de inmediato, sin explicar los pasos.", tema.ACENTO)
        else:
            self._mensaje_estado("Modo paso a paso: te explicaré cada cosa.", tema.SUAVE)

    def _alternar_hablar(self) -> None:
        self.voz_salida.activar(self.hablar.get())
        self._guardar_preferencias()

    def _guardar_preferencias(self) -> None:
        guardar_preferencias(
            {
                "hablar": bool(self.hablar.get()),
                "manos_libres": bool(self.manos_libres.get()),
                "telefono": self.sesion.telefono,
            }
        )

    def _mensaje_estado(self, texto: str, color=tema.SUAVE) -> None:
        self.estado.config(text=texto, fg=color)

    # --- Voz -------------------------------------------------------------
    def _comprobar_voz(self) -> None:
        def revisar():
            try:
                disponible = self.entrada_voz.disponible()
                self.cola_ui.put(("voz_disponible", disponible, self.entrada_voz.motivo()))
            except Exception as error:
                self.cola_ui.put(("voz_disponible", False, str(error)))

        threading.Thread(target=revisar, daemon=True).start()

    def _marcar_voz_no_disponible(self, motivo: str) -> None:
        self._voz_disponible = False
        self._motivo_voz = motivo
        try:
            self.canvas_mic.itemconfig(self._anillo, fill=tema.TECLA)
            self.canvas_mic.itemconfig(self._circulo, fill=tema.SUAVE)
            self.canvas_mic.itemconfig(self._micro, text="⌨")
        except tk.TclError:
            pass
        self.estado_voz.config(text="La voz no está disponible en este equipo.")
        self.ayuda_voz.config(
            text="Puedes usar la pestaña «Escribir» mientras instalas los componentes de voz. "
            "Abre una terminal en la carpeta de PasoAPaso y escribe: "
            "python -m pip install SpeechRecognition sounddevice"
        )

    def _hablar_click(self) -> None:
        if self.ocupado or self._escuchando:
            return
        if self._voz_disponible is False:
            messagebox.showinfo(
                "Voz no disponible",
                self._motivo_voz
                or "Para hablar necesitas instalar SpeechRecognition y sounddevice. Mientras tanto, usa la pestaña «Escribir».",
                parent=self.raiz,
            )
            self._cambiar_modo("texto")
            return
        self._escuchando = True
        self._limpiar_transcripcion()
        self.estado_voz.config(text="Escuchando… habla ahora.", fg=tema.VOZ_OSCURO)
        self._animar_mic(True)
        threading.Thread(target=self._escuchar_hilo, daemon=True).start()

    def _escuchar_hilo(self) -> None:
        try:
            texto = self.entrada_voz.escuchar()
        except VozNoDisponible as error:
            self.cola_ui.put(("voz_error", str(error), "nodisponible"))
        except ErrorVoz as error:
            self.cola_ui.put(("voz_error", str(error), "error"))
        except Exception as error:
            self.cola_ui.put(("voz_error", f"No pude escucharte: {error}", "error"))
        else:
            self.cola_ui.put(("voz_ok", texto))

    def _animar_mic(self, activo: bool) -> None:
        if self._animacion:
            try:
                self.raiz.after_cancel(self._animacion)
            except tk.TclError:
                pass
            self._animacion = None
        if not activo:
            try:
                self.canvas_mic.itemconfig(self._anillo, fill=tema.VOZ_CLARO)
                self.canvas_mic.itemconfig(self._circulo, fill=tema.VOZ)
                self.canvas_mic.itemconfig(self._micro, text="🎤")
            except tk.TclError:
                pass
            return
        colores = (tema.VOZ, tema.VOZ_OSCURO)
        self._paso_animacion = getattr(self, "_paso_animacion", 0) + 1

        def paso():
            if not self._escuchando:
                return
            color = colores[self._paso_animacion % 2]
            try:
                self.canvas_mic.itemconfig(self._anillo, fill=color)
                self.canvas_mic.itemconfig(self._circulo, fill=tema.VOZ_CLARO)
                self.canvas_mic.itemconfig(self._micro, text="🎤")
            except tk.TclError:
                return
            self._paso_animacion += 1
            self._animacion = self.raiz.after(320, paso)

        paso()

    def _limpiar_transcripcion(self) -> None:
        self._texto_pendiente = ""
        self.caja_transcripcion.pack_forget()
        self.botones_voz.pack_forget()

    def _al_reconocer(self, texto: str) -> None:
        self._escuchando = False
        self._animar_mic(False)
        self._texto_pendiente = texto
        self.transcripcion.config(text=f"«{texto}»")
        self.caja_transcripcion.pack(fill="x", pady=(8, 6))
        self.botones_voz.pack(pady=(2, 0))
        self.estado_voz.config(text="¿Es esto lo que quieres hacer?", fg=tema.TEXTO)
        self.ayuda_voz.config(text="Puedes confirmar con el botón o volver a intentarlo.")
        self._mensaje_estado("Revisa lo que entendí y confirma.", tema.ACENTO)

    def _confirmar_voz(self) -> None:
        if self._texto_pendiente:
            self._enviar(self._texto_pendiente, "voz")

    def _repetir_voz(self) -> None:
        if self.ocupado:
            return
        self._limpiar_transcripcion()
        self.estado_voz.config(text="Toca el micrófono y vuelve a hablar.", fg=tema.TEXTO)
        self._hablar_click()

    def _usar_ejemplo(self, texto: str) -> None:
        if self.ocupado:
            return
        self._cambiar_modo("texto")
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self.entrada.focus_set()

    # --- Envío e interpretación -----------------------------------------
    def _enviar(self, texto: str | None = None, origen: str = "texto") -> None:
        if self.ocupado:
            return
        if texto is None:
            texto = self.entrada.get().strip()
        texto = (texto or "").strip()
        if not texto:
            self._mensaje_estado("Escribe o di primero lo que quieres hacer.", tema.AVISO)
            if self.modo == "texto":
                self.entrada.focus_set()
            return
        self.ocupado = True
        self._fin_recibido = False
        self._terminado = False
        self._bloquear(True)
        self._limpiar_transcripcion()
        self.estado_voz.config(text="Pensando la mejor forma de ayudarte…", fg=tema.TEXTO)
        self._mensaje_estado("Pensando…", tema.SUAVE)
        self._cambiar_modo_visual(origen)
        threading.Thread(target=self._procesar, args=(texto, origen), daemon=True).start()

    def _cambiar_modo_visual(self, origen: str) -> None:
        if origen == "voz" and self.modo != "voz":
            self._cambiar_modo("voz")

    def _procesar(self, texto: str, origen: str) -> None:
        datos = None
        local = False
        if self.sesion.es_local or not self.sesion.token:
            local = True
        else:
            try:
                datos = self.nube.interpretar(texto, origen)
            except ErrorNube as error:
                if error.codigo in (401, 403):
                    self.cola_ui.put(("sesion", error.mensaje))
                    return
                if error.codigo == 400:
                    self.cola_ui.put(("error", error.mensaje))
                    return
                local = True
            except Exception:
                local = True
        if local:
            ordenes = interpretar(texto)
            datos = {
                "prompt_id": None,
                "ia_usada": False,
                "estado": "pendiente",
                "mensaje": "",
                "sugerencias": [],
                "motivo": "local_offline",
            }
        else:
            ordenes = []
            for elemento in (datos or {}).get("ordenes") or []:
                if not isinstance(elemento, dict):
                    continue
                ordenes.append(
                    Orden(
                        tipo=str(elemento.get("tipo", "")),
                        datos=elemento.get("datos") or {},
                        resumen=str(elemento.get("resumen", "")),
                        texto=str(elemento.get("texto", "")),
                    )
                )
        self.cola_ui.put(("listo", datos or {}, ordenes, texto, origen, local))

    def _al_interpretar(self, datos: dict, ordenes, texto: str, origen: str, local: bool) -> None:
        validas = [orden for orden in ordenes if orden.tipo != "desconocido"]
        if not validas:
            self.ocupado = False
            self._bloquear(False)
            mensaje = datos.get("mensaje") or (
                "No entendí esa orden. Prueba con algo como «abre la calculadora» "
                "o «crea una carpeta llamada Tareas»."
            )
            self._mensaje_estado(mensaje, tema.AVISO)
            self.estado_voz.config(text="No entendí. Inténtalo con otras palabras.", fg=tema.AVISO)
            self.ayuda_voz.config(
                text="Ejemplos: «abre la calculadora», «toma una captura», «busca recetas en Google»."
            )
            self.raiz.deiconify()
            self.raiz.lift()
            return
        self._ultimo_prompt = datos.get("prompt_id")
        self._mensaje_estado(
            "Usé la inteligencia artificial para entenderte." if datos.get("ia_usada") else "Entendí tu orden.",
            tema.ACENTO if datos.get("ia_usada") else tema.SUAVE,
        )
        self.guia.preparar(self.velocidad.get(), self.instantaneo.get())
        self.raiz.withdraw()
        threading.Thread(
            target=self._ejecutar,
            args=(ordenes, self._ultimo_prompt, texto, origen, local, bool(datos.get("ia_usada"))),
            daemon=True,
        ).start()

    def _ejecutar(self, ordenes, prompt_id, texto, origen, local, ia_usada) -> None:
        try:
            resultado = Ejecutor(self.guia).correr(ordenes)
        except Exception as error:
            resultado = {
                "completado": False,
                "errores": [str(error)],
                "acciones": [],
                "duracion_ms": 0,
            }
        self.cola_ui.put(
            ("fin_ejecucion", resultado, prompt_id, texto, origen, ordenes, local, ia_usada)
        )

    def _al_fin_ejecucion(
        self, resultado, prompt_id, texto, origen, ordenes, local, ia_usada
    ) -> None:
        self._resultado = resultado
        completado = bool(resultado.get("completado"))
        if not self._fin_recibido:
            self.raiz.after(
                250,
                lambda: self._terminar(
                    {
                        "completado": completado,
                        "instantaneo": bool(self.instantaneo.get()),
                        "avisos": [],
                    }
                ),
            )
        errores = resultado.get("errores") or []
        estado = "completado" if completado else "detenido"
        if completado and errores:
            estado = "error"
        error = "; ".join(errores)[:500]
        duracion = int(resultado.get("duracion_ms") or 0)
        acciones = resultado.get("acciones") or []
        if prompt_id:
            threading.Thread(
                target=self._reportar,
                args=(prompt_id, estado, error, duracion, acciones),
                daemon=True,
            ).start()
        else:
            self.cola.agregar(
                "offline",
                {
                    "texto": texto,
                    "origen": origen,
                    "estado": estado,
                    "ordenes": [
                        {
                            "tipo": orden.tipo,
                            "datos": orden.datos,
                            "resumen": orden.resumen,
                            "texto": orden.texto,
                        }
                        for orden in ordenes
                    ],
                    "creado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "duracion_ms": duracion,
                    "error": error,
                },
            )
            self._sincronizar()

    def _reportar(self, prompt_id, estado, error, duracion, acciones) -> None:
        try:
            self.nube.reportar(prompt_id, estado, error, duracion, acciones)
        except ErrorNube as fallo:
            if fallo.codigo in (401, 403):
                self.cola.agregar(
                    "resultado",
                    {
                        "prompt_id": prompt_id,
                        "estado": estado,
                        "error": error,
                        "duracion_ms": duracion,
                        "acciones": acciones,
                    },
                )
                self.cola_ui.put(("sesion", fallo.mensaje))
                return
            self.cola.agregar(
                "resultado",
                {
                    "prompt_id": prompt_id,
                    "estado": estado,
                    "error": error,
                    "duracion_ms": duracion,
                    "acciones": acciones,
                },
            )
            self._sincronizar()
        except Exception:
            pass

    def _terminar(self, datos: dict) -> None:
        if self._terminado:
            return
        self._terminado = True
        self.panel.ocultar()
        self.ocupado = False
        self._bloquear(False)
        try:
            self.raiz.deiconify()
            self.raiz.lift()
            self.entrada.focus_force()
        except tk.TclError:
            return
        resultado = self._resultado or {}
        errores = resultado.get("errores") or []
        if datos.get("avisos"):
            self._mensaje_estado("Terminé, pero hubo un detalle: " + "; ".join(datos["avisos"][:2]), tema.AVISO)
        elif errores:
            self._mensaje_estado("Terminé, pero un paso tuvo un problema: " + errores[0][:120], tema.AVISO)
        elif datos.get("completado"):
            self._mensaje_estado(
                "¡Hecho! ¿Qué sigue?" if datos.get("instantaneo") else "¡Listo! ¿Qué más quieres aprender a hacer?",
                tema.OK,
            )
        else:
            self._mensaje_estado("Me detuve. Puedes pedirme otra cosa cuando quieras.", tema.AVISO)
        self._resultado = None
        if self.manos_libres.get() and self.modo == "voz" and not self._cerrando:
            self.raiz.after(900, self._hablar_click)

    # --- Conexión y sincronización --------------------------------------
    def _verificar_conexion(self) -> None:
        def revisar():
            try:
                self.nube.estado()
                self.cola_ui.put(("conexion", True))
            except Exception:
                self.cola_ui.put(("conexion", False))

        threading.Thread(target=revisar, daemon=True).start()

    def _sincronizar(self) -> None:
        if self.sesion.es_local or not self.sesion.token:
            return

        def enviar():
            try:
                if not self.nube.disponible():
                    return
                enviados, quedan = self.cola.sincronizar(self.nube)
                if enviados or quedan:
                    self.cola_ui.put(("sincronizado", enviados, quedan))
            except Exception:
                pass

        threading.Thread(target=enviar, daemon=True).start()

    # --- Eventos ---------------------------------------------------------
    def _sondear(self) -> None:
        if self._cerrando:
            return
        try:
            while True:
                tipo, datos = self.guia.eventos.get_nowait()
                if not (tipo == "fin" and datos.get("instantaneo")):
                    self.panel.procesar(tipo, datos)
                if tipo == "mensaje" and self.hablar.get():
                    self.voz_salida.decir(datos.get("titulo", ""))
                if tipo == "fin":
                    self._fin_recibido = True
                    demora = 0 if datos.get("instantaneo") else 3500
                    self.raiz.after(demora, lambda d=datos: self._terminar(d))
        except queue.Empty:
            pass

        try:
            while True:
                evento = self.cola_ui.get_nowait()
                self._procesar_evento(evento)
        except queue.Empty:
            pass
        try:
            self.raiz.after(50, self._sondear)
        except tk.TclError:
            pass

    def _procesar_evento(self, evento) -> None:
        tipo = evento[0]
        if tipo == "conexion":
            if evento[1]:
                self.estado_conexion.config(text="● En línea", fg=tema.OK)
            else:
                self.estado_conexion.config(text="● Sin conexión", fg=tema.AVISO)
                self._mensaje_estado(
                    "Sin conexión al servidor: usaré las reglas locales y guardaré lo que pase para después.",
                    tema.AVISO,
                )
        elif tipo == "sincronizado":
            enviados, quedan = evento[1], evento[2]
            if enviados:
                self._mensaje_estado(f"Guardé {enviados} consulta(s) que estaban pendientes.", tema.OK)
            elif quedan:
                self._mensaje_estado(f"Tienes {queden} consulta(s) esperando conexión.", tema.AVISO)
        elif tipo == "voz_disponible":
            self._voz_disponible = bool(evento[1])
            if not self._voz_disponible:
                self._marcar_voz_no_disponible(str(evento[2] or ""))
        elif tipo == "voz_ok":
            self._al_reconocer(str(evento[1]))
        elif tipo == "voz_error":
            self._escuchando = False
            self._animar_mic(False)
            self.estado_voz.config(text=str(evento[1]), fg=tema.AVISO)
            self._mensaje_estado(str(evento[1]), tema.AVISO)
            if evento[2] == "nodisponible":
                self._voz_disponible = False
                self._motivo_voz = str(evento[1])
        elif tipo == "listo":
            self._al_interpretar(evento[1], evento[2], evento[3], evento[4], evento[5])
        elif tipo == "fin_ejecucion":
            self._al_fin_ejecucion(evento[1], evento[2], evento[3], evento[4], evento[5], evento[6], evento[7])
        elif tipo == "sesion":
            self.ocupado = False
            self._bloquear(False)
            messagebox.showwarning(
                "Tu sesión venció",
                str(evento[1]) + "\n\nVuelve a iniciar sesión para continuar.",
                parent=self.raiz,
            )
            self.reiniciar_sesion = True
            self._cerrar(forzar=True)
        elif tipo == "error":
            self.ocupado = False
            self._bloquear(False)
            self._mensaje_estado(str(evento[1]), tema.AVISO)
            self.raiz.deiconify()
            self.raiz.lift()

    # --- Bloqueo de controles -------------------------------------------
    def _bloquear(self, activo: bool) -> None:
        estado = "disabled" if activo else "normal"
        for control in (self.boton_enviar, self.boton_confirmar, self.boton_repetir, self.boton_instantaneo):
            try:
                control.config(state=estado)
            except tk.TclError:
                pass
        try:
            self.entrada.config(state=estado)
        except tk.TclError:
            pass
        try:
            self.escala.config(state="disabled" if activo or self.instantaneo.get() else "normal")
        except tk.TclError:
            pass

    # --- Ventanas --------------------------------------------------------
    def _abrir_historial(self) -> None:
        VentanaHistorial(self.raiz, self.nube, self.sesion, self.cola)

    def _abrir_acerca(self) -> None:
        mostrar_acerca_de(self.raiz, self.sesion)

    def _abrir_admin(self) -> None:
        try:
            webbrowser.open(self.nube.url_admin())
        except Exception:
            messagebox.showerror("Panel", "No pude abrir el navegador.", parent=self.raiz)

    def _cerrar_sesion(self) -> None:
        if self.ocupado:
            messagebox.showinfo(
                "Espera un momento",
                "Termina o detén la demostración antes de cerrar sesión.",
                parent=self.raiz,
            )
            return
        if not messagebox.askyesno(
            "Cerrar sesión",
            "¿Quieres cerrar sesión? La próxima vez tendrás que entrar con tu teléfono y tu clave.",
            parent=self.raiz,
        ):
            return
        Sesion.borrar()
        self.reiniciar_sesion = True
        self._cerrar(forzar=True)

    def _cerrar(self, forzar: bool = False) -> None:
        if self._cerrando:
            return
        if self.ocupado and not forzar:
            if not messagebox.askyesno(
                "Salir de PasoAPaso",
                "Hay una demostración en curso. ¿Quieres detenerla y salir?",
                parent=self.raiz,
            ):
                return
        self._cerrando = True
        try:
            self._guardar_preferencias()
        except Exception:
            pass
        try:
            self.guia.cancelar.set()
            self.voz_salida.cerrar()
        except Exception:
            pass
        try:
            self.raiz.destroy()
        except tk.TclError:
            pass

    def ejecutar(self) -> None:
        self.raiz.mainloop()
