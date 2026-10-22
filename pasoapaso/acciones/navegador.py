from urllib.parse import quote_plus

from .. import configuracion as cfg
from ..utilidades.plataforma import hay_internet
from .aplicaciones import abrir_catalogo


def avisar_sin_internet(guia):
    if not hay_internet():
        guia.decir(
            "No veo conexión a internet",
            "Te muestro igual cómo se hace. Para ver los resultados, conéctate a una red Wi-Fi.",
            tipo="aviso",
        )
        guia.pausar(4)


def preparar_navegador(guia, clave="chrome"):
    abrir_catalogo(guia, clave)
    guia.esperar(3.5)
    guia.teclas(
        "win",
        "up",
        titulo="Agrandamos la ventana",
        detalle="Windows + flecha arriba hace la ventana más grande para que todo se vea mejor.",
    )
    guia.esperar(1.5)


def ir_a(guia, direccion, titulo, detalle):
    guia.teclas(
        "ctrl",
        "l",
        titulo="Elige la barra de direcciones",
        detalle="Ctrl + L pone el cursor arriba, donde se escriben las direcciones y las búsquedas.",
    )
    guia.escribir(direccion, titulo=titulo, detalle=detalle)
    guia.tecla("enter", titulo="Presiona Enter", detalle="Enter le dice al navegador que vaya a lo que escribiste.")
    guia.esperar(4)


def buscar_web(guia, orden):
    consulta = orden.datos.get("consulta", "")
    clave = orden.datos.get("navegador", "chrome")
    guia.decir("Vamos a buscar en internet", "Para eso usamos un navegador, como Chrome.", tipo="info")
    guia.pausar(2.2)
    avisar_sin_internet(guia)
    preparar_navegador(guia, clave)
    if consulta:
        ir_a(
            guia,
            consulta,
            f"Escribe lo que buscas: «{consulta}»",
            "En esta barra también puedes escribir palabras sueltas y el navegador las busca por ti.",
        )
        guia.decir("Estos son los resultados", "Haz clic en el que más te guste.", tipo="ok")
    else:
        guia.decir("El navegador está listo", "Escribe lo que quieras buscar en la barra de arriba.", tipo="ok")
    guia.pausar(2.5)


def reproducir_youtube(guia, orden):
    consulta = orden.datos.get("consulta", "")
    reproducir = orden.datos.get("reproducir", False)
    guia.decir("Vamos a usar YouTube", "YouTube es una página web, así que la abrimos con el navegador.", tipo="info")
    guia.pausar(2.2)
    avisar_sin_internet(guia)
    preparar_navegador(guia)
    if consulta:
        direccion = "youtube.com/results?search_query=" + quote_plus(consulta)
        ir_a(
            guia,
            direccion,
            f"Escribe la dirección de la búsqueda: «{consulta}»",
            "Esta dirección le dice a YouTube qué buscar. Normalmente lo haces con la lupa de la página.",
        )
    else:
        ir_a(guia, "youtube.com", "Escribe youtube.com", "Así se escribe la dirección de una página web.")
    if reproducir and cfg.REPRODUCIR_PRIMER_RESULTADO:
        guia.esperar(2.5)
        guia.mover_y_clic(
            *cfg.POSICION_PRIMER_VIDEO,
            titulo="Hacemos clic en el primer video",
            detalle="Mira cómo se mueve el mouse. Un clic sobre un video lo reproduce.",
        )
        guia.decir("¡Listo! Tu video empezó", "Para pausarlo, haz clic sobre él o presiona la barra espaciadora.", tipo="ok")
    elif consulta:
        guia.decir("Estos son los resultados", "Haz clic en el video que quieras ver.", tipo="ok")
    else:
        guia.decir("YouTube está listo", tipo="ok")
    guia.pausar(2.5)


def abrir_sitio(guia, orden):
    direccion = orden.datos["direccion"]
    nombre = orden.datos.get("nombre", direccion)
    guia.decir(f"Vamos a abrir {nombre}", "Las páginas web se abren desde un navegador.", tipo="info")
    guia.pausar(2.2)
    avisar_sin_internet(guia)
    preparar_navegador(guia)
    ir_a(guia, direccion, f"Escribe la dirección: {direccion}", "Así se escribe la dirección de una página web.")
    guia.decir(f"¡Listo! Esta es la página de {nombre}", tipo="ok")
    guia.pausar(2.5)
