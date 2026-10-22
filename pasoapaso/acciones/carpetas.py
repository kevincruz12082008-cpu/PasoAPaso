from ..datos.ubicaciones import ETIQUETAS, buscar_carpeta, ruta_ubicacion


def _nombre_libre(base, nombre):
    if not (base / nombre).exists():
        return nombre
    numero = 2
    while (base / f"{nombre} ({numero})").exists():
        numero += 1
    return f"{nombre} ({numero})"


def llegar_a(guia, ruta):
    guia.teclas(
        "win",
        "e",
        titulo="Abre el Explorador de archivos",
        detalle="Windows + E abre la ventana donde están todas tus carpetas y archivos.",
    )
    guia.esperar(2.8)
    guia.teclas(
        "ctrl",
        "l",
        titulo="Elige la barra de direcciones",
        detalle="Ctrl + L pone el cursor arriba, donde se escribe el camino hacia una carpeta.",
    )
    guia.escribir(
        str(ruta),
        titulo="Escribe dónde quieres ir",
        detalle="Esto se llama «ruta»: es el camino que sigue la computadora hasta la carpeta.",
    )
    guia.tecla("enter", titulo="Presiona Enter para entrar", detalle="Así el Explorador te lleva hasta ese lugar.")
    guia.esperar(2)


def crear_carpeta(guia, orden):
    clave = orden.datos.get("ubicacion") or "escritorio"
    base = ruta_ubicacion(clave)
    solicitado = orden.datos["nombre"]
    nombre = _nombre_libre(base, solicitado)
    guia.decir(
        "Vamos a crear una carpeta",
        f"Se llamará «{nombre}» y estará en {ETIQUETAS[clave]}.",
        tipo="info",
    )
    guia.pausar(2.5)
    if nombre != solicitado:
        guia.decir(
            "Ese nombre ya existía",
            f"Para no mezclar carpetas, usaré «{nombre}».",
            tipo="aviso",
        )
        guia.pausar(3)
    llegar_a(guia, base)
    guia.teclas(
        "ctrl",
        "shift",
        "n",
        titulo="Crea una carpeta nueva",
        detalle="Estas tres teclas juntas crean una carpeta y te dejan escribir su nombre.",
    )
    guia.esperar(1.2)
    guia.escribir(
        nombre,
        titulo=f"Escribe el nombre: {nombre}",
        detalle="El nombre de ejemplo aparece seleccionado, por eso al escribir se reemplaza solo.",
    )
    guia.tecla("enter", titulo="Presiona Enter para guardar el nombre", detalle="Y la carpeta queda lista.")
    guia.esperar(1.5)
    destino = base / nombre
    if not destino.exists():
        destino.mkdir(parents=True, exist_ok=True)
        guia.decir(
            "El teclado no alcanzó, la creé directamente",
            "A veces la ventana pierde la atención. La carpeta ya existe.",
            tipo="aviso",
        )
        guia.pausar(3)
    guia.memoria["ultima_carpeta"] = destino
    guia.decir(f"¡Listo! Creé la carpeta «{nombre}»", f"La encuentras en {ETIQUETAS[clave]}.", tipo="ok")
    guia.pausar(2)


def abrir_carpeta(guia, orden):
    nombre = orden.datos.get("nombre")
    clave = orden.datos.get("ubicacion")
    if nombre:
        ruta = buscar_carpeta(nombre, clave)
        if ruta is None:
            guia.decir(
                f"No encontré la carpeta «{nombre}»",
                "Busqué en Escritorio, Documentos, Descargas e Imágenes. Revisa que el nombre esté bien escrito.",
                tipo="aviso",
            )
            guia.pausar(4)
            return
    elif clave:
        ruta = ruta_ubicacion(clave)
    else:
        guia.decir("Vamos a abrir el Explorador de archivos", tipo="info")
        guia.pausar(2)
        guia.teclas(
            "win",
            "e",
            titulo="Abre el Explorador de archivos",
            detalle="Windows + E abre la ventana donde están todas tus carpetas y archivos.",
        )
        guia.esperar(2)
        return
    guia.decir("Vamos a abrir una carpeta", f"Voy a entrar a «{ruta.name}».", tipo="info")
    guia.pausar(2.2)
    llegar_a(guia, ruta)
    guia.decir(f"¡Listo! Esta es la carpeta «{ruta.name}»", tipo="ok")
    guia.pausar(2)


def abrir_ultima(guia, orden):
    ruta = guia.memoria.get("ultima_carpeta")
    if ruta is None:
        guia.decir("Todavía no hay una carpeta que abrir", "Primero pídeme crear una carpeta.", tipo="aviso")
        guia.pausar(3.5)
        return
    guia.decir("Vamos a abrir la carpeta nueva", f"Voy a entrar a «{ruta.name}».", tipo="info")
    guia.pausar(2.2)
    llegar_a(guia, ruta)
    guia.decir(f"¡Listo! Esta es la carpeta «{ruta.name}»", "Está vacía porque acaba de nacer.", tipo="ok")
    guia.pausar(2)
