import tkinter as tk

from .. import configuracion as cfg
from ..utilidades.plataforma import evitar_foco
from . import tema

COLORES_TIPO = {
    "paso": tema.TEXTO,
    "info": tema.TEXTO,
    "ok": tema.OK,
    "aviso": tema.AVISO,
}


class PanelGuia:
    def __init__(self, raiz, guia):
        self.guia = guia
        self.vista = None
        self.total = 1
        self.arrastre = (0, 0)
        self.ancho = tema.px(580)
        self.alto = tema.px(330)
        self.ventana = tk.Toplevel(raiz)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self._construir()
        self.ventana.geometry(f"{self.ancho}x{self.alto}+-6000+-6000")
        self.ventana.update()
        evitar_foco(self.ventana)
        self.ventana.withdraw()
        self.ventana.geometry(self._posicion_inicial())

    def _posicion_inicial(self):
        x = self.ventana.winfo_screenwidth() - self.ancho - tema.px(24)
        y = self.ventana.winfo_screenheight() - self.alto - tema.px(80)
        return f"{self.ancho}x{self.alto}+{x}+{y}"

    def _construir(self):
        borde = tk.Frame(self.ventana, bg=tema.ACENTO)
        borde.pack(fill="both", expand=True)
        interior = tk.Frame(borde, bg=tema.TARJETA)
        interior.pack(fill="both", expand=True, padx=2, pady=2)

        cabecera = tk.Frame(interior, bg=tema.ACENTO)
        cabecera.pack(fill="x")
        marca = tk.Label(
            cabecera, text=cfg.NOMBRE_APP, bg=tema.ACENTO, fg="#FFFFFF", font=tema.fuente(10, "bold")
        )
        marca.pack(side="left", padx=(14, 10), pady=8)
        self.etiqueta_tarea = tk.Label(
            cabecera, text="", bg=tema.ACENTO, fg=tema.ACENTO_CLARO, font=tema.fuente(10)
        )
        self.etiqueta_tarea.pack(side="left")
        detener = tk.Button(
            cabecera,
            text="Detener",
            command=self.guia.cancelar.set,
            bg="#FFFFFF",
            fg=tema.PELIGRO,
            activebackground=tema.PELIGRO_CLARO,
            activeforeground=tema.PELIGRO,
            relief="flat",
            bd=0,
            padx=12,
            pady=2,
            font=tema.fuente(10, "bold"),
            cursor="hand2",
        )
        detener.pack(side="right", padx=10, pady=6)
        for pieza in (cabecera, marca, self.etiqueta_tarea):
            pieza.bind("<ButtonPress-1>", self._iniciar_arrastre)
            pieza.bind("<B1-Motion>", self._arrastrar)

        self.progreso = tk.Canvas(
            interior, height=tema.px(6), bg=tema.PROGRESO_FONDO, highlightthickness=0
        )
        self.progreso.pack(fill="x")
        self.barra = self.progreso.create_rectangle(0, 0, 0, tema.px(6), fill=tema.ACENTO, width=0)

        cuerpo = tk.Frame(interior, bg=tema.TARJETA)
        cuerpo.pack(fill="both", expand=True, padx=tema.px(20), pady=(tema.px(12), tema.px(10)))
        self.zona = tk.Frame(cuerpo, bg=tema.TARJETA, height=tema.px(48))
        self.zona.pack(side="bottom", fill="x")
        self.zona.pack_propagate(False)
        self.sobretitulo = tk.Label(
            cuerpo, text="", font=tema.fuente(9, "bold"), fg=tema.ACENTO, bg=tema.TARJETA, anchor="w"
        )
        self.sobretitulo.pack(fill="x")
        self.titulo = tk.Label(
            cuerpo,
            text="",
            font=tema.fuente(17, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="nw",
            justify="left",
            wraplength=tema.px(530),
            height=2,
        )
        self.titulo.pack(fill="x")
        self.detalle = tk.Label(
            cuerpo,
            text="",
            font=tema.fuente(11),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
            anchor="nw",
            justify="left",
            wraplength=tema.px(530),
            height=4,
        )
        self.detalle.pack(fill="x")

    def _iniciar_arrastre(self, evento):
        self.arrastre = (evento.x_root - self.ventana.winfo_x(), evento.y_root - self.ventana.winfo_y())

    def _arrastrar(self, evento):
        self.ventana.geometry(f"+{evento.x_root - self.arrastre[0]}+{evento.y_root - self.arrastre[1]}")

    def _mostrar(self):
        self.ventana.deiconify()
        self.ventana.attributes("-topmost", True)
        self.ventana.lift()

    def ocultar(self):
        self.ventana.withdraw()

    def _barra(self, fraccion):
        ancho = self.progreso.winfo_width()
        self.progreso.coords(self.barra, 0, 0, ancho * fraccion, tema.px(6))

    def _limpiar_zona(self):
        self.vista = None
        for hijo in self.zona.winfo_children():
            hijo.destroy()

    def _poner(self, sobretitulo, titulo, detalle, color, teclas=()):
        self.sobretitulo.config(text=sobretitulo)
        self.titulo.config(text=titulo, fg=color)
        self.detalle.config(text=detalle)
        self._limpiar_zona()
        for posicion, nombre in enumerate(teclas):
            if posicion:
                tk.Label(
                    self.zona, text="+", font=tema.fuente(13, "bold"), fg=tema.SUAVE, bg=tema.TARJETA
                ).pack(side="left", padx=6)
            tk.Label(
                self.zona,
                text=nombre,
                font=tema.fuente(12, "bold"),
                bg=tema.TECLA,
                fg=tema.TEXTO,
                padx=12,
                pady=5,
                highlightthickness=1,
                highlightbackground=tema.BORDE_TECLA,
            ).pack(side="left")

    def procesar(self, tipo, datos):
        if tipo == "plan":
            self._plan(datos["resumenes"])
        elif tipo == "tarea":
            self._tarea(datos)
        elif tipo == "mensaje":
            self._mensaje(datos)
        elif tipo == "escritura":
            self._escritura(datos["texto"])
        elif tipo == "ocultar":
            self.ocultar()
        elif tipo == "mostrar":
            self._mostrar()
        elif tipo == "fin":
            self._final(datos["completado"])

    def _plan(self, resumenes):
        self.total = max(1, len(resumenes))
        lineas = [f"{i}. {texto}" for i, texto in enumerate(resumenes[:4], 1)]
        if len(resumenes) > 4:
            lineas.append(f"…y {len(resumenes) - 4} más")
        self.etiqueta_tarea.config(text="Listo para empezar")
        self._poner("EL PLAN", "Esto es lo que voy a hacer", "\n".join(lineas), tema.TEXTO)
        self._mostrar()
        self._barra(0)

    def _tarea(self, datos):
        self.etiqueta_tarea.config(text=f"Tarea {datos['numero']} de {datos['total']}")
        self._barra((datos["numero"] - 1) / datos["total"])
        self._poner(f"TAREA {datos['numero']} DE {datos['total']}", datos["resumen"], "", tema.ACENTO)

    def _mensaje(self, datos):
        tipo = datos["tipo"]
        sobre = {
            "paso": f"PASO {datos['paso']}",
            "ok": "LISTO",
            "aviso": "ATENCIÓN",
            "info": "",
        }[tipo]
        self._poner(sobre, datos["titulo"], datos["detalle"], COLORES_TIPO[tipo], datos["teclas"])

    def _escritura(self, texto):
        if self.vista is None:
            self._limpiar_zona()
            caja = tk.Frame(
                self.zona, bg=tema.TECLA, highlightthickness=1, highlightbackground=tema.BORDE_TECLA
            )
            caja.pack(fill="x", pady=(2, 0))
            self.vista = tk.Label(
                caja, text="", font=tema.FUENTE_MONO, bg=tema.TECLA, fg=tema.TEXTO, anchor="w", padx=10, pady=6
            )
            self.vista.pack(fill="x")
        visible = texto if len(texto) <= 44 else "…" + texto[-43:]
        self.vista.config(text=visible + "▏")

    def _final(self, completado):
        if completado:
            self._barra(1)
            self.etiqueta_tarea.config(text="Terminado")
            self._poner(
                "FIN",
                "¡Terminamos!",
                "Hice todo lo que me pediste. Ahora inténtalo tú: repite los pasos con tus propias manos.",
                tema.OK,
            )
        else:
            self.etiqueta_tarea.config(text="Detenido")
            self._poner("FIN", "Me detuve", "Paré la demostración como pediste. Puedes pedirme algo nuevo.", tema.AVISO)
