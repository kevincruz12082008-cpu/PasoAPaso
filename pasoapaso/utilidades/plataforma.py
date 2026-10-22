import ctypes
import socket
import sys


def es_windows():
    return sys.platform.startswith("win")


def idioma_es():
    if not es_windows():
        return True
    try:
        return (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF) == 0x0A
    except Exception:
        return True


def carpeta_conocida(csidl):
    memoria = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, memoria)
    return memoria.value


def activar_nitidez():
    if not es_windows():
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def evitar_foco(ventana):
    if not es_windows():
        return
    try:
        ventana.update_idletasks()
        identificador = ctypes.windll.user32.GetParent(ventana.winfo_id())
        estilo = ctypes.windll.user32.GetWindowLongW(identificador, -20)
        ctypes.windll.user32.SetWindowLongW(
            identificador, -20, estilo | 0x08000000 | 0x00000080
        )
    except Exception:
        pass


def hay_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
        return True
    except OSError:
        return False
