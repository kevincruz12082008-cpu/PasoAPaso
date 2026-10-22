"""Rutas del servidor: portal, API y panel de administración."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import base_datos, config, ia, seguridad, vistas
from .servidor import (
    ErrorHTTP,
    Peticion,
    Respuesta,
    csrf_token,
    csrf_valido,
    solo_admin,
    solo_usuario,
)

RUTAS: list[tuple[str, re.Pattern, object]] = []
LIMITADOR_LOGIN = seguridad.Limitador(config.MAX_INTENTOS_LOGIN, config.VENTANA_INTENTOS)
LIMITADOR_REGISTRO = seguridad.Limitador(50, 3600)

SUGERENCIAS = (
    "abre la calculadora y el bloc de notas",
    "crea una carpeta llamada Tareas en el escritorio",
    "toma una captura de pantalla",
    "busca recetas de pupusas en google",
    "reproduce música de Juan Gabriel en youtube",
)


def ruta(metodo: str, patron: str):
    def registrar(funcion):
        RUTAS.append((metodo, re.compile(patron), funcion))
        return funcion

    registrar._patron = patron
    return registrar


# --- Utilidades -------------------------------------------------------------

def _telefono_bonito(telefono: str) -> str:
    telefono = seguridad.normalizar_telefono(telefono)
    if len(telefono) == 8:
        return f"{telefono[:4]}-{telefono[4:]}"
    if len(telefono) == 11 and telefono.startswith("504"):
        return f"+504 {telefono[3:7]}-{telefono[7:]}"
    return ("+" + telefono) if len(telefono) > 8 else telefono


def _usuario_api(usuario: dict) -> dict:
    publico = base_datos.usuario_publico(usuario) or {}
    return {
        "id": publico.get("id"),
        "telefono": publico.get("telefono"),
        "telefono_bonito": _telefono_bonito(publico.get("telefono", "")),
        "nombre": publico.get("nombre"),
        "edad": publico.get("edad"),
        "ciudad": publico.get("ciudad"),
        "experiencia": publico.get("experiencia"),
        "experiencia_texto": config.EXPERIENCIAS.get(publico.get("experiencia", ""), ""),
        "creado_en": publico.get("creado_en"),
        "ultimo_acceso": publico.get("ultimo_acceso"),
    }


def _orden_dict(orden) -> dict:
    return {
        "tipo": getattr(orden, "tipo", ""),
        "datos": getattr(orden, "datos", {}) or {},
        "resumen": getattr(orden, "resumen", ""),
        "texto": getattr(orden, "texto", ""),
    }


def _prompt_api(prompt: dict) -> dict:
    return {
        "id": prompt.get("id"),
        "texto": prompt.get("texto"),
        "origen": prompt.get("origen"),
        "estado": prompt.get("estado"),
        "ia_usada": bool(prompt.get("ia_usada")),
        "ia_modelo": prompt.get("ia_modelo"),
        "fecha": prompt.get("fecha"),
        "fecha_corta": prompt.get("fecha_corta"),
        "error": prompt.get("error"),
        "duracion_ms": prompt.get("duracion_ms"),
        "acciones": prompt.get("acciones") or [],
        "ordenes": [
            {
                "tipo": o.get("tipo", ""),
                "datos": o.get("datos", {}),
                "resumen": o.get("resumen", ""),
            }
            for o in (prompt.get("intencion") or [])
            if isinstance(o, dict)
        ],
        "feedback": prompt.get("feedback"),
    }


def _query_redireccion(url: str, mensaje: str = "", tipo: str = "aviso") -> str:
    if not mensaje:
        return url
    clave = "aviso" if tipo == "aviso" else "error"
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}{clave}={urllib.parse.quote(mensaje)}"


def _mensajes(peticion: Peticion) -> str:
    partes = []
    aviso = peticion.dato("aviso")
    error = peticion.dato("error")
    if aviso:
        partes.append(vistas.aviso(aviso, "ok"))
    if error:
        partes.append(vistas.aviso(error, "error"))
    return "".join(partes)


def _pagina(peticion: Peticion) -> int:
    return max(1, peticion.entero("pagina", 1))


def _next_seguro(valor: str) -> str:
    if valor and valor.startswith("/") and not valor.startswith("//") and "\\" not in valor:
        return valor
    return "/portal"


def _clave_limite(peticion: Peticion, extra: str = "") -> str:
    return f"{peticion.ip}|{extra}"


def _validar_registro(datos: dict) -> tuple[dict, str]:
    telefono = seguridad.normalizar_telefono(datos.get("telefono"))
    nombre = seguridad.limpiar_nombre(datos.get("nombre"), config.MAX_NOMBRE)
    pin = seguridad.normalizar_pin(datos.get("clave"))
    pin2 = seguridad.normalizar_pin(datos.get("clave2"))
    ciudad = seguridad.limpiar_nombre(datos.get("ciudad"), config.MAX_CIUDAD)
    experiencia = seguridad.normalizar_experiencia(datos.get("experiencia"))
    como = seguridad.limpiar_texto(datos.get("como_nos_conocio"), 120)
    consentimiento_crudo = datos.get("consentimiento")
    if isinstance(consentimiento_crudo, str):
        consentimiento = consentimiento_crudo.strip().lower() in ("1", "true", "on", "si", "sí")
    else:
        consentimiento = bool(consentimiento_crudo)
    edad_texto = str(datos.get("edad") or "").strip()

    if len(nombre) < 2:
        return {}, "Escribe tu nombre completo (al menos 2 letras)."
    if not seguridad.telefono_valido(telefono):
        return {}, "Escribe un número de teléfono válido, con 8 a 15 números."
    if not seguridad.pin_valido(pin):
        return {}, "La clave debe tener entre 4 y 8 números."
    if pin != pin2:
        return {}, "Las dos claves no son iguales. Vuelve a escribirla."
    if not consentimiento:
        return {}, "Marca la casilla para que podamos guardar tus datos y ayudarte."
    edad = None
    if edad_texto:
        try:
            edad = int(edad_texto)
        except ValueError:
            return {}, "La edad debe ser un número."
        if not 5 <= edad <= 120:
            return {}, "La edad debe estar entre 5 y 120 años."
    return {
        "telefono": telefono,
        "nombre": nombre,
        "clave": pin,
        "edad": edad,
        "ciudad": ciudad,
        "experiencia": experiencia,
        "como_nos_conocio": como,
        "consentimiento": True,
    }, ""


def _crear_sesion_usuario(peticion: Peticion, usuario: dict) -> None:
    token = seguridad.token_usuario(int(usuario["id"]), int(usuario.get("token_version", 0)))
    peticion.poner_cookie(
        "pa_sesion", token, config.SESION_HORAS * 3600, http_only=True
    )


def _crear_sesion_admin(peticion: Peticion, admin: dict) -> None:
    token = seguridad.token_admin(int(admin["id"]), int(admin.get("token_version", 0)))
    peticion.poner_cookie(
        "pa_admin", token, config.ADMIN_SESION_HORAS * 3600, http_only=True
    )


def _filas_prompt(prompts, admin: bool = False) -> str:
    piezas = []
    for prompt in prompts:
        destino = (
            f"/admin/prompts/{prompt['id']}" if admin else f"/portal/consulta/{prompt['id']}"
        )
        piezas.append(
            f"""<tr>
              <td><a class="enlace-fuerte" href="{destino}">{vistas.escapar(vistas.texto_truncado(prompt.get('texto',''), 90))}</a></td>
              <td>{vistas.insignia_origen(prompt.get('origen',''))}</td>
              <td>{vistas.insignia_estado(prompt.get('estado',''))}</td>
              <td>{vistas.insignia_ia(prompt.get('ia_usada', 0))}</td>
              <td class="columna-fecha">{vistas.escapar(prompt.get('fecha_corta',''))}</td>
            </tr>"""
        )
    return "".join(piezas) or vistas.tabla_vacia("Todavía no hay consultas.", 5)


# --- Salud y páginas públicas ----------------------------------------------

@ruta("GET", r"/salud")
@ruta("GET", r"/api/estado")
def salud(peticion: Peticion) -> Respuesta:
    return Respuesta.json(
        {
            "ok": True,
            "app": config.NOMBRE_APP,
            "version": config.VERSION,
            "ia_configurada": bool(config.GEMINI_API_KEY),
            "ia_activa": base_datos.ia_activa(),
            "registro_abierto": base_datos.registro_abierto(),
            "hora": base_datos.ahora_utc(),
        }
    )


@ruta("GET", r"/")
def portada(peticion: Peticion) -> Respuesta:
    if peticion.usuario:
        return Respuesta.redirigir("/portal")
    csrf = csrf_token(peticion)
    contenido = vistas.render(
        "inicio",
        csrf=vistas.csrf_input(csrf),
        mensajes=_mensajes(peticion),
        telefono=vistas.escapar(peticion.dato("telefono")),
        registro_abierto="sí" if base_datos.registro_abierto() else "no",
    )
    return Respuesta.html(
        vistas.layout(
            "Aprende a usar la computadora",
            contenido,
            nav=vistas.nav_usuario(None, csrf),
        )
    )


def _vista_entrar(peticion: Peticion, error: str = "", aviso: str = "") -> Respuesta:
    csrf = csrf_token(peticion)
    contenido = vistas.render(
        "entrar",
        csrf=vistas.csrf_input(csrf),
        error=vistas.aviso(error, "error"),
        aviso=vistas.aviso(aviso, "ok"),
        telefono=vistas.escapar(peticion.dato("telefono")),
        next=vistas.escapar(peticion.dato("next")),
    )
    return Respuesta.html(
        vistas.layout("Entrar", contenido, nav=vistas.nav_usuario(None, csrf))
    )


@ruta("GET", r"/entrar")
def entrar_form(peticion: Peticion) -> Respuesta:
    if peticion.usuario:
        return Respuesta.redirigir("/portal")
    return _vista_entrar(peticion, aviso=peticion.dato("aviso"))


@ruta("POST", r"/entrar")
def entrar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    telefono = seguridad.normalizar_telefono(peticion.dato("telefono"))
    pin = seguridad.normalizar_pin(peticion.dato("clave"))
    siguiente = _next_seguro(peticion.dato("next"))
    if not seguridad.telefono_valido(telefono) or not seguridad.pin_valido(pin):
        return _vista_entrar(peticion, error="Escribe tu teléfono y tu clave de 4 a 8 números.")
    clave_limite = _clave_limite(peticion, telefono)
    if not LIMITADOR_LOGIN.permitido(clave_limite):
        return _vista_entrar(
            peticion,
            error="Demasiados intentos seguidos. Espera unos minutos y vuelve a probar.",
        )
    usuario = base_datos.obtener_usuario_por_telefono(telefono)
    if not usuario or not seguridad.verificar_clave(pin, usuario.get("clave_hash", "")):
        LIMITADOR_LOGIN.fallo(clave_limite)
        return _vista_entrar(peticion, error="El teléfono o la clave no son correctos.")
    if not int(usuario.get("activo", 0)):
        return _vista_entrar(
            peticion,
            error="Tu cuenta está desactivada. Habla con el administrador de PasoAPaso.",
        )
    LIMITADOR_LOGIN.limpiar(clave_limite)
    base_datos.registrar_acceso(int(usuario["id"]))
    _crear_sesion_usuario(peticion, usuario)
    return Respuesta.redirigir(siguiente)


@ruta("GET", r"/registro")
def registro_form(peticion: Peticion) -> Respuesta:
    if peticion.usuario:
        return Respuesta.redirigir("/portal")
    return _vista_registro(peticion)


def _vista_registro(peticion: Peticion, error: str = "", datos: dict | None = None) -> Respuesta:
    csrf = csrf_token(peticion)
    datos = datos or {}
    experiencia = datos.get("experiencia") or peticion.dato("experiencia") or "poco"
    opciones = "".join(
        f'<option value="{vistas.escapar(clave)}"'
        f'{" selected" if experiencia == clave else ""}>'
        f"{vistas.escapar(texto)}</option>"
        for clave, texto in config.EXPERIENCIAS.items()
    )
    contenido = vistas.render(
        "registro",
        csrf=vistas.csrf_input(csrf),
        error=vistas.aviso(error, "error"),
        opciones_experiencia=opciones,
        abierto="1" if base_datos.registro_abierto() else "0",
        telefono=vistas.escapar(datos.get("telefono") or peticion.dato("telefono")),
        nombre=vistas.escapar(datos.get("nombre") or ""),
        edad=vistas.escapar(datos.get("edad") or ""),
        ciudad=vistas.escapar(datos.get("ciudad") or ""),
        como=vistas.escapar(datos.get("como_nos_conocio") or ""),
        consentimiento="checked" if datos.get("consentimiento") else "",
    )
    return Respuesta.html(
        vistas.layout("Crear cuenta", contenido, nav=vistas.nav_usuario(None, csrf))
    )


@ruta("POST", r"/registro")
def registro(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    datos_formulario = {
        "telefono": peticion.dato("telefono"),
        "nombre": peticion.dato("nombre"),
        "clave": peticion.dato("clave"),
        "clave2": peticion.dato("clave2"),
        "edad": peticion.dato("edad"),
        "ciudad": peticion.dato("ciudad"),
        "experiencia": peticion.dato("experiencia"),
        "como_nos_conocio": peticion.dato("como_nos_conocio"),
        "consentimiento": peticion.dato("consentimiento") == "1",
    }
    if not base_datos.registro_abierto():
        return _vista_registro(peticion, error="El registro está cerrado por ahora.", datos=datos_formulario)
    if not LIMITADOR_REGISTRO.permitido(peticion.ip):
        return _vista_registro(
            peticion,
            error="Se hicieron muchos registros desde esta conexión. Intenta más tarde.",
            datos=datos_formulario,
        )
    LIMITADOR_REGISTRO.fallo(peticion.ip)
    datos, error = _validar_registro(datos_formulario)
    if error:
        return _vista_registro(peticion, error=error, datos=datos_formulario)
    if base_datos.obtener_usuario_por_telefono(datos["telefono"]):
        return _vista_registro(
            peticion, error="Ese teléfono ya tiene una cuenta. Entra con tu clave.", datos=datos_formulario
        )
    try:
        base_datos.crear_usuario(
            datos["telefono"],
            datos["nombre"],
            datos["clave"],
            datos["edad"],
            datos["ciudad"],
            datos["experiencia"],
            datos["como_nos_conocio"],
            True,
        )
    except sqlite3.IntegrityError:
        return _vista_registro(peticion, error="Ese teléfono ya tiene una cuenta.", datos=datos_formulario)
    usuario = base_datos.obtener_usuario_por_telefono(datos["telefono"])
    if usuario:
        _crear_sesion_usuario(peticion, usuario)
    return Respuesta.redirigir("/portal?aviso=" + urllib.parse.quote("¡Bienvenido a PasoAPaso!"))


@ruta("POST", r"/salir")
def salir(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    peticion.borrar_cookie("pa_sesion")
    return Respuesta.redirigir("/")


# --- Portal del usuario -----------------------------------------------------

@ruta("GET", r"/portal")
@solo_usuario
def portal(peticion: Peticion) -> Respuesta:
    return _vista_portal(peticion)


def _vista_portal(peticion: Peticion, error: str = "", aviso: str = "") -> Respuesta:
    usuario = peticion.usuario or {}
    csrf = csrf_token(peticion)
    historial = base_datos.historial_usuario(int(usuario["id"]), 20)
    total = base_datos.listar_prompts(usuario_id=int(usuario["id"]), por_pagina=1)["total"]
    filas = _filas_prompt(historial)
    contenido = vistas.render(
        "portal",
        csrf=vistas.csrf_input(csrf),
        nombre=vistas.escapar(usuario.get("nombre", "")),
        iniciales=vistas.escapar(vistas.iniciales(usuario.get("nombre", ""))),
        telefono=vistas.escapar(_telefono_bonito(usuario.get("telefono", ""))),
        ciudad=vistas.escapar(usuario.get("ciudad") or "Sin indicar"),
        experiencia=vistas.insignia_experiencia(usuario.get("experiencia", "")),
        desde=vistas.escapar(vistas.fecha(usuario.get("creado_en", ""), "%d/%m/%Y")),
        total=total,
        filas=filas,
        mensajes=_mensajes(peticion) + vistas.aviso(error, "error") + vistas.aviso(aviso, "ok"),
        boton_descarga=(
            '<a class="boton boton-primario" href="/descargar">⬇ Descargar PasoAPaso</a>'
            if config.RUTA_ZIP.exists()
            else '<a class="boton boton-contorno" href="/soporte/#empezar">Cómo instalar</a>'
        ),
    )
    return Respuesta.html(
        vistas.layout(
            "Mi cuenta",
            contenido,
            nav=vistas.nav_usuario(usuario, csrf),
            clase_cuerpo="portal",
        )
    )


@ruta("GET", r"/portal/consulta/(?P<prompt_id>\d+)")
@solo_usuario
def portal_consulta(peticion: Peticion) -> Respuesta:
    prompt = base_datos.obtener_prompt(int(peticion.params["prompt_id"]))
    if not prompt or int(prompt.get("usuario_id") or 0) != int(peticion.usuario["id"]):
        raise ErrorHTTP(404, "No encontré esa consulta.")
    csrf = csrf_token(peticion)
    feedback = base_datos.feedback_de_prompt(int(prompt["id"]))
    util = feedback.get("util") if feedback else None
    contenido = vistas.render(
        "consulta",
        csrf=vistas.csrf_input(csrf),
        prompt_id=prompt["id"],
        prompt_texto=vistas.escapar(prompt.get("texto", "")),
        fecha=vistas.escapar(prompt.get("fecha", "")),
        origen=vistas.insignia_origen(prompt.get("origen", "")),
        estado=vistas.insignia_estado(prompt.get("estado", "")),
        ia=vistas.insignia_ia(prompt.get("ia_usada", 0)),
        modelo=vistas.escapar(prompt.get("ia_modelo") or "Reglas locales"),
        duracion=vistas.escapar(f"{prompt.get('duracion_ms')} ms" if prompt.get("duracion_ms") else "—"),
        error=vistas.aviso(prompt.get("error") or "", "error"),
        ordenes=vistas.lista_ordenes(prompt.get("intencion") or []),
        feedback=feedback or {},
        checked_si="checked" if util == 1 else "",
        checked_no="checked" if util == 0 else "",
        mensajes=_mensajes(peticion),
    )
    return Respuesta.html(
        vistas.layout(
            "Consulta",
            contenido,
            nav=vistas.nav_usuario(peticion.usuario, csrf),
            clase_cuerpo="portal",
        )
    )


@ruta("POST", r"/portal/feedback")
@solo_usuario
def portal_feedback(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    try:
        prompt_id = int(peticion.dato("prompt_id"))
    except (TypeError, ValueError):
        raise ErrorHTTP(400, "Falta la consulta.")
    prompt = base_datos.obtener_prompt(prompt_id)
    if not prompt or int(prompt.get("usuario_id") or 0) != int(peticion.usuario["id"]):
        raise ErrorHTTP(404, "No encontré esa consulta.")
    util = peticion.dato("util") == "1"
    comentario = seguridad.limpiar_texto(peticion.dato("comentario"), 300)
    base_datos.guardar_feedback(prompt_id, util, comentario)
    return Respuesta.redirigir(
        _query_redireccion(f"/portal/consulta/{prompt_id}", "Gracias por tu respuesta.")
    )


@ruta("POST", r"/portal/clave")
@solo_usuario
def portal_clave(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    actual = seguridad.normalizar_pin(peticion.dato("actual"))
    nueva = seguridad.normalizar_pin(peticion.dato("nueva"))
    repetir = seguridad.normalizar_pin(peticion.dato("repetir"))
    if not seguridad.verificar_clave(actual, peticion.usuario.get("clave_hash", "")):
        return _vista_portal(peticion, error="La clave actual no es correcta.")
    if not seguridad.pin_valido(nueva):
        return _vista_portal(peticion, error="La clave nueva debe tener entre 4 y 8 números.")
    if nueva != repetir:
        return _vista_portal(peticion, error="Las dos claves nuevas no son iguales.")
    base_datos.cambiar_pin(int(peticion.usuario["id"]), nueva)
    usuario = base_datos.obtener_usuario(int(peticion.usuario["id"]))
    if usuario:
        _crear_sesion_usuario(peticion, usuario)
    return Respuesta.redirigir(
        "/portal?aviso=" + urllib.parse.quote("Tu clave se cambió correctamente.")
    )


@ruta("POST", r"/portal/eliminar")
@solo_usuario
def portal_eliminar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    if peticion.dato("confirmar").strip().upper() != "ELIMINAR":
        return _vista_portal(
            peticion, error="Escribe ELIMINAR (en mayúsculas) para confirmar que quieres borrar tu cuenta."
        )
    base_datos.eliminar_usuario(int(peticion.usuario["id"]))
    peticion.borrar_cookie("pa_sesion")
    return Respuesta.redirigir(
        "/?aviso=" + urllib.parse.quote("Tu cuenta y tus consultas fueron eliminadas.")
    )


@ruta("GET", r"/privacidad")
def privacidad(peticion: Peticion) -> Respuesta:
    csrf = csrf_token(peticion)
    contenido = vistas.render("privacidad")
    return Respuesta.html(
        vistas.layout("Privacidad", contenido, nav=vistas.nav_usuario(peticion.usuario, csrf))
    )


@ruta("GET", r"/descargar")
def descargar(peticion: Peticion) -> Respuesta:
    if not config.RUTA_ZIP.exists():
        return Respuesta.redirigir(
            "/portal?error=" + urllib.parse.quote("La descarga todavía no está preparada.")
        )
    return Respuesta.archivo(config.RUTA_ZIP, descargar="PasoAPaso.zip", cache="no-store")


# --- Soporte técnico --------------------------------------------------------

@ruta("GET", r"/soporte")
def soporte_raiz(peticion: Peticion) -> Respuesta:
    return Respuesta.redirigir("/soporte/")


@ruta("GET", r"/soporte/")
def soporte_indice(peticion: Peticion) -> Respuesta:
    return _archivo_soporte("index.html")


@ruta("GET", r"/soporte/(?P<ruta>.+)")
def soporte_archivo(peticion: Peticion) -> Respuesta:
    return _archivo_soporte(peticion.params["ruta"])


def _archivo_soporte(relativa: str) -> Respuesta:
    base = (config.RAIZ / "soporte").resolve()
    if ".." in Path(relativa).parts:
        raise ErrorHTTP(404, "Archivo no encontrado.")
    destino = (base / relativa).resolve()
    try:
        destino.relative_to(base)
    except ValueError as error:
        raise ErrorHTTP(404, "Archivo no encontrado.") from error
    if not destino.is_file():
        raise ErrorHTTP(404, "Archivo no encontrado.")
    return Respuesta.archivo(destino)


# --- API para la app de escritorio -----------------------------------------

@ruta("POST", r"/api/registro")
def api_registro(peticion: Peticion) -> Respuesta:
    if not base_datos.registro_abierto():
        raise ErrorHTTP(403, "El registro está cerrado por ahora.", api=True)
    if not LIMITADOR_REGISTRO.permitido(peticion.ip):
        raise ErrorHTTP(429, "Demasiados registros desde esta conexión.", api=True)
    LIMITADOR_REGISTRO.fallo(peticion.ip)
    datos = peticion.json()
    limpios, error = _validar_registro(datos)
    if error:
        raise ErrorHTTP(400, error, api=True)
    if base_datos.obtener_usuario_por_telefono(limpios["telefono"]):
        raise ErrorHTTP(409, "Ese teléfono ya tiene una cuenta.", api=True)
    try:
        base_datos.crear_usuario(
            limpios["telefono"],
            limpios["nombre"],
            limpios["clave"],
            limpios["edad"],
            limpios["ciudad"],
            limpios["experiencia"],
            limpios["como_nos_conocio"],
            True,
        )
    except sqlite3.IntegrityError as exc:
        raise ErrorHTTP(409, "Ese teléfono ya tiene una cuenta.", api=True) from exc
    usuario = base_datos.obtener_usuario_por_telefono(limpios["telefono"])
    token = seguridad.token_usuario(int(usuario["id"]), int(usuario.get("token_version", 0)))
    base_datos.registrar_acceso(int(usuario["id"]))
    return Respuesta.json(
        {"ok": True, "token": token, "usuario": _usuario_api(usuario)}, 201
    )


@ruta("POST", r"/api/login")
def api_login(peticion: Peticion) -> Respuesta:
    datos = peticion.json()
    telefono = seguridad.normalizar_telefono(datos.get("telefono"))
    pin = seguridad.normalizar_pin(datos.get("clave"))
    if not seguridad.telefono_valido(telefono) or not seguridad.pin_valido(pin):
        raise ErrorHTTP(400, "Escribe un teléfono y una clave válidos.", api=True)
    clave_limite = _clave_limite(peticion, telefono)
    if not LIMITADOR_LOGIN.permitido(clave_limite):
        raise ErrorHTTP(429, "Demasiados intentos. Espera unos minutos.", api=True)
    usuario = base_datos.obtener_usuario_por_telefono(telefono)
    if not usuario or not seguridad.verificar_clave(pin, usuario.get("clave_hash", "")):
        LIMITADOR_LOGIN.fallo(clave_limite)
        raise ErrorHTTP(401, "El teléfono o la clave no son correctos.", api=True)
    if not int(usuario.get("activo", 0)):
        raise ErrorHTTP(403, "Tu cuenta está desactivada. Habla con el administrador.", api=True)
    LIMITADOR_LOGIN.limpiar(clave_limite)
    base_datos.registrar_acceso(int(usuario["id"]))
    token = seguridad.token_usuario(int(usuario["id"]), int(usuario.get("token_version", 0)))
    return Respuesta.json({"ok": True, "token": token, "usuario": _usuario_api(usuario)})


@ruta("GET", r"/api/perfil")
@solo_usuario
def api_perfil(peticion: Peticion) -> Respuesta:
    usuario = peticion.usuario
    total = base_datos.listar_prompts(usuario_id=int(usuario["id"]), por_pagina=1)["total"]
    return Respuesta.json(
        {"ok": True, "usuario": _usuario_api(usuario), "consultas": total}
    )


@ruta("POST", r"/api/interpretar")
@solo_usuario
def api_interpretar(peticion: Peticion) -> Respuesta:
    datos = peticion.json()
    texto = seguridad.limpiar_texto(datos.get("texto"), config.MAX_TEXTO)
    origen = seguridad.normalizar_origen(datos.get("origen"))
    if not texto:
        raise ErrorHTTP(400, "No escribiste ninguna orden.", api=True)
    resultado = ia.resolver(texto)
    validas = [orden for orden in resultado.ordenes if getattr(orden, "tipo", "") != "desconocido"]
    estado = "pendiente" if validas else "sin_entender"
    prompt_id = base_datos.crear_prompt(
        int(peticion.usuario["id"]),
        texto,
        origen,
        estado,
        resultado.ordenes,
        resultado.ia_usada,
        resultado.modelo,
    )
    mensaje = ""
    if not validas:
        mensaje = (
            "No entendí esa orden. Prueba con algo como «abre la calculadora» "
            "o «crea una carpeta llamada Tareas»."
        )
    return Respuesta.json(
        {
            "ok": True,
            "prompt_id": prompt_id,
            "estado": estado,
            "ordenes": [_orden_dict(o) for o in resultado.ordenes],
            "ia_usada": resultado.ia_usada,
            "ia_modelo": resultado.modelo,
            "motivo": resultado.motivo,
            "ia_error": resultado.error,
            "latencia_ms": resultado.latencia_ms,
            "ia_configurada": bool(config.GEMINI_API_KEY),
            "mensaje": mensaje,
            "sugerencias": list(SUGERENCIAS) if not validas else [],
        }
    )


@ruta("POST", r"/api/prompts/(?P<prompt_id>\d+)/resultado")
@solo_usuario
def api_resultado(peticion: Peticion) -> Respuesta:
    datos = peticion.json()
    prompt_id = int(peticion.params["prompt_id"])
    prompt = base_datos.obtener_prompt(prompt_id)
    if not prompt or int(prompt.get("usuario_id") or 0) != int(peticion.usuario["id"]):
        raise ErrorHTTP(404, "No encontré esa consulta.", api=True)
    estado = str(datos.get("estado", "")).strip().lower()
    if estado not in {"completado", "detenido", "error"}:
        raise ErrorHTTP(400, "Estado de resultado no válido.", api=True)
    error = seguridad.limpiar_texto(datos.get("error"), 500)
    try:
        duracion = int(datos.get("duracion_ms") or 0)
    except (TypeError, ValueError):
        duracion = 0
    duracion = max(0, min(duracion, 3_600_000))
    acciones = datos.get("acciones") or []
    if not isinstance(acciones, list):
        acciones = []
    base_datos.actualizar_prompt(
        prompt_id,
        int(peticion.usuario["id"]),
        estado,
        error,
        duracion,
        acciones[:20],
    )
    return Respuesta.json({"ok": True})


@ruta("POST", r"/api/prompts/offline")
@solo_usuario
def api_offline(peticion: Peticion) -> Respuesta:
    datos = peticion.json()
    texto = seguridad.limpiar_texto(datos.get("texto"), config.MAX_TEXTO)
    if not texto:
        raise ErrorHTTP(400, "La consulta está vacía.", api=True)
    origen = seguridad.normalizar_origen(datos.get("origen"))
    estado = seguridad.normalizar_estado(datos.get("estado"))
    if estado not in {"completado", "detenido", "error", "sin_entender"}:
        estado = "completado"
    crudas = datos.get("ordenes") or []
    if not isinstance(crudas, list):
        crudas = []
    try:
        ordenes = validar_ordenes_seguras(crudas, texto)
    except ValueError:
        ordenes = []
    creado = str(datos.get("creado_en") or "").strip()
    try:
        momento = datetime.fromisoformat(creado)
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        if momento > datetime.now(timezone.utc) + timedelta(days=2):
            creado = ""
    except (ValueError, TypeError):
        creado = ""
    prompt_id = base_datos.crear_prompt(
        int(peticion.usuario["id"]),
        texto,
        "offline",
        estado,
        ordenes,
        False,
        "",
        seguridad.limpiar_texto(datos.get("error"), 500),
        creado or None,
    )
    try:
        duracion_offline = int(datos.get("duracion_ms") or 0)
    except (TypeError, ValueError):
        duracion_offline = 0
    base_datos.actualizar_prompt(
        prompt_id,
        int(peticion.usuario["id"]),
        estado,
        seguridad.limpiar_texto(datos.get("error"), 500),
        max(0, min(duracion_offline, 3_600_000)),
        [_orden_dict(o) for o in ordenes],
    )
    return Respuesta.json({"ok": True, "prompt_id": prompt_id})


def validar_ordenes_seguras(crudas: list, texto: str):
    from pasoapaso.nucleo.validacion import validar_ordenes

    return validar_ordenes(crudas, texto, maximo=12)


@ruta("GET", r"/api/historial")
@solo_usuario
def api_historial(peticion: Peticion) -> Respuesta:
    limite = peticion.entero("limite", 30)
    historial = base_datos.historial_usuario(int(peticion.usuario["id"]), limite)
    return Respuesta.json(
        {"ok": True, "consultas": [_prompt_api(p) for p in historial]}
    )


@ruta("POST", r"/api/feedback")
@solo_usuario
def api_feedback(peticion: Peticion) -> Respuesta:
    datos = peticion.json()
    try:
        prompt_id = int(datos.get("prompt_id"))
    except (TypeError, ValueError) as error:
        raise ErrorHTTP(400, "Falta la consulta.", api=True) from error
    prompt = base_datos.obtener_prompt(prompt_id)
    if not prompt or int(prompt.get("usuario_id") or 0) != int(peticion.usuario["id"]):
        raise ErrorHTTP(404, "No encontré esa consulta.", api=True)
    util = bool(datos.get("util"))
    comentario = seguridad.limpiar_texto(datos.get("comentario"), 300)
    base_datos.guardar_feedback(prompt_id, util, comentario)
    return Respuesta.json({"ok": True})


# --- Administración ---------------------------------------------------------

def _vista_admin_login(peticion: Peticion, error: str = "", aviso: str = "") -> Respuesta:
    csrf = csrf_token(peticion)
    por_defecto = base_datos.admin_usa_clave_defecto()
    contenido = vistas.render(
        "admin_login",
        csrf=vistas.csrf_input(csrf),
        error=vistas.aviso(error, "error"),
        aviso=vistas.aviso(aviso, "ok"),
        usuario=vistas.escapar(config.ADMIN_USUARIO),
        por_defecto=(
            f'<div class="aviso aviso-aviso"><strong>Clave inicial.</strong> '
            f"Usuario <code>{vistas.escapar(config.ADMIN_USUARIO)}</code> y clave "
            f"<code>{vistas.escapar(config.ADMIN_CLAVE_DEFECTO)}</code>. "
            "Cámbiala en «Mi clave» antes de mostrar el proyecto.</div>"
            if por_defecto and not config.PRODUCCION
            else ""
        ),
        version=config.VERSION,
        anio=datetime.now().year,
    )
    return Respuesta.html(contenido)


@ruta("GET", r"/admin/entrar")
def admin_entrar_form(peticion: Peticion) -> Respuesta:
    if peticion.admin:
        return Respuesta.redirigir("/admin")
    return _vista_admin_login(peticion, aviso=peticion.dato("aviso"))


@ruta("POST", r"/admin/entrar")
def admin_entrar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    usuario = peticion.dato("usuario").strip()
    clave = peticion.dato("clave")
    limite = _clave_limite(peticion, "admin|" + usuario.lower())
    if not LIMITADOR_LOGIN.permitido(limite):
        return _vista_admin_login(
            peticion, error="Demasiados intentos. Espera unos minutos y vuelve a probar."
        )
    admin = base_datos.obtener_admin_por_usuario(usuario)
    if not admin or not seguridad.verificar_clave(clave, admin.get("clave_hash", "")):
        LIMITADOR_LOGIN.fallo(limite)
        return _vista_admin_login(peticion, error="Usuario o clave incorrectos.")
    LIMITADOR_LOGIN.limpiar(limite)
    base_datos.registrar_acceso_admin(int(admin["id"]))
    _crear_sesion_admin(peticion, admin)
    return Respuesta.redirigir("/admin")


@ruta("POST", r"/admin/salir")
@solo_admin
def admin_salir(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    peticion.borrar_cookie("pa_admin")
    return Respuesta.redirigir("/admin/entrar")


@ruta("GET", r"/admin")
@solo_admin
def admin_panel(peticion: Peticion) -> Respuesta:
    return _vista_admin_panel(peticion)


def _vista_admin_panel(peticion: Peticion, aviso: str = "", error: str = "") -> Respuesta:
    stats = base_datos.estadisticas()
    csrf = csrf_token(peticion)
    tarjetas = "".join(
        [
            vistas.tarjeta_stat(stats["total_usuarios"], "Personas registradas", f"{stats['nuevos_hoy']} hoy", "teal"),
            vistas.tarjeta_stat(stats["total_prompts"], "Consultas guardadas", f"{stats['prompts_hoy']} hoy", "azul"),
            vistas.tarjeta_stat(f"{stats['ia_porcentaje']}%", "Resueltas con IA", f"{stats['ia_total']} en total", "violeta"),
            vistas.tarjeta_stat(stats["pendientes"], "Pendientes", "Sin resultado reportado", "ambar"),
        ]
    )
    filas = _filas_prompt(stats["recientes"], admin=True)
    top = "".join(
        f'<li><span>{vistas.escapar(vistas.TIPOS_ACCION.get(tipo, tipo))}</span>'
        f"<strong>{n}</strong></li>"
        for tipo, n in stats["top"]
    ) or '<li class="vacio">Todavía no hay datos.</li>'
    contenido = vistas.render(
        "admin_panel",
        tarjetas=tarjetas,
        grafico=vistas.grafico(stats["serie"], stats["max_serie"]),
        filas=filas,
        top=top,
        aviso_clave=(
            '<div class="aviso aviso-aviso"><strong>Estás usando la clave inicial.</strong> '
            'Cámbiala en <a href="/admin/clave">Mi clave</a>.</div>'
            if base_datos.admin_usa_clave_defecto()
            else ""
        ),
        ia_estado=(
            '<span class="chip chip-verde">IA activa</span>'
            if base_datos.ia_activa() and config.GEMINI_API_KEY
            else '<span class="chip chip-ambar">IA no configurada</span>'
        ),
        mensajes=_mensajes(peticion) + vistas.aviso(aviso, "ok") + vistas.aviso(error, "error"),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Resumen", contenido, admin=peticion.admin, nav=vistas.nav_admin("panel", csrf)
        )
    )


@ruta("GET", r"/admin/usuarios")
@solo_admin
def admin_usuarios(peticion: Peticion) -> Respuesta:
    return _vista_admin_usuarios(peticion)


def _vista_admin_usuarios(peticion: Peticion, aviso: str = "", error: str = "") -> Respuesta:
    busqueda = peticion.dato("q").strip()
    pagina = _pagina(peticion)
    resultado = base_datos.listar_usuarios(busqueda, pagina)
    csrf = csrf_token(peticion)
    filas = []
    for usuario in resultado["filas"]:
        estado = (
            '<span class="chip chip-verde">Activa</span>'
            if int(usuario.get("activo", 0))
            else '<span class="chip chip-rojo">Desactivada</span>'
        )
        filas.append(
            f"""<tr>
              <td><a class="enlace-fuerte" href="/admin/usuarios/{usuario['id']}">{vistas.escapar(usuario.get('nombre',''))}</a>
                  <div class="texto-pequeno">{vistas.escapar(_telefono_bonito(usuario.get('telefono','')))}</div></td>
              <td>{vistas.insignia_experiencia(usuario.get('experiencia',''))}</td>
              <td class="numero">{usuario.get('consultas', 0)}</td>
              <td>{estado}</td>
              <td class="columna-fecha">{vistas.escapar(vistas.fecha(usuario.get('creado_en',''), '%d/%m/%Y'))}</td>
              <td><a class="boton boton-suave boton-pequeno" href="/admin/usuarios/{usuario['id']}">Ver</a></td>
            </tr>"""
        )
    filas = "".join(filas) or vistas.tabla_vacia("No hay personas registradas todavía.", 6)
    contenido = vistas.render(
        "admin_usuarios",
        csrf=vistas.csrf_input(csrf),
        filas=filas,
        total=resultado["total"],
        q=vistas.escapar(busqueda),
        paginacion=vistas.paginacion(
            resultado["pagina"], resultado["paginas"], "/admin/usuarios", {"q": busqueda}
        ),
        mensajes=_mensajes(peticion) + vistas.aviso(aviso, "ok") + vistas.aviso(error, "error"),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Usuarios", contenido, admin=peticion.admin, nav=vistas.nav_admin("usuarios", csrf)
        )
    )


@ruta("GET", r"/admin/usuarios/(?P<usuario_id>\d+)")
@solo_admin
def admin_usuario(peticion: Peticion) -> Respuesta:
    return _vista_admin_usuario(peticion, int(peticion.params["usuario_id"]))


def _vista_admin_usuario(
    peticion: Peticion,
    usuario_id: int,
    pin_temporal: str = "",
    aviso: str = "",
    error: str = "",
) -> Respuesta:
    usuario = base_datos.obtener_usuario(usuario_id)
    if not usuario:
        raise ErrorHTTP(404, "No encontré esa persona.")
    pagina = _pagina(peticion)
    resultado = base_datos.listar_prompts(usuario_id=usuario_id, pagina=pagina, por_pagina=15)
    csrf = csrf_token(peticion)
    filas = []
    for prompt in resultado["filas"]:
        filas.append(
            f"""<tr>
              <td><a class="enlace-fuerte" href="/admin/prompts/{prompt['id']}">{vistas.escapar(vistas.texto_truncado(prompt.get('texto',''), 70))}</a></td>
              <td>{vistas.insignia_origen(prompt.get('origen',''))}</td>
              <td>{vistas.insignia_estado(prompt.get('estado',''))}</td>
              <td>{vistas.insignia_ia(prompt.get('ia_usada',0))}</td>
              <td class="columna-fecha">{vistas.escapar(prompt.get('fecha_corta',''))}</td>
            </tr>"""
        )
    filas = "".join(filas) or vistas.tabla_vacia("Esta persona todavía no hizo consultas.", 5)
    pin_html = (
        f'<div class="aviso aviso-ok"><strong>Nueva clave temporal:</strong> '
        f'<code class="clave-temporal">{vistas.escapar(pin_temporal)}</code>. '
        "Dásela a la persona y pídele que la cambie al entrar.</div>"
        if pin_temporal
        else ""
    )
    contenido = vistas.render(
        "admin_usuario",
        csrf=vistas.csrf_input(csrf),
        usuario_id=usuario_id,
        nombre=vistas.escapar(usuario.get("nombre", "")),
        iniciales=vistas.escapar(vistas.iniciales(usuario.get("nombre", ""))),
        telefono=vistas.escapar(_telefono_bonito(usuario.get("telefono", ""))),
        ciudad=vistas.escapar(usuario.get("ciudad") or "Sin indicar"),
        edad=vistas.escapar(usuario.get("edad") if usuario.get("edad") else "Sin indicar"),
        experiencia=vistas.insignia_experiencia(usuario.get("experiencia", "")),
        estado=(
            '<span class="chip chip-verde">Activa</span>'
            if int(usuario.get("activo", 0))
            else '<span class="chip chip-rojo">Desactivada</span>'
        ),
        desde=vistas.escapar(vistas.fecha(usuario.get("creado_en", ""), "%d/%m/%Y")),
        ultimo=vistas.escapar(vistas.fecha(usuario.get("ultimo_acceso") or "")),
        consultas=resultado["total"],
        filas=filas,
        pin_html=pin_html,
        paginacion=vistas.paginacion(
            resultado["pagina"], resultado["paginas"], f"/admin/usuarios/{usuario_id}", {}
        ),
        mensajes=_mensajes(peticion) + vistas.aviso(aviso, "ok") + vistas.aviso(error, "error"),
    )
    return Respuesta.html(
        vistas.layout_admin(
            usuario.get("nombre", "Usuario"),
            contenido,
            admin=peticion.admin,
            nav=vistas.nav_admin("usuarios", csrf),
        )
    )


@ruta("POST", r"/admin/usuarios/(?P<usuario_id>\d+)/activo")
@solo_admin
def admin_usuario_activo(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    nuevo = base_datos.alternar_usuario(int(peticion.params["usuario_id"]))
    if nuevo is None:
        raise ErrorHTTP(404, "No encontré esa persona.")
    mensaje = "Cuenta activada." if nuevo else "Cuenta desactivada."
    return Respuesta.redirigir(
        _query_redireccion(f"/admin/usuarios/{peticion.params['usuario_id']}", mensaje)
    )


@ruta("POST", r"/admin/usuarios/(?P<usuario_id>\d+)/pin")
@solo_admin
def admin_usuario_pin(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    usuario_id = int(peticion.params["usuario_id"])
    if not base_datos.obtener_usuario(usuario_id):
        raise ErrorHTTP(404, "No encontré esa persona.")
    pin = base_datos.resetear_pin(usuario_id)
    return _vista_admin_usuario(peticion, usuario_id, pin_temporal=pin)


@ruta("POST", r"/admin/usuarios/(?P<usuario_id>\d+)/eliminar")
@solo_admin
def admin_usuario_eliminar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    if peticion.dato("confirmar").strip().upper() != "ELIMINAR":
        return _vista_admin_usuario(
            peticion,
            int(peticion.params["usuario_id"]),
            error="Escribe ELIMINAR para confirmar que quieres borrar la cuenta y sus consultas.",
        )
    base_datos.eliminar_usuario(int(peticion.params["usuario_id"]))
    return Respuesta.redirigir(
        _query_redireccion("/admin/usuarios", "La cuenta y sus consultas fueron eliminadas.")
    )


@ruta("GET", r"/admin/prompts")
@solo_admin
def admin_prompts(peticion: Peticion) -> Respuesta:
    return _vista_admin_prompts(peticion)


def _vista_admin_prompts(peticion: Peticion) -> Respuesta:
    busqueda = peticion.dato("q").strip()
    estado = peticion.dato("estado").strip()
    origen = peticion.dato("origen").strip()
    ia_filtro = peticion.dato("ia").strip()
    pagina = _pagina(peticion)
    resultado = base_datos.listar_prompts(
        busqueda=busqueda,
        estado=estado,
        origen=origen,
        ia=ia_filtro,
        pagina=pagina,
    )
    csrf = csrf_token(peticion)
    filas = []
    for prompt in resultado["filas"]:
        filas.append(
            f"""<tr>
              <td class="numero">{prompt['id']}</td>
              <td><a class="enlace-fuerte" href="/admin/prompts/{prompt['id']}">{vistas.escapar(vistas.texto_truncado(prompt.get('texto',''), 80))}</a>
                  <div class="texto-pequeno">{vistas.escapar(prompt.get('usuario_nombre') or 'Sin usuario')}</div></td>
              <td>{vistas.insignia_origen(prompt.get('origen',''))}</td>
              <td>{vistas.insignia_estado(prompt.get('estado',''))}</td>
              <td>{vistas.insignia_ia(prompt.get('ia_usada',0))}</td>
              <td class="columna-fecha">{vistas.escapar(prompt.get('fecha_corta',''))}</td>
            </tr>"""
        )
    filas = "".join(filas) or vistas.tabla_vacia("No hay consultas con esos filtros.", 6)
    opciones_estado = "".join(
        f'<option value="{k}"{" selected" if estado == k else ""}>{vistas.escapar(v)}</option>'
        for k, (v, _) in vistas.ESTADOS.items()
    )
    opciones_origen = "".join(
        f'<option value="{k}"{" selected" if origen == k else ""}>{vistas.escapar(v)}</option>'
        for k, (v, _) in vistas.ORIGENES.items()
    )
    contenido = vistas.render(
        "admin_prompts",
        csrf=vistas.csrf_input(csrf),
        filas=filas,
        total=resultado["total"],
        q=vistas.escapar(busqueda),
        opciones_estado=opciones_estado,
        opciones_origen=opciones_origen,
        ia_sel_1=" selected" if ia_filtro == "1" else "",
        ia_sel_0=" selected" if ia_filtro == "0" else "",
        paginacion=vistas.paginacion(
            resultado["pagina"],
            resultado["paginas"],
            "/admin/prompts",
            {"q": busqueda, "estado": estado, "origen": origen, "ia": ia_filtro},
        ),
        mensajes=_mensajes(peticion),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Consultas", contenido, admin=peticion.admin, nav=vistas.nav_admin("prompts", csrf)
        )
    )


@ruta("GET", r"/admin/prompts/(?P<prompt_id>\d+)")
@solo_admin
def admin_prompt(peticion: Peticion) -> Respuesta:
    prompt = base_datos.obtener_prompt(int(peticion.params["prompt_id"]))
    if not prompt:
        raise ErrorHTTP(404, "No encontré esa consulta.")
    csrf = csrf_token(peticion)
    feedback = base_datos.feedback_de_prompt(int(prompt["id"]))
    if feedback:
        feedback_html = (
            f'<p><strong>{"Sí, le sirvió" if feedback.get("util") else "No le sirvió"}.</strong> '
            f'<span class="texto-pequeno">{vistas.escapar(vistas.fecha(feedback.get("creado_en", "")))}</span></p>'
            + (f'<p class="texto-pequeno">«{vistas.escapar(feedback.get("comentario") or "")}»</p>' if feedback.get("comentario") else "")
        )
    else:
        feedback_html = '<p class="vacio">La persona todavía no respondió.</p>'
    contenido = vistas.render(
        "admin_prompt",
        csrf=vistas.csrf_input(csrf),
        prompt_id=prompt["id"],
        texto=vistas.escapar(prompt.get("texto", "")),
        usuario_nombre=vistas.escapar(prompt.get("usuario_nombre") or "Sin usuario"),
        usuario_id=prompt.get("usuario_id") or "",
        usuario_telefono=vistas.escapar(_telefono_bonito(prompt.get("usuario_telefono") or "")),
        fecha=vistas.escapar(prompt.get("fecha", "")),
        origen=vistas.insignia_origen(prompt.get("origen", "")),
        estado=vistas.insignia_estado(prompt.get("estado", "")),
        ia=vistas.insignia_ia(prompt.get("ia_usada", 0)),
        modelo=vistas.escapar(prompt.get("ia_modelo") or "Reglas locales"),
        duracion=vistas.escapar(f"{prompt.get('duracion_ms')} ms" if prompt.get("duracion_ms") else "—"),
        error=vistas.aviso(prompt.get("error") or "", "error"),
        ordenes=vistas.lista_ordenes(prompt.get("intencion") or []),
        acciones=vistas.lista_ordenes(prompt.get("acciones") or []),
        json=vistas.escapar(vistas.json_bonito(prompt.get("intencion") or [])),
        feedback=feedback or {},
        feedback_html=feedback_html,
        mensajes=_mensajes(peticion),
    )
    return Respuesta.html(
        vistas.layout_admin(
            f"Consulta #{prompt['id']}",
            contenido,
            admin=peticion.admin,
            nav=vistas.nav_admin("prompts", csrf),
        )
    )


@ruta("GET", r"/admin/ia")
@solo_admin
def admin_ia(peticion: Peticion) -> Respuesta:
    return _vista_admin_ia(peticion)


def _vista_admin_ia(peticion: Peticion, aviso: str = "") -> Respuesta:
    csrf = csrf_token(peticion)
    activa = base_datos.ia_activa()
    configurada = bool(config.GEMINI_API_KEY)
    registro = base_datos.registro_abierto()
    recientes = base_datos.listar_prompts(ia="1", por_pagina=8)["filas"]
    filas = _filas_prompt(recientes, admin=True)
    contenido = vistas.render(
        "admin_ia",
        csrf=vistas.csrf_input(csrf),
        activa_checked="checked" if activa else "",
        registro_checked="checked" if registro else "",
        configurada=(
            '<span class="chip chip-verde">Configurada</span>'
            if configurada
            else '<span class="chip chip-rojo">Falta la clave</span>'
        ),
        activa_chip=(
            '<span class="chip chip-verde">Activa</span>'
            if activa
            else '<span class="chip chip-gris">Desactivada</span>'
        ),
        modelo=vistas.escapar(config.GEMINI_MODELO),
        filas=filas,
        mensajes=_mensajes(peticion) + vistas.aviso(aviso, "ok"),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Inteligencia artificial", contenido, admin=peticion.admin, nav=vistas.nav_admin("ia", csrf)
        )
    )


@ruta("POST", r"/admin/ia")
@solo_admin
def admin_ia_guardar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    base_datos.guardar_ajuste("ia_activa", "1" if peticion.dato("ia_activa") == "1" else "0")
    base_datos.guardar_ajuste(
        "permitir_registro", "1" if peticion.dato("permitir_registro") == "1" else "0"
    )
    return Respuesta.redirigir(
        _query_redireccion("/admin/ia", "La configuración se guardó correctamente.")
    )


@ruta("GET", r"/admin/clave")
@solo_admin
def admin_clave(peticion: Peticion) -> Respuesta:
    csrf = csrf_token(peticion)
    contenido = vistas.render(
        "admin_clave",
        csrf=vistas.csrf_input(csrf),
        mensajes=_mensajes(peticion),
        por_defecto=base_datos.admin_usa_clave_defecto(),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Mi clave", contenido, admin=peticion.admin, nav=vistas.nav_admin("clave", csrf)
        )
    )


@ruta("POST", r"/admin/clave")
@solo_admin
def admin_clave_guardar(peticion: Peticion) -> Respuesta:
    csrf_valido(peticion)
    actual = peticion.dato("actual")
    nueva = peticion.dato("nueva")
    repetir = peticion.dato("repetir")
    if not seguridad.verificar_clave(actual, peticion.admin.get("clave_hash", "")):
        return _vista_admin_clave_error(peticion, "La clave actual no es correcta.")
    error = seguridad.validar_clave_admin(nueva)
    if error:
        return _vista_admin_clave_error(peticion, error)
    if nueva != repetir:
        return _vista_admin_clave_error(peticion, "Las dos claves nuevas no son iguales.")
    base_datos.cambiar_clave_admin(int(peticion.admin["id"]), nueva)
    admin = base_datos.obtener_admin(int(peticion.admin["id"]))
    if admin:
        _crear_sesion_admin(peticion, admin)
    return Respuesta.redirigir(
        _query_redireccion("/admin", "Tu clave de administrador se cambió correctamente.")
    )


def _vista_admin_clave_error(peticion: Peticion, mensaje: str) -> Respuesta:
    csrf = csrf_token(peticion)
    contenido = vistas.render(
        "admin_clave",
        csrf=vistas.csrf_input(csrf),
        mensajes=vistas.aviso(mensaje, "error"),
        por_defecto=base_datos.admin_usa_clave_defecto(),
    )
    return Respuesta.html(
        vistas.layout_admin(
            "Mi clave", contenido, admin=peticion.admin, nav=vistas.nav_admin("clave", csrf)
        )
    )


def _celda_csv(valor) -> str:
    """Evita que Excel interprete texto del usuario como fórmula."""
    texto = "" if valor is None else str(valor)
    if texto[:1] in ("=", "+", "-", "@"):
        texto = "'" + texto
    return texto


@ruta("GET", r"/admin/exportar.csv")
@solo_admin
def admin_exportar(peticion: Peticion) -> Respuesta:
    filas = base_datos.prompts_para_exportar()
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(
        [
            "ID",
            "Fecha",
            "Usuario",
            "Teléfono",
            "Texto",
            "Origen",
            "Estado",
            "IA",
            "Modelo",
            "Duración ms",
            "Error",
            "Acciones",
        ]
    )
    for fila in filas:
        acciones = ", ".join(
            str(o.get("tipo", ""))
            for o in base_datos._json_lista(fila.get("intencion_json"))
            if isinstance(o, dict)
        )
        escritor.writerow(
            [
                fila.get("id"),
                vistas.fecha(fila.get("creado_en", "")),
                _celda_csv(fila.get("usuario_nombre")),
                _celda_csv(fila.get("usuario_telefono")),
                _celda_csv(fila.get("texto")),
                _celda_csv(fila.get("origen")),
                _celda_csv(fila.get("estado")),
                "Sí" if fila.get("ia_usada") else "No",
                _celda_csv(fila.get("ia_modelo")),
                fila.get("duracion_ms") or "",
                _celda_csv(fila.get("error")),
                _celda_csv(acciones),
            ]
        )
    datos = ("\ufeff" + salida.getvalue()).encode("utf-8")
    nombre = f"pasoapaso_consultas_{datetime.now():%Y%m%d_%H%M}.csv"
    return Respuesta(
        200,
        datos,
        "text/csv; charset=utf-8",
        [("Content-Disposition", f'attachment; filename="{nombre}"'), ("Cache-Control", "no-store")],
    )
