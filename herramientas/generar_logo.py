"""Genera el logo de PasoAPaso y sus versiones para la app y la web.

Uso:
    python herramientas/generar_logo.py

No necesita internet. Solo usa Pillow (ya viene en requirements.txt).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
RECURSOS = RAIZ / "recursos"

TEAL_ARRIBA = (20, 184, 166)
TEAL_ABAJO = (13, 100, 95)
CREMA = (255, 247, 236)
BLANCO = (255, 255, 255)
CORAL = (249, 115, 22)
CORAL_CLARO = (253, 186, 116)
SOMBRA = (6, 78, 74)


def _degradado(ancho: int, alto: int, arriba, abajo) -> Image.Image:
    imagen = Image.new("RGB", (ancho, alto))
    dibujo = ImageDraw.Draw(imagen)
    for y in range(alto):
        t = y / max(1, alto - 1)
        color = tuple(round(arriba[i] * (1 - t) + abajo[i] * t) for i in range(3))
        dibujo.line([(0, y), (ancho, y)], fill=color)
    return imagen


def _rect_redondeado(dibujo, caja, radio, relleno, contorno=None, grosor=0):
    dibujo.rounded_rectangle(caja, radius=radio, fill=relleno, outline=contorno, width=grosor)


def crear_icono(lado: int = 1024) -> Image.Image:
    """Crea el icono cuadrado con fondo transparente."""
    escala = lado / 1024
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))

    # Fondo redondeado con degradado y una sombra suave.
    fondo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    gradiente = _degradado(lado, lado, TEAL_ARRIBA, TEAL_ABAJO).convert("RGBA")
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        (28 * escala, 28 * escala, (1024 - 28) * escala, (1024 - 28) * escala),
        radius=230 * escala,
        fill=255,
    )
    fondo.paste(gradiente, (0, 0), mascara)

    sombra = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle(
        (44 * escala, 56 * escala, (1024 - 44) * escala, (1024 - 44) * escala),
        radius=230 * escala,
        fill=SOMBRA + (90,),
    )
    sombra = sombra.filter(ImageFilter.GaussianBlur(26 * escala))
    lienzo.alpha_composite(sombra)
    lienzo.alpha_composite(fondo)

    dibujo = ImageDraw.Draw(lienzo)

    # Brillo diagonal sutil.
    brillo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).polygon(
        [
            (70 * escala, 70 * escala),
            (520 * escala, 70 * escala),
            (250 * escala, 420 * escala),
            (70 * escala, 500 * escala),
        ],
        fill=(255, 255, 255, 22),
    )
    mascara_brillo = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara_brillo).rounded_rectangle(
        (28 * escala, 28 * escala, (1024 - 28) * escala, (1024 - 28) * escala),
        radius=230 * escala,
        fill=255,
    )
    recorte = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    recorte.paste(brillo, (0, 0), mascara_brillo)
    lienzo.alpha_composite(recorte)

    # Escalera: tres bloques que suben de izquierda a derecha.
    base_y = 842 * escala
    bloques = (
        (196, 674, 402, 842, 44),
        (356, 522, 562, 842, 44),
        (516, 370, 722, 842, 44),
    )
    for x1, y1, x2, y2, radio in bloques:
        # Sombra de cada bloque.
        sombra_bloque = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(sombra_bloque).rounded_rectangle(
            ((x1 + 8) * escala, (y1 + 14) * escala, (x2 + 8) * escala, (y2 + 14) * escala),
            radius=radio * escala,
            fill=(5, 60, 57, 80),
        )
        sombra_bloque = sombra_bloque.filter(ImageFilter.GaussianBlur(12 * escala))
        lienzo.alpha_composite(sombra_bloque)

    for indice, (x1, y1, x2, y2, radio) in enumerate(bloques):
        color = (255, 255, 255) if indice == 2 else (240, 253, 250) if indice == 1 else (204, 251, 241)
        _rect_redondeado(
            dibujo,
            (x1 * escala, y1 * escala, x2 * escala, y2 * escala),
            radio * escala,
            color,
        )
        # Línea interior para dar volumen.
        dibujo.rounded_rectangle(
            ((x1 + 12) * escala, (y1 + 12) * escala, (x2 - 12) * escala, (y2 - 12) * escala),
            radius=(radio - 10) * escala,
            outline=(255, 255, 255, 70),
            width=max(1, round(3 * escala)),
        )

    # Punto coral: la meta a la que se llega paso a paso.
    cx, cy, r = 820 * escala, 246 * escala, 74 * escala
    dibujo.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CORAL)
    dibujo.ellipse(
        (cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62),
        fill=CORAL_CLARO,
    )
    # Brillo del punto.
    dibujo.ellipse(
        (cx - r * 0.30, cy - r * 0.48, cx + r * 0.10, cy - r * 0.10),
        fill=(255, 255, 255, 170),
    )

    # Tres puntitos que marcan el camino.
    for i, (px, py) in enumerate(((220, 566), (302, 470), (386, 374))):
        radio_punto = (11 - i * 1.5) * escala
        dibujo.ellipse(
            (px * escala - radio_punto, py * escala - radio_punto,
             px * escala + radio_punto, py * escala + radio_punto),
            fill=(204, 251, 241, 190 - i * 25),
        )

    return lienzo


def crear_svg() -> str:
    """Versión vectorial sencilla para la web."""
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img" aria-label="PasoAPaso">
  <defs>
    <linearGradient id="fondo" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#14B8A6"/>
      <stop offset="1" stop-color="#0D645F"/>
    </linearGradient>
    <filter id="sombra" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#064E4A" flood-opacity="0.35"/>
    </filter>
  </defs>
  <rect x="28" y="28" width="968" height="968" rx="230" fill="url(#fondo)" filter="url(#sombra)"/>
  <path d="M70 70 H520 L250 420 L70 500 Z" fill="#FFFFFF" opacity="0.08"/>
  <g>
    <rect x="196" y="674" width="206" height="168" rx="44" fill="#CCFBF1"/>
    <rect x="356" y="522" width="206" height="320" rx="44" fill="#F0FDFA"/>
    <rect x="516" y="370" width="206" height="472" rx="44" fill="#FFFFFF"/>
  </g>
  <circle cx="820" cy="246" r="74" fill="#F97316"/>
  <circle cx="820" cy="246" r="46" fill="#FDBA74"/>
  <circle cx="802" cy="228" r="16" fill="#FFFFFF" opacity="0.75"/>
  <g fill="#CCFBF1">
    <circle cx="220" cy="566" r="11"/>
    <circle cx="302" cy="470" r="9.5"/>
    <circle cx="386" cy="374" r="8"/>
  </g>
</svg>
"""


