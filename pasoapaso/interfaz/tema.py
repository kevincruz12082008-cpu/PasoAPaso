FONDO = "#FFF7EC"
FONDO_SUAVE = "#FFF3E2"
TARJETA = "#FFFFFF"
TARJETA_SUAVE = "#FFFDF8"
TEXTO = "#17302E"
SUAVE = "#5C6B69"
ACENTO = "#0F766E"
ACENTO_OSCURO = "#0B5D57"
ACENTO_CLARO = "#CCFBF1"
ACENTO_MUY_CLARO = "#E8FAF6"
BORDE = "#E7DCCB"
BORDE_FUERTE = "#D8C9B4"
TECLA = "#F1F5F9"
BORDE_TECLA = "#94A3B8"
OK = "#15803D"
OK_CLARO = "#DCFCE7"
AVISO = "#B45309"
AVISO_CLARO = "#FEF3C7"
PELIGRO = "#B91C1C"
PELIGRO_CLARO = "#FEE2E2"
VOZ = "#EA580C"
VOZ_OSCURO = "#C2410C"
VOZ_CLARO = "#FFEDD5"
PROGRESO_FONDO = "#D5EFEA"
INFO = "#2563EB"
INFO_CLARO = "#DBEAFE"

FUENTE_MONO = ("Consolas", 12)
FUENTE_EMOJI = ("Segoe UI Emoji", 34)

FACTOR = 1.0


def iniciar(raiz):
    global FACTOR
    FACTOR = max(1.0, raiz.winfo_fpixels("1i") / 96.0)


def px(valor):
    return int(valor * FACTOR)


def fuente(tamano, peso="normal"):
    return ("Segoe UI", tamano, peso)
