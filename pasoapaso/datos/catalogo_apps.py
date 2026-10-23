from dataclasses import dataclass


@dataclass(frozen=True)
class Aplicacion:
    nombre: str
    busqueda_es: str
    busqueda_en: str
    alias: tuple
    atajo: tuple = ()
    detalle_atajo: str = ""


CATALOGO = {
    "calculadora": Aplicacion("Calculadora", "calculadora", "calculator", ("calculadora", "calculator", "calc")),
    "bloc": Aplicacion("Bloc de notas", "bloc de notas", "notepad", ("bloc de notas", "notepad", "bloc", "notas")),
    "paint": Aplicacion("Paint", "paint", "paint", ("paint", "pintura")),
    "explorador": Aplicacion(
        "el Explorador de archivos", "explorador de archivos", "file explorer",
        ("explorador", "explorador de archivos", "explorador de windows", "archivos", "mis archivos", "mi pc", "este equipo"),
        ("win", "e"),
        "Windows + E abre la ventana donde están todas tus carpetas y archivos.",
    ),
    "chrome": Aplicacion("Google Chrome", "chrome", "chrome", ("chrome", "google chrome", "navegador", "internet")),
    "edge": Aplicacion("Microsoft Edge", "edge", "edge", ("edge", "microsoft edge")),
    "firefox": Aplicacion("Firefox", "firefox", "firefox", ("firefox", "mozilla firefox", "mozilla")),
    "word": Aplicacion("Word", "word", "word", ("word", "microsoft word")),
    "excel": Aplicacion("Excel", "excel", "excel", ("excel", "microsoft excel")),
    "powerpoint": Aplicacion("PowerPoint", "powerpoint", "powerpoint", ("powerpoint", "power point", "presentaciones")),
    "configuracion": Aplicacion(
        "Configuración", "configuracion", "settings",
        ("configuracion", "ajustes", "opciones", "settings"),
        ("win", "i"),
        "Windows + I abre la configuración de tu computadora.",
    ),
    "tareas": Aplicacion(
        "el Administrador de tareas", "administrador de tareas", "task manager",
        ("administrador de tareas", "task manager", "tareas"),
        ("ctrl", "shift", "esc"),
        "Ctrl + Mayús + Esc muestra qué programas están funcionando.",
    ),
    "cmd": Aplicacion("el Símbolo del sistema", "cmd", "cmd", ("simbolo del sistema", "cmd", "consola", "terminal")),
    "camara": Aplicacion("la Cámara", "camara", "camera", ("camara", "camera")),
    "spotify": Aplicacion("Spotify", "spotify", "spotify", ("spotify",)),
    "whatsapp": Aplicacion("WhatsApp", "whatsapp", "whatsapp", ("whatsapp",)),
    "zoom": Aplicacion("Zoom", "zoom", "zoom", ("zoom",)),
    "vlc": Aplicacion("VLC", "vlc", "vlc", ("vlc", "reproductor vlc")),
    "code": Aplicacion("Visual Studio Code", "visual studio code", "visual studio code", ("visual studio code", "vscode", "vs code", "code")),
}


def buscar_app(texto):
    t = texto.strip()
    for clave, app in CATALOGO.items():
        if t in app.alias:
            return clave
    for clave, app in CATALOGO.items():
        for alias in app.alias:
            if len(alias) > 4 and (t.startswith(alias + " ") or t.endswith(" " + alias)):
                return clave
    return None
