"""Ventana «Mi historial» de la app de escritorio."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from .. import configuracion as cfg
from ..nucleo.nube import ClienteNube, ErrorNube
from ..nucleo.sesion import Cola, Sesion
from . import tema


class VentanaHistorial:
    def __init__(self, raiz: tk.Tk, nube: ClienteNube, sesion: Sesion, cola: Cola):
        self.raiz = raiz
        self.nube = nube
        self.sesion = sesion
        self.cola = cola
        self._cola: queue.Queue = queue.Queue()

        self.ventana = tk.Toplevel(raiz)
        self.ventana.title(f"{cfg.NOMBRE_APP} · Mi historial")
        self.ventana.configure(bg=tema.FONDO)
        self.ventana.geometry("720x620")
        self.ventana.minsize(620, 480)
        self.ventana.transient(raiz)
        try:
            self._icono = tk.PhotoImage(file=str(cfg.RUTA_LOGO_64))
            self.ventana.iconphoto(True, self._icono)
        except tk.TclError:
            pass
        self._construir()
        self._cargar()
        self._sondear()
        self.ventana.grab_set()

    def _construir(self) -> None:
        cabecera = tk.Frame(self.ventana, bg=tema.FONDO, padx=tema.px(24), pady=tema.px(18))
        cabecera.pack(fill="x")
        izquierda = tk.Frame(cabecera, bg=tema.FONDO)
        izquierda.pack(side="left")
        tk.Label(
            izquierda,
            text="Mi historial",
            font=tema.fuente(21, "bold"),
            fg=tema.ACENTO,
            bg=tema.FONDO,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            izquierda,
            text="Todo lo que le has pedido a PasoAPaso, lo más reciente primero.",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            anchor="w",
        ).pack(anchor="w")
        tk.Button(
            cabecera,
            text="Cerrar",
            command=self.ventana.destroy,
            bg=tema.TECLA,
            fg=tema.TEXTO,
            activebackground=tema.BORDE,
            activeforeground=tema.TEXTO,
            relief="flat",
            bd=0,
            font=tema.fuente(9, "bold"),
            padx=tema.px(14),
            pady=tema.px(6),
            cursor="hand2",
        ).pack(side="right")

        self.estado = tk.Label(
            self.ventana,
            text="Cargando tus consultas…",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
            padx=tema.px(24),
            anchor="w",
        )
        self.estado.pack(fill="x")

        contenedor = tk.Frame(self.ventana, bg=tema.FONDO, padx=tema.px(20), pady=tema.px(10))
        contenedor.pack(fill="both", expand=True)
        self.lienzo = tk.Canvas(contenedor, bg=tema.FONDO, highlightthickness=0)
        barra = tk.Scrollbar(contenedor, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lienzo.pack(side="left", fill="both", expand=True)
        self.interior = tk.Frame(self.lienzo, bg=tema.FONDO)
        self._ventana_interior = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        self.interior.bind(
            "<Configure>",
            lambda _: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")),
        )
        self.lienzo.bind(
            "<Configure>",
            lambda evento: self.lienzo.itemconfigure(self._ventana_interior, width=evento.width),
        )
        self.ventana.bind("<MouseWheel>", self._rueda)

        pie = tk.Frame(self.ventana, bg=tema.FONDO, padx=tema.px(24), pady=tema.px(12))
        pie.pack(fill="x")
        self.enlace_cuenta = tk.Label(
            pie,
            text="Abrir mi cuenta en internet",
            font=tema.fuente(9, "underline"),
            fg=tema.ACENTO,
            bg=tema.FONDO,
            cursor="hand2",
        )
        self.enlace_cuenta.pack(side="left")
        self.enlace_cuenta.bind("<Button-1>", lambda _: self._abrir_cuenta())
        tk.Label(
            pie,
            text=f"{self.cola.contar()} pendiente(s) de enviar" if self.cola.contar() else "",
            font=tema.fuente(9),
            fg=tema.AVISO,
            bg=tema.FONDO,
        ).pack(side="right")

    def _rueda(self, evento) -> None:
        self.lienzo.yview_scroll(int(-1 * (evento.delta / 120)), "units")

    def _cargar(self) -> None:
        def cargar():
            if self.sesion.es_local or not self.sesion.token:
                self._cola.put(("local", None))
                return
            try:
                datos = self.nube.historial(40)
                self._cola.put(("ok", datos.get("consultas") or []))
            except ErrorNube as error:
                self._cola.put(("error", error.mensaje))
            except Exception as error:
                self._cola.put(("error", str(error)))

        threading.Thread(target=cargar, daemon=True).start()

    def _sondear(self) -> None:
        try:
            while True:
                tipo, datos = self._cola.get_nowait()
                if tipo == "ok":
                    self._mostrar_consultas(datos)
                elif tipo == "local":
                    self._mostrar_pendientes()
                elif tipo == "error":
                    self.estado.config(text=str(datos), fg=tema.AVISO)
                    self._mostrar_pendientes(solo_pendientes=True)
        except queue.Empty:
            pass
        try:
            self.ventana.after(100, self._sondear)
        except tk.TclError:
            pass

    def _limpiar(self) -> None:
        for hijo in self.interior.winfo_children():
            hijo.destroy()

    def _mostrar_consultas(self, consultas) -> None:
        self._limpiar()
        if not consultas:
            self.estado.config(text="Todavía no tienes consultas. ¡Pídele algo a PasoAPaso!", fg=tema.SUAVE)
            return
        self.estado.config(
            text=f"{len(consultas)} consulta(s) guardadas en tu cuenta.", fg=tema.SUAVE
        )
        for consulta in consultas:
            self._tarjeta(
                consulta.get("texto", ""),
                consulta.get("fecha", ""),
                consulta.get("origen", ""),
                consulta.get("estado", ""),
                bool(consulta.get("ia_usada")),
                consulta.get("error") or "",
            )

    def _mostrar_pendientes(self, solo_pendientes=False) -> None:
        self._limpiar()
        pendientes = self.cola.pendientes()
        if not pendientes:
            if not solo_pendientes:
                self.estado.config(
                    text="No pude cargar tu historial y no hay consultas pendientes.", fg=tema.AVISO
                )
            return
        self.estado.config(
            text=f"{len(pendientes)} consulta(s) guardadas en este equipo, esperando conexión.",
            fg=tema.AVISO,
        )
        for elemento in reversed(pendientes):
            datos = elemento.get("datos") or {}
            self._tarjeta(
                datos.get("texto", "(consulta)"),
                "",
                datos.get("origen", "offline"),
                datos.get("estado", "pendiente"),
                False,
                datos.get("error", ""),
            )

    def _tarjeta(self, texto, fecha, origen, estado, ia, error) -> None:
        colores = {
            "completado": (tema.OK_CLARO, tema.OK, "Completado"),
            "detenido": (tema.TECLA, tema.SUAVE, "Detenido"),
            "error": (tema.PELIGRO_CLARO, tema.PELIGRO, "Error"),
            "sin_entender": (tema.AVISO_CLARO, tema.AVISO, "No entendida"),
            "pendiente": (tema.AVISO_CLARO, tema.AVISO, "Pendiente"),
        }
        fondo, color, etiqueta = colores.get(estado, (tema.TECLA, tema.SUAVE, estado))
        tarjeta = tk.Frame(
            self.interior,
            bg=tema.TARJETA,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
            padx=tema.px(14),
            pady=tema.px(11),
        )
        tarjeta.pack(fill="x", pady=4, padx=2)
        cabecera = tk.Frame(tarjeta, bg=tema.TARJETA)
        cabecera.pack(fill="x")
        tk.Label(
            cabecera,
            text=fecha or "Guardada en este equipo",
            font=tema.fuente(8),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
        ).pack(side="left")
        if ia:
            tk.Label(
                cabecera,
                text="✦ IA",
                font=tema.fuente(8, "bold"),
                fg=tema.VOZ_OSCURO,
                bg=tema.VOZ_CLARO,
                padx=6,
            ).pack(side="right")
        tk.Label(
            cabecera,
            text=etiqueta,
            font=tema.fuente(8, "bold"),
            fg=color,
            bg=fondo,
            padx=7,
            pady=1,
        ).pack(side="right", padx=(0, 5))
        tk.Label(
            tarjeta,
            text=texto,
            font=tema.fuente(10),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
            justify="left",
            wraplength=tema.px(600),
        ).pack(fill="x", pady=(5, 0))
        if error:
            tk.Label(
                tarjeta,
                text=error[:200],
                font=tema.fuente(8),
                fg=tema.PELIGRO,
                bg=tema.TARJETA,
                anchor="w",
                justify="left",
                wraplength=tema.px(600),
            ).pack(fill="x", pady=(3, 0))

    def _abrir_cuenta(self) -> None:
        try:
            webbrowser.open(self.nube.base_url + "/portal")
        except Exception:
            messagebox.showerror("Mi cuenta", "No pude abrir el navegador.", parent=self.ventana)