def main() -> None:
    RECURSOS.mkdir(parents=True, exist_ok=True)
    icono = crear_icono(1024)
    icono.save(RECURSOS / "logo.png", optimize=True)
    for lado in (512, 256, 128, 64):
        icono.resize((lado, lado), Image.LANCZOS).save(
            RECURSOS / f"logo_{lado}.png", optimize=True
        )
    icono.resize((256, 256), Image.LANCZOS).save(
        RECURSOS / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    (RECURSOS / "logo.svg").write_text(crear_svg(), encoding="utf-8")

    # Versión horizontal para documentos y presentaciones.
    horizontal = Image.new("RGBA", (1500, 420), (0, 0, 0, 0))
    horizontal.alpha_composite(icono.resize((360, 360), Image.LANCZOS), (30, 30))
    dibujo = ImageDraw.Draw(horizontal)
    try:
        fuente = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 104)
        fuente_pequena = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 30)
    except OSError:
        fuente = ImageFont.load_default()
        fuente_pequena = ImageFont.load_default()
    dibujo.text((430, 90), "PasoAPaso", font=fuente, fill=(15, 118, 110))
    dibujo.text(
        (434, 232),
        "Tu ayudante para aprender a usar la computadora",
        font=fuente_pequena,
        fill=(100, 116, 139),
    )
    horizontal.save(RECURSOS / "logo_horizontal.png", optimize=True)

    print(f"Listo. Imágenes generadas en {RECURSOS}")


if __name__ == "__main__":
    from PIL import ImageFont

    main()
