import tkinter as tk
import webbrowser
from tkinter import messagebox

from .. import configuracion as cfg
from ..nucleo.sesion import Sesion
from . import tema


def abrir_soporte(ventana):
    try:
        webbrowser.open(cfg.URL_SERVIDOR + "/soporte/")
    except Exception:
        if cfg.PAGINA_SOPORTE.exists():
            webbrowser.open(cfg.PAGINA_SOPORTE.as_uri())
        else:
            messagebox.showerror(
                cfg.NOMBRE_APP,
                "No encuentro la página de soporte técnico.",
                parent=ventana,
            )


def _abrir(url: str, ventana):
    try:
        webbrowser.open(url)
    except Exception:
        messagebox.showerror("PasoAPaso", "No pude abrir el navegador.", parent=ventana)


def mostrar_acerca_de(raiz, sesion: Sesion | None = None):
    ventana = tk.Toplevel(raiz)
    ventana.title(f"Acerca de {cfg.NOMBRE_APP}")
    ventana.configure(bg=tema.FONDO)
    ventana.resizable(False, False)
    ventana.transient(raiz)

    marco = tk.Frame(ventana, bg=tema.FONDO, padx=tema.px(30), pady=tema.px(22))
    marco.pack()
    try:
        logo = tk.PhotoImage(file=str(cfg.RUTA_LOGO_128))
        tk.Label(marco, image=logo, bg=tema.FONDO).pack()
        ventana._logo = logo
    except tk.TclError:
        pass
    tk.Label(marco, text=cfg.NOMBRE_APP, font=tema.fuente(22, "bold"), fg=tema.ACENTO, bg=tema.FONDO).pack()
    tk.Label(marco, text=cfg.LEMA, font=tema.fuente(10), fg=tema.SUAVE, bg=tema.FONDO).pack(pady=(2, 10))
    tk.Label(
        marco,
        text=f"Versión {cfg.VERSION} · Proyecto de " + " y ".join(cfg.CLASES),
        font=tema.fuente(9),
        fg=tema.TEXTO,
        bg=tema.FONDO,
    ).pack()

    if sesion:
        tk.Label(
            marco,
            text=f"Sesión: {sesion.nombre} · {sesion.telefono or 'modo local'}",
            font=tema.fuente(9),
            fg=tema.SUAVE,
            bg=tema.FONDO,
        ).pack(pady=(4, 0))

    caja = tk.Frame(marco, bg=tema.TARJETA, highlightbackground=tema.BORDE, highlightthickness=1, padx=tema.px(16), pady=tema.px(12))
    caja.pack(fill="x", pady=(14, 10))
    tk.Label(
        caja,
        text="Cómo funciona esta versión",
        font=tema.fuente(10, "bold"),
        fg=tema.TEXTO,
        bg=tema.TARJETA,
        anchor="w",
    ).pack(fill="x")
    for linea in (
        "• La app se ejecuta en tu Windows y usa el mouse y el teclado reales.",
        "• Tu cuenta, tu historial y las consultas viven en una base de datos SQLite.",
        "• El panel del administrador es una página web privada.",
        "• Si las reglas no entienden una orden, Gemini puede ayudar a interpretarla.",
        "• La voz se convierte en texto en tu equipo; solo el texto viaja al servidor.",
    ):
        tk.Label(
            caja,
            text=linea,
            font=tema.fuente(8),
            fg=tema.SUAVE,
            bg=tema.TARJETA,
            anchor="w",
            justify="left",
            wraplength=tema.px(430),
        ).pack(fill="x", pady=1)
    tk.Label(
        caja,
        text=f"Servidor: {cfg.URL_SERVIDOR}",
        font=tema.fuente(7),
        fg=tema.SUAVE,
        bg=tema.TARJETA,
        anchor="w",
    ).pack(fill="x", pady=(6, 0))

    tk.Label(marco, text="Integrantes", font=tema.fuente(10, "bold"), fg=tema.ACENTO, bg=tema.FONDO).pack(
        pady=(6, 2)
    )
    for nombre in cfg.INTEGRANTES:
        tk.Label(marco, text=nombre, font=tema.fuente(9), fg=tema.TEXTO, bg=tema.FONDO).pack()

    botones = tk.Frame(marco, bg=tema.FONDO)
    botones.pack(fill="x", pady=(14, 0))
    tk.Button(
        botones,
        text="Panel del administrador",
        command=lambda: _abrir(cfg.URL_SERVIDOR + "/admin", ventana),
        bg=tema.ACENTO,
        fg="#FFFFFF",
        activebackground=tema.ACENTO_OSCURO,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=tema.px(14),
        pady=tema.px(7),
        font=tema.fuente(9, "bold"),
        cursor="hand2",
    ).pack(side="left")
    tk.Button(
        botones,
        text="Mi cuenta en internet",
        command=lambda: _abrir(cfg.URL_SERVIDOR + "/portal", ventana),
        bg=tema.TECLA,
        fg=tema.TEXTO,
        activebackground=tema.BORDE,
        activeforeground=tema.TEXTO,
        relief="flat",
        bd=0,
        padx=tema.px(14),
        pady=tema.px(7),
        font=tema.fuente(9, "bold"),
        cursor="hand2",
    ).pack(side="left", padx=(6, 0))
    tk.Button(
        botones,
        text="Soporte técnico",
        command=lambda: abrir_soporte(ventana),
        bg=tema.TECLA,
        fg=tema.TEXTO,
        activebackground=tema.BORDE,
        activeforeground=tema.TEXTO,
        relief="flat",
        bd=0,
        padx=tema.px(14),
        pady=tema.px(7),
        font=tema.fuente(9, "bold"),
        cursor="hand2",
    ).pack(side="left", padx=(6, 0))

    tk.Button(
        marco,
        text="Cerrar",
        command=ventana.destroy,
        bg=tema.SUAVE,
        fg="#FFFFFF",
        activebackground=tema.TEXTO,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=tema.px(22),
        pady=tema.px(6),
        font=tema.fuente(10, "bold"),
        cursor="hand2",
    ).pack(pady=(12, 0))

    ventana.update_idletasks()
    x = raiz.winfo_x() + (raiz.winfo_width() - ventana.winfo_width()) // 2
    y = raiz.winfo_y() + (raiz.winfo_height() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")
    ventana.grab_set()
