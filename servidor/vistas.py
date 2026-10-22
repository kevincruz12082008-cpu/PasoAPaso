"""Vistas HTML del servidor.

Las plantillas son archivos .html con marcadores {{nombre}}. Aquí se
arman los fragmentos dinámicos (tablas, tarjetas, paginación) y se
escapa todo lo que escribe el usuario.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode

from . import base_datos, config

TIPOS_ACCION = {
    "abrir_app": "Abrir un programa",
    "crear_carpeta": "Crear una carpeta",
    "abrir_carpeta": "Abrir una carpeta",
    "abrir_ultima": "Abrir la última carpeta",
    "captura": "Tomar una captura",
    "buscar_web": "Buscar en internet",
    "youtube": "Usar YouTube",
    "sitio": "Abrir una página",
    "volumen": "Cambiar el volumen",
    "escritorio": "Mostrar el escritorio",
    "cerrar_ventana": "Cerrar una ventana",
    "escribir": "Escribir un texto",
    "desconocido": "No entendida",
}

ESTADOS = {
    "pendiente": ("Pendiente", "ambar"),
    "completado": ("Completado", "verde"),
    "detenido": ("Detenido", "gris"),
    "error": ("Error", "rojo"),
    "sin_entender": ("No entendida", "naranja"),
}

ORIGENES = {
    "texto": ("Texto", "azul"),
    "voz": ("Voz", "violeta"),
    "voz_web": ("Voz web", "violeta"),
    "offline": ("Sin conexión", "gris"),
}

_CACHE: dict[str, str] = {}


def escapar(valor) -> str:
    return html.escape(str(valor if valor is not None else ""), quote=True)


def _plantilla(nombre: str) -> str:
    if nombre not in _CACHE:
        ruta = config.DIR_PLANTILLAS / f"{nombre}.html"
        _CACHE[nombre] = ruta.read_text(encoding="utf-8")
    return _CACHE[nombre]


_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render(plantilla: str, **contexto) -> str:
    texto = _plantilla(plantilla)
    # Una sola pasada: lo que se inserta (por ejemplo, un prompt del usuario)
    # no se vuelve a interpretar como plantilla.
    return _PLACEHOLDER.sub(
        lambda coincidencia: str(contexto.get(coincidencia.group(1), coincidencia.group(0))),
        texto,
    )


def fecha(iso: str, formato: str = "%d/%m/%Y %H:%M") -> str:
    return base_datos.fecha_local(iso, formato)


def fecha_corta(iso: str) -> str:
    return fecha(iso, "%d/%m %H:%M")


def iniciales(nombre: str) -> str:
    partes = [p for p in (nombre or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def avatar(nombre: str, clase: str = "") -> str:
    return f'<span class="avatar {clase}">{escapar(iniciales(nombre))}</span>'


def insignia_estado(estado: str) -> str:
    etiqueta, color = ESTADOS.get(estado, (estado or "—", "gris"))
    return f'<span class="chip chip-{color}">{escapar(etiqueta)}</span>'


def insignia_origen(origen: str) -> str:
    etiqueta, color = ORIGENES.get(origen, (origen or "—", "gris"))
    return f'<span class="chip chip-{color}">{escapar(etiqueta)}</span>'


def insignia_ia(usada) -> str:
    if int(usada or 0):
        return '<span class="chip chip-ia" title="Interpretado con Gemini">✦ IA</span>'
    return '<span class="chip chip-gris" title="Interpretado con las reglas locales">Reglas</span>'


def insignia_experiencia(valor: str) -> str:
    return escapar(config.EXPERIENCIAS.get(valor or "", "Sin dato"))


def csrf_input(token: str) -> str:
    return f'<input type="hidden" name="_csrf" value="{escapar(token)}">'


def aviso(mensaje: str = "", tipo: str = "info") -> str:
    if not mensaje:
        return ""
    return f'<div class="aviso aviso-{escapar(tipo)}" role="status">{escapar(mensaje)}</div>'


def layout(
    titulo: str,
    contenido: str,
    *,
    nav: str = "",
    aviso_html: str = "",
    clase_cuerpo: str = "",
    scripts: str = "",
) -> str:
    return render(
        "base",
        titulo=escapar(titulo),
        contenido=contenido,
        nav=nav,
        aviso=aviso_html,
        clase_cuerpo=escapar(clase_cuerpo),
        version=config.VERSION,
        anio=datetime.now().year,
        scripts=scripts,
    )


def layout_admin(
    titulo: str,
    contenido: str,
    *,
    admin: dict,
    nav: str,
    aviso_html: str = "",
    clase_cuerpo: str = "admin",
) -> str:
    return render(
        "admin_base",
        titulo=escapar(titulo),
        contenido=contenido,
        admin_nombre=escapar(admin.get("nombre", "Administrador")),
        admin_iniciales=escapar(iniciales(admin.get("nombre", ""))),
        nav=nav,
        aviso=aviso_html,
        clase_cuerpo=escapar(clase_cuerpo),
        version=config.VERSION,
        anio=datetime.now().year,
    )


def nav_usuario(usuario: Optional[dict], csrf: str) -> str:
    if not usuario:
        return (
            '<a class="nav-enlace" href="/entrar">Entrar</a>'
            '<a class="boton boton-primario boton-pequeno" href="/registro">Crear cuenta</a>'
        )
    nombre = escapar(usuario.get("nombre", "").split()[0] if usuario.get("nombre") else "Mi cuenta")
    return f"""
      <a class="nav-enlace" href="/portal">Mi cuenta</a>
      <a class="nav-enlace" href="/soporte">Ayuda</a>
      <span class="nav-usuario">{avatar(usuario.get('nombre',''))} <span>{nombre}</span></span>
      <form method="post" action="/salir" class="en-linea">
        {csrf_input(csrf)}
        <button class="boton boton-suave boton-pequeno" type="submit">Salir</button>
      </form>
    """


def nav_admin(activo: str, csrf: str) -> str:
    enlaces = [
        ("panel", "/admin", "Resumen", "▦"),
        ("usuarios", "/admin/usuarios", "Usuarios", "☺"),
        ("prompts", "/admin/prompts", "Consultas", "✎"),
        ("ia", "/admin/ia", "Inteligencia artificial", "✦"),
        ("clave", "/admin/clave", "Mi clave", "⚿"),
    ]
    piezas = []
    for clave, url, texto, icono in enlaces:
        clase = "nav-admin-enlace activo" if clave == activo else "nav-admin-enlace"
        piezas.append(
            f'<a class="{clase}" href="{url}"><span class="nav-icono">{icono}</span>{escapar(texto)}</a>'
        )
    piezas.append(
        f"""<form method="post" action="/admin/salir" class="nav-salir">
              {csrf_input(csrf)}
              <button type="submit" class="nav-admin-enlace boton-enlace">↩ Cerrar sesión</button>
            </form>"""
    )
    return "\n".join(piezas)


def pagina_error(codigo: int, mensaje: str) -> str:
    return render(
        "error",
        codigo=str(codigo),
        mensaje=escapar(mensaje),
        version=config.VERSION,
        anio=datetime.now().year,
    )


def paginacion(pagina: int, paginas: int, ruta: str, params: Optional[dict] = None) -> str:
    if paginas <= 1:
        return ""
    params = {k: v for k, v in (params or {}).items() if v not in ("", None)}
    piezas = ['<nav class="paginacion" aria-label="Páginas">']
    if pagina > 1:
        p = dict(params, pagina=pagina - 1)
        piezas.append(f'<a class="pagina" href="{ruta}?{urlencode(p)}">← Anterior</a>')
    else:
        piezas.append('<span class="pagina deshabilitada">← Anterior</span>')
    piezas.append(f'<span class="pagina-info">Página {pagina} de {paginas}</span>')
    if pagina < paginas:
        p = dict(params, pagina=pagina + 1)
        piezas.append(f'<a class="pagina" href="{ruta}?{urlencode(p)}">Siguiente →</a>')
    else:
        piezas.append('<span class="pagina deshabilitada">Siguiente →</span>')
    piezas.append("</nav>")
    return "\n".join(piezas)


def tarjeta_stat(valor, etiqueta: str, detalle: str = "", color: str = "teal") -> str:
    return f"""
    <div class="tarjeta-stat tarjeta-stat-{escapar(color)}">
      <span class="stat-valor">{escapar(valor)}</span>
      <span class="stat-etiqueta">{escapar(etiqueta)}</span>
      <span class="stat-detalle">{escapar(detalle)}</span>
    </div>"""


def grafico(serie: Iterable[dict], maximo: int) -> str:
    barras = []
    for punto in serie:
        n = int(punto.get("n", 0))
        altura = max(3, round(n * 100 / max(1, maximo)))
        barras.append(
            f"""<div class="grafico-columna" title="{n} consultas">
                  <span class="grafico-numero">{n}</span>
                  <div class="grafico-barra" style="height:{altura}%"></div>
                  <span class="grafico-fecha">{escapar(punto.get('etiqueta',''))}</span>
                </div>"""
        )
    return '<div class="grafico">' + "".join(barras) + "</div>"


def lista_ordenes(ordenes: Iterable[dict]) -> str:
    piezas = []
    for orden in ordenes or []:
        if not isinstance(orden, dict):
            continue
        tipo = str(orden.get("tipo", ""))
        datos = orden.get("datos") or {}
        filas = "".join(
            f'<span class="dato-clave">{escapar(k)}</span> <span class="dato-valor">{escapar(v)}</span>'
            for k, v in datos.items()
        )
        piezas.append(
            f"""<li class="orden">
                  <div class="orden-cabecera">
                    <span class="orden-tipo">{escapar(TIPOS_ACCION.get(tipo, tipo))}</span>
                    <code class="orden-id">{escapar(tipo)}</code>
                  </div>
                  <p class="orden-resumen">{escapar(orden.get('resumen',''))}</p>
                  <p class="orden-datos">{filas or '<span class="dato-vacio">Sin datos</span>'}</p>
                </li>"""
        )
    if not piezas:
        return '<p class="vacio">No hay acciones registradas.</p>'
    return '<ul class="lista-ordenes">' + "".join(piezas) + "</ul>"


def json_bonito(datos) -> str:
    try:
        return json.dumps(datos, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(datos)


def tabla_vacia(mensaje: str, columnas: int) -> str:
    return f'<tr><td colspan="{columnas}" class="tabla-vacia">{escapar(mensaje)}</td></tr>'


def texto_truncado(texto: str, maximo: int = 90) -> str:
    texto = (texto or "").strip().replace("\n", " ")
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


def enlace_ayuda() -> str:
    return '<a href="/soporte">Centro de ayuda</a>'
