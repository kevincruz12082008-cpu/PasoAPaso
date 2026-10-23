ETIQUETAS = {
    "win": "⊞ Windows",
    "ctrl": "Ctrl",
    "shift": "Mayús",
    "alt": "Alt",
    "enter": "Enter",
    "esc": "Esc",
    "tab": "Tab",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
    "space": "Espacio",
    "volumeup": "Subir volumen",
    "volumedown": "Bajar volumen",
    "volumemute": "Silencio",
}


def etiqueta(tecla):
    return ETIQUETAS.get(tecla, tecla.upper())
