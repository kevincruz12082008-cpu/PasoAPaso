"""Ventana de acceso: entrar o crear una cuenta."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk

from .. import configuracion as cfg
from ..nucleo.nube import ClienteNube, ErrorNube
from ..nucleo.sesion import Sesion, cargar_preferencias, guardar_preferencias
from . import tema


class VentanaAcceso:
    def __init__(self, raiz: tk.Tk, cliente: ClienteNube | None = None):
        self.raiz = raiz
        self.cliente = cliente or ClienteNube()
        self.resultado: Sesion | None = None
        self.modo = "entrar"
        self._ocupado = False
        self._cola: queue.Queue = queue.Queue()
        self._cerrada = False
        self.preferencias = cargar_preferencias()

        self.ventana = tk.Toplevel(raiz)
        self.ventana.title(f"{cfg.NOMBRE_APP} · Entrar")
        self.ventana.configure(bg=tema.FONDO)
        self.ventana.resizable(False, False)
        self.ventana.protocol("WM_DELETE_WINDOW", self._cerrar)
        try:
            self._icono = tk.PhotoImage(file=str(cfg.RUTA_LOGO_64))
            self.ventana.iconphoto(True, self._icono)
        except tk.TclError:
            self._icono = None
        self._construir()
        self._centrar()
        self._cambiar_modo("entrar")
        self.ventana.grab_set()
        self.ventana.focus_force()
        self._verificar_servidor()
        self._sondear()

    # --- Construcción ----------------------------------------------------
    def _fuente(self, tamano, peso="normal"):
        return tema.fuente(tamano, peso)

    def _boton(self, padre, texto, comando, fondo, activo, tamano=12, ancho=None):
        boton = tk.Button(
            padre,
            text=texto,
            command=comando,
            bg=fondo,
            fg="#FFFFFF",
            activebackground=activo,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=tema.px(20),
            pady=tema.px(10),
            font=self._fuente(tamano, "bold"),
            cursor="hand2",
        )
        if ancho:
            boton.config(width=ancho)
        boton.bind("<Enter>", lambda _: boton.config(bg=activo))
        boton.bind("<Leave>", lambda _: boton.config(bg=fondo))
        return boton

    def _campo(self, padre, etiqueta, variable=None, mostrar=None, ayuda="", tipo="text"):
        marco = tk.Frame(padre, bg=tema.TARJETA)
        marco.pack(fill="x", pady=(0, 10))
        tk.Label(
            marco,
            text=etiqueta,
            font=self._fuente(10, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
        ).pack(fill="x")
        entrada = tk.Entry(
            marco,
            textvariable=variable,
            font=self._fuente(13),
            show=mostrar or "",
            relief="flat",
            bd=0,
            bg="#FFFDF8",
            fg=tema.TEXTO,
            insertbackground=tema.TEXTO,
            highlightthickness=2,
            highlightbackground=tema.BORDE,
            highlightcolor=tema.ACENTO,
        )
        entrada.pack(fill="x", ipady=tema.px(7), pady=(3, 0))
        if ayuda:
            tk.Label(
                marco,
                text=ayuda,
                font=self._fuente(8),
                fg=tema.SUAVE,
                bg=tema.TARJETA,
                anchor="w",
                justify="left",
                wraplength=tema.px(500),
            ).pack(fill="x")
        return entrada

    def _campo_clave(self, padre, etiqueta, variable):
        marco = tk.Frame(padre, bg=tema.TARJETA)
        marco.pack(fill="x", pady=(0, 10))
        tk.Label(
            marco, text=etiqueta, font=self._fuente(10, "bold"), fg=tema.TEXTO, bg=tema.TARJETA, anchor="w"
        ).pack(fill="x")
        fila = tk.Frame(marco, bg=tema.TARJETA)
        fila.pack(fill="x", pady=(3, 0))
        entrada = tk.Entry(
            fila,
            textvariable=variable,
            font=self._fuente(13),
            show="•",
            relief="flat",
            bd=0,
            bg="#FFFDF8",
            fg=tema.TEXTO,
            insertbackground=tema.TEXTO,
            highlightthickness=2,
            highlightbackground=tema.BORDE,
            highlightcolor=tema.ACENTO,
        )
        entrada.pack(side="left", fill="x", expand=True, ipady=tema.px(7))

        def alternar():
            if entrada.cget("show"):
                entrada.config(show="")
                ojo.config(text="Ocultar")
            else:
                entrada.config(show="•")
                ojo.config(text="Mostrar")

        ojo = tk.Button(
            fila,
            text="Mostrar",
            command=alternar,
            bg=tema.TARJETA,
            fg=tema.ACENTO,
            activebackground=tema.TARJETA,
            activeforeground=tema.ACENTO_OSCURO,
            relief="flat",
            bd=0,
            font=self._fuente(9, "bold"),
            cursor="hand2",
            padx=8,
        )
        ojo.pack(side="left")
        return entrada

    def _construir(self) -> None:
        ancho, alto = 940, 650
        self.ventana.geometry(f"{ancho}x{alto}")
        self.ventana.minsize(ancho, alto)

        lateral = tk.Frame(self.ventana, bg=tema.ACENTO_OSCURO, width=330)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)

        try:
            self._logo = tk.PhotoImage(file=str(cfg.RUTA_LOGO_128))
            tk.Label(lateral, image=self._logo, bg=tema.ACENTO_OSCURO).pack(pady=(44, 14))
        except tk.TclError:
            tk.Label(
                lateral, text="PasoAPaso", font=self._fuente(24, "bold"), fg="#FFFFFF", bg=tema.ACENTO_OSCURO
            ).pack(pady=(60, 14))

        tk.Label(
            lateral,
            text=cfg.NOMBRE_APP,
            font=self._fuente(26, "bold"),
            fg="#FFFFFF",
            bg=tema.ACENTO_OSCURO,
        ).pack()
        tk.Label(
            lateral,
            text="Aprende a tu ritmo,\ncon alguien que te acompaña.",
            font=self._fuente(11),
            fg=tema.ACENTO_CLARO,
            bg=tema.ACENTO_OSCURO,
            justify="center",
        ).pack(pady=(4, 28))

        for texto in (
            "Habla y te entiende",
            "Te muestra cada tecla",
            "Tus datos, solo tuyos",
        ):
            fila = tk.Frame(lateral, bg=tema.ACENTO_OSCURO)
            fila.pack(fill="x", padx=38, pady=5)
            tk.Label(
                fila,
                text="✓",
                font=self._fuente(11, "bold"),
                fg=tema.ACENTO_CLARO,
                bg=tema.ACENTO_OSCURO,
            ).pack(side="left", padx=(0, 9))
            tk.Label(
                fila,
                text=texto,
                font=self._fuente(10),
                fg="#E6FFFA",
                bg=tema.ACENTO_OSCURO,
                anchor="w",
            ).pack(side="left")

        tk.Label(
            lateral,
            text=f"Versión {cfg.VERSION}",
            font=self._fuente(8),
            fg="#9AD9D0",
            bg=tema.ACENTO_OSCURO,
        ).pack(side="bottom", pady=20)

        derecha = tk.Frame(self.ventana, bg=tema.TARJETA, padx=42, pady=28)
        derecha.pack(side="left", fill="both", expand=True)

        cabecera = tk.Frame(derecha, bg=tema.TARJETA)
        cabecera.pack(fill="x")
        self.estado_servidor = tk.Label(
            cabecera,
            text="● Comprobando conexión…",
            font=self._fuente(9, "bold"),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
        )
        self.estado_servidor.pack(side="right", pady=(4, 0))

        self.titulo = tk.Label(
            derecha,
            text="Entra a tu cuenta",
            font=self._fuente(24, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
        )
        self.titulo.pack(fill="x", pady=(0, 2))
        self.subtitulo = tk.Label(
            derecha,
            text="Tu historial y tus datos te esperan.",
            font=self._fuente(10),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
            anchor="w",
        )
        self.subtitulo.pack(fill="x", pady=(0, 16))

        pestañas = tk.Frame(derecha, bg=tema.TARJETA)
        pestañas.pack(fill="x", pady=(0, 14))
        self.boton_entrar = tk.Button(
            pestañas,
            text="Entrar",
            command=lambda: self._cambiar_modo("entrar"),
            font=self._fuente(10, "bold"),
            relief="flat",
            bd=0,
            padx=tema.px(18),
            pady=tema.px(7),
            cursor="hand2",
        )
        self.boton_entrar.pack(side="left")
        self.boton_registro = tk.Button(
            pestañas,
            text="Crear cuenta",
            command=lambda: self._cambiar_modo("registro"),
            font=self._fuente(10, "bold"),
            relief="flat",
            bd=0,
            padx=tema.px(18),
            pady=tema.px(7),
            cursor="hand2",
        )
        self.boton_registro.pack(side="left", padx=(8, 0))

        self.panel_entrar = tk.Frame(derecha, bg=tema.TARJETA)
        self.panel_registro = tk.Frame(derecha, bg=tema.TARJETA)
        self._construir_entrar()
        self._construir_registro()

        self.error = tk.Label(
            derecha,
            text="",
            font=self._fuente(9, "bold"),
            fg=tema.PELIGRO,
            bg=tema.TARJETA,
            justify="left",
            anchor="w",
            wraplength=tema.px(520),
        )
        self.error.pack(fill="x", pady=(4, 2))

        pie = tk.Frame(derecha, bg=tema.TARJETA)
        pie.pack(fill="x", side="bottom")
        tk.Button(
            pie,
            text="Usar sin conexión",
            command=self._usar_sin_conexion,
            bg=tema.TARJETA,
            fg=tema.SUAVE,
            activebackground=tema.TARJETA,
            activeforeground=tema.TEXTO,
            relief="flat",
            bd=0,
            font=self._fuente(9),
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            pie,
            text="Panel del administrador",
            command=self._abrir_admin,
            bg=tema.TARJETA,
            fg=tema.ACENTO,
            activebackground=tema.TARJETA,
            activeforeground=tema.ACENTO_OSCURO,
            relief="flat",
            bd=0,
            font=self._fuente(9, "bold"),
            cursor="hand2",
        ).pack(side="right")

    def _construir_entrar(self) -> None:
        marco = self.panel_entrar
        self.var_telefono = tk.StringVar(value=str(self.preferencias.get("telefono", "")))
        self.var_clave = tk.StringVar()
        self.entrada_telefono = self._campo(
            marco,
            "Número de teléfono",
            self.var_telefono,
            ayuda="El mismo número con el que creaste tu cuenta.",
            tipo="tel",
        )
        self.entrada_clave = self._campo_clave(marco, "Tu clave (4 a 8 números)", self.var_clave)
        self.entrada_telefono.bind("<Return>", lambda _: self.entrada_clave.focus_set())
        self.entrada_clave.bind("<Return>", lambda _: self._entrar())

        self.var_recordar = tk.BooleanVar(value=False)
        tk.Checkbutton(
            marco,
            text="Recordarme en esta computadora",
            variable=self.var_recordar,
            bg=tema.TARJETA,
            fg=tema.TEXTO,
            activebackground=tema.TARJETA,
            activeforeground=tema.TEXTO,
            font=self._fuente(9),
            cursor="hand2",
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        self.boton_entrar_form = self._boton(
            marco, "Entrar a mi cuenta", self._entrar, tema.ACENTO, tema.ACENTO_OSCURO, 12
        )
        self.boton_entrar_form.pack(fill="x", pady=(6, 8))
        tk.Button(
            marco,
            text="¿Olvidaste tu clave? Pídele ayuda al administrador.",
            command=self._olvido,
            bg=tema.TARJETA,
            fg=tema.SUAVE,
            activebackground=tema.TARJETA,
            activeforeground=tema.ACENTO,
            relief="flat",
            bd=0,
            font=self._fuente(9),
            cursor="hand2",
        ).pack(anchor="w")

    def _construir_registro(self) -> None:
        marco = self.panel_registro
        self.var_nombre = tk.StringVar()
        self.var_telefono_reg = tk.StringVar()
        self.var_edad = tk.StringVar()
        self.var_ciudad = tk.StringVar()
        self.var_experiencia = tk.StringVar(value=list(cfg.EXPERIENCIAS.values())[1])
        self.var_clave_reg = tk.StringVar()
        self.var_clave_reg2 = tk.StringVar()
        self.var_consentimiento = tk.BooleanVar(value=False)

        self._campo(marco, "Nombre completo", self.var_nombre)
        self.entrada_nombre = marco.winfo_children()[-1].winfo_children()[-1]
        fila = tk.Frame(marco, bg=tema.TARJETA)
        fila.pack(fill="x")
        izquierda = tk.Frame(fila, bg=tema.TARJETA)
        izquierda.pack(side="left", fill="x", expand=True, padx=(0, 8))
        derecha = tk.Frame(fila, bg=tema.TARJETA)
        derecha.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._campo(izquierda, "Teléfono", self.var_telefono_reg)
        self._campo(derecha, "Edad (opcional)", self.var_edad)

        fila2 = tk.Frame(marco, bg=tema.TARJETA)
        fila2.pack(fill="x")
        izquierda2 = tk.Frame(fila2, bg=tema.TARJETA)
        izquierda2.pack(side="left", fill="x", expand=True, padx=(0, 8))
        derecha2 = tk.Frame(fila2, bg=tema.TARJETA)
        derecha2.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._campo(izquierda2, "Ciudad (opcional)", self.var_ciudad)
        etiqueta_exp = tk.Frame(derecha2, bg=tema.TARJETA)
        etiqueta_exp.pack(fill="x", pady=(0, 10))
        tk.Label(
            etiqueta_exp,
            text="¿Cuánto usas la computadora?",
            font=self._fuente(10, "bold"),
            fg=tema.TEXTO,
            bg=tema.TARJETA,
            anchor="w",
        ).pack(fill="x")
        combo = ttk.Combobox(
            etiqueta_exp,
            textvariable=self.var_experiencia,
            values=list(cfg.EXPERIENCIAS.values()),
            state="readonly",
            font=self._fuente(10),
        )
        combo.pack(fill="x", pady=(3, 0))
        combo.bind("<<ComboboxSelected>>", lambda _: None)

        fila3 = tk.Frame(marco, bg=tema.TARJETA)
        fila3.pack(fill="x")
        izquierda3 = tk.Frame(fila3, bg=tema.TARJETA)
        izquierda3.pack(side="left", fill="x", expand=True, padx=(0, 8))
        derecha3 = tk.Frame(fila3, bg=tema.TARJETA)
        derecha3.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._campo_clave(izquierda3, "Clave (4 a 8 números)", self.var_clave_reg)
        self._campo_clave(derecha3, "Repite tu clave", self.var_clave_reg2)

        casilla = tk.Checkbutton(
            marco,
            text="Acepto que se guarden mis datos y mis consultas para poder ayudarme.",
            variable=self.var_consentimiento,
            bg=tema.TARJETA,
            fg=tema.TEXTO,
            activebackground=tema.TARJETA,
            activeforeground=tema.TEXTO,
            font=self._fuente(9),
            wraplength=tema.px(520),
            justify="left",
            cursor="hand2",
        )
        casilla.pack(fill="x", pady=(0, 8), anchor="w")

        self.boton_registro_form = self._boton(
            marco, "Crear mi cuenta", self._registrar, tema.ACENTO, tema.ACENTO_OSCURO, 12
        )
        self.boton_registro_form.pack(fill="x", pady=(2, 4))

    # --- Comportamiento --------------------------------------------------
    def _centrar(self) -> None:
        self.ventana.update_idletasks()
        ancho = self.ventana.winfo_width()
        alto = self.ventana.winfo_height()
        x = (self.ventana.winfo_screenwidth() - ancho) // 2
        y = max(0, (self.ventana.winfo_screenheight() - alto) // 2 - 20)
        self.ventana.geometry(f"+{x}+{y}")

    def _cambiar_modo(self, modo: str) -> None:
        if self._ocupado:
            return
        self.modo = modo
        activo = {"bg": tema.ACENTO, "fg": "#FFFFFF"}
        inactivo = {"bg": tema.FONDO, "fg": tema.SUAVE}
        self.boton_entrar.config(**(activo if modo == "entrar" else inactivo))
        self.boton_registro.config(**(activo if modo == "registro" else inactivo))
        self.panel_entrar.pack_forget()
        self.panel_registro.pack_forget()
        self.error.config(text="")
        if modo == "entrar":
            self.titulo.config(text="Entra a tu cuenta")
            self.subtitulo.config(text="Tu historial y tus datos te esperan.")
            self.panel_entrar.pack(fill="x")
            self.ventana.after(50, self.entrada_telefono.focus_set)
        else:
            self.titulo.config(text="Crea tu cuenta")
            self.subtitulo.config(text="Solo tu nombre, tu teléfono y una clave de 4 números.")
            self.panel_registro.pack(fill="x")
            self.ventana.after(50, self.entrada_nombre.focus_set)

    def _verificar_servidor(self) -> None:
        def revisar():
            try:
                self.cliente.estado()
                self._cola.put(("servidor", True))
            except Exception:
                self._cola.put(("servidor", False))

        threading.Thread(target=revisar, daemon=True).start()

    def _sondear(self) -> None:
        if self._cerrada:
            return
        try:
            while True:
                tipo, datos = self._cola.get_nowait()
                if tipo == "servidor":
                    if datos:
                        self.estado_servidor.config(text="● En línea", fg=tema.OK)
                    else:
                        self.estado_servidor.config(text="● Sin conexión", fg=tema.AVISO)
                elif tipo == "ok":
                    try:
                        datos()
                    except Exception as error:
                        self._ocupado = False
                        self._habilitar(True)
                        self.error.config(text=self._mensaje_error(error))
                elif tipo == "error":
                    self._ocupado = False
                    self._habilitar(True)
                    self.error.config(text=str(datos))
                elif tipo == "terminar":
                    self._terminar(datos)
        except queue.Empty:
            pass
        self.ventana.after(100, self._sondear)

    def _hilo(self, funcion, al_terminar) -> None:
        def trabajar():
            try:
                resultado = funcion()
            except Exception as error:
                self._cola.put(("error", self._mensaje_error(error)))
                return
            self._cola.put(("ok", lambda r=resultado: al_terminar(r)))

        threading.Thread(target=trabajar, daemon=True).start()

    def _mensaje_error(self, error: Exception) -> str:
        if isinstance(error, ErrorNube):
            return error.mensaje
        return f"No pude completar la operación: {error}"

    def _habilitar(self, activo: bool) -> None:
        estado = "normal" if activo else "disabled"
        for boton in (self.boton_entrar_form, self.boton_registro_form):
            try:
                boton.config(state=estado)
            except tk.TclError:
                pass

    def _entrar(self) -> None:
        if self._ocupado:
            return
        telefono = self.var_telefono.get().strip()
        clave = self.var_clave.get().strip()
        digitos = "".join(c for c in telefono if c.isdigit())
        if len(digitos) < 8:
            self.error.config(text="Escribe tu número de teléfono (al menos 8 números).")
            self.entrada_telefono.focus_set()
            return
        if not (4 <= len(clave) <= 8 and clave.isdigit()):
            self.error.config(text="Tu clave son de 4 a 8 números.")
            self.entrada_clave.focus_set()
            return
        self._ocupado = True
        self.error.config(text="")
        self._habilitar(False)
        self._hilo(lambda: self.cliente.entrar(telefono, clave), self._al_entrar)

    def _al_entrar(self, datos: dict) -> None:
        if not datos.get("token") or not datos.get("usuario"):
            self._ocupado = False
            self._habilitar(True)
            self.error.config(text="El servidor no devolvió una sesión. Inténtalo de nuevo.")
            return
        guardar_preferencias({"telefono": self.var_telefono.get().strip()})
        self._terminar(
            Sesion(
                token=str(datos["token"]),
                usuario=datos["usuario"],
                base_url=cfg.URL_SERVIDOR,
                modo="nube",
            )
        )

    def _registrar(self) -> None:
        if self._ocupado:
            return
        nombre = self.var_nombre.get().strip()
        telefono = self.var_telefono_reg.get().strip()
        clave = self.var_clave_reg.get().strip()
        clave2 = self.var_clave_reg2.get().strip()
        digitos = "".join(c for c in telefono if c.isdigit())
        if len(nombre) < 2:
            self.error.config(text="Escribe tu nombre completo.")
            return
        if len(digitos) < 8:
            self.error.config(text="Escribe tu número de teléfono (al menos 8 números).")
            return
        if not (4 <= len(clave) <= 8 and clave.isdigit()):
            self.error.config(text="La clave debe tener entre 4 y 8 números.")
            return
        if clave != clave2:
            self.error.config(text="Las dos claves no son iguales. Vuelve a escribirla.")
            return
        if not self.var_consentimiento.get():
            self.error.config(text="Marca la casilla para que podamos guardar tus datos.")
            return
        edad = self.var_edad.get().strip()
        if edad:
            if not edad.isdigit() or not (5 <= int(edad) <= 120):
                self.error.config(text="La edad debe ser un número entre 5 y 120.")
                return
        experiencia = "poco"
        for clave_exp, texto in cfg.EXPERIENCIAS.items():
            if texto == self.var_experiencia.get():
                experiencia = clave_exp
                break
        ciudad = self.var_ciudad.get().strip()
        self._ocupado = True
        self.error.config(text="")
        self._habilitar(False)
        self._hilo(
            lambda: self.cliente.registrar(
                telefono=telefono,
                nombre=nombre,
                clave=clave,
                edad=int(edad) if edad else None,
                ciudad=ciudad,
                experiencia=experiencia,
                consentimiento=True,
            ),
            self._al_registrar,
        )

    def _al_registrar(self, datos: dict) -> None:
        if not datos.get("token") or not datos.get("usuario"):
            self._ocupado = False
            self._habilitar(True)
            self.error.config(text="El servidor no devolvió una sesión. Inténtalo de nuevo.")
            return
        guardar_preferencias({"telefono": self.var_telefono_reg.get().strip()})
        self._terminar(
            Sesion(
                token=str(datos["token"]),
                usuario=datos["usuario"],
                base_url=cfg.URL_SERVIDOR,
                modo="nube",
            )
        )

    def _terminar(self, sesion: Sesion) -> None:
        self.resultado = sesion
        if self.var_recordar.get():
            try:
                sesion.guardar()
            except OSError:
                pass
        else:
            Sesion.borrar()
        self._cerrar()

    def _usar_sin_conexion(self) -> None:
        if self._ocupado:
            return
        nombre = simpledialog.askstring(
            "Usar sin conexión",
            "¿Cómo te llamas? (Puedes usar solo tu nombre.)",
            parent=self.ventana,
        )
        if nombre is None:
            return
        nombre = nombre.strip() or "amigo"
        messagebox.showinfo(
            "Modo sin conexión",
            "Vas a usar PasoAPaso sin conectarte al servidor.\n\n"
            "La app puede enseñarte igual, pero lo que pidas no se guardará en tu cuenta "
            "hasta que vuelvas a entrar con internet.",
            parent=self.ventana,
        )
        self._terminar(
            Sesion(
                token="",
                usuario={"nombre": nombre, "telefono": ""},
                base_url=cfg.URL_SERVIDOR,
                modo="local",
            )
        )

    def _olvido(self) -> None:
        messagebox.showinfo(
            "¿Olvidaste tu clave?",
            "Pídele al administrador de PasoAPaso que te genere una clave nueva.\n\n"
            "Por seguridad, nadie puede ver tu clave actual.",
            parent=self.ventana,
        )

    def _abrir_admin(self) -> None:
        try:
            webbrowser.open(self.cliente.url_admin())
        except Exception:
            self.error.config(text="No pude abrir el navegador. Abre el panel desde el servidor.")

    def _cerrar(self) -> None:
        self._cerrada = True
        try:
            self.ventana.grab_release()
        except tk.TclError:
            pass
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass

    def mostrar(self) -> Sesion | None:
        self.raiz.wait_window(self.ventana)
        return self.resultado
