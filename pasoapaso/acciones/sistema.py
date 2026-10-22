import pyautogui

AJUSTES_VOLUMEN = {
    "subir": ("volumeup", "Subimos el volumen", 6),
    "bajar": ("volumedown", "Bajamos el volumen", 6),
    "silenciar": ("volumemute", "Silenciamos el sonido", 1),
}


def ajustar_volumen(guia, orden):
    tecla, titulo, repeticiones = AJUSTES_VOLUMEN[orden.datos["accion"]]
    guia.decir(
        titulo,
        "Muchos teclados tienen teclas con un altavoz para esto. También puedes hacer clic en el altavoz junto al reloj.",
        teclas=(tecla,),
    )
    guia.pausar(2.5)
    for _ in range(repeticiones):
        guia.verificar()
        pyautogui.press(tecla)
        guia.pausar(0.35)
    guia.decir("¡Listo!", "Si no notaste el cambio, revisa que tus bocinas estén encendidas.", tipo="ok")
    guia.pausar(2)


def mostrar_escritorio(guia, orden):
    guia.teclas(
        "win",
        "d",
        titulo="Mostramos el escritorio",
        detalle="Windows + D esconde todas las ventanas. Si lo presionas otra vez, vuelven.",
    )
    guia.decir("¡Listo! Este es tu escritorio", tipo="ok")
    guia.pausar(2)


def cerrar_ventana(guia, orden):
    guia.teclas(
        "alt",
        "f4",
        titulo="Cerramos la ventana de adelante",
        detalle="Alt + F4 cierra el programa que estás viendo. Si tenías algo sin guardar, te preguntará.",
    )
    guia.decir("¡Listo!", tipo="ok")
    guia.pausar(2)


def escribir_texto(guia, orden):
    guia.decir(
        "Vamos a escribir",
        "El texto aparecerá en la ventana que tengas abierta. Ten un programa de escritura a la mano.",
        tipo="info",
    )
    guia.pausar(2.5)
    guia.escribir(
        orden.datos["texto"],
        titulo="Escribimos tu texto",
        detalle="Así se ve cuando alguien escribe con el teclado, letra por letra.",
    )
    guia.decir("¡Listo!", tipo="ok")
    guia.pausar(2)
