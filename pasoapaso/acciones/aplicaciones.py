from ..datos.catalogo_apps import CATALOGO
from ..utilidades.plataforma import idioma_es


def abrir_por_busqueda(guia, nombre, termino):
    guia.tecla(
        "win",
        titulo="Abre el menú Inicio",
        detalle="Presiona la tecla con el logo de Windows, abajo a la izquierda de tu teclado.",
    )
    guia.esperar(1.5)
    guia.escribir(
        termino,
        titulo=f"Escribe «{termino}»",
        detalle="Windows busca el programa mientras escribes. No hace falta hacer clic en nada.",
    )
    guia.esperar(1.8)
    guia.tecla(
        "enter",
        titulo="Presiona Enter",
        detalle=f"Enter abre el primer resultado de la búsqueda: {nombre}.",
    )
    guia.esperar(2.5)


def abrir_catalogo(guia, clave):
    app = CATALOGO[clave]
    guia.decir(f"Vamos a abrir {app.nombre}", "Todo programa se puede abrir desde el teclado.", tipo="info")
    guia.pausar(2)
    if app.atajo:
        guia.teclas(*app.atajo, titulo=f"Abre {app.nombre}", detalle=app.detalle_atajo)
        guia.esperar(2.5)
    else:
        termino = app.busqueda_es if idioma_es() else app.busqueda_en
        abrir_por_busqueda(guia, app.nombre, termino)
    guia.decir(f"¡Listo! {app.nombre} se está abriendo", tipo="ok")
    guia.pausar(1.5)


def abrir_app(guia, orden):
    clave = orden.datos.get("clave")
    if clave:
        abrir_catalogo(guia, clave)
        return
    termino = orden.datos["termino"]
    guia.decir(f"Vamos a abrir «{termino}»", "Si Windows lo encuentra, se abrirá.", tipo="info")
    guia.pausar(2)
    abrir_por_busqueda(guia, termino, termino)
    guia.decir(f"Intenté abrir «{termino}»", "Si no apareció, revisa que el nombre esté bien escrito.", tipo="ok")
    guia.pausar(2)
