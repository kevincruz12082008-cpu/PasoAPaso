"""Base de datos SQLite de PasoAPaso.

Guarda usuarios, administradores, prompts (lo que escribe o dice cada
persona), resultados, feedback y ajustes. Todo con sqlite3, sin
dependencias externas.
"""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from . import config, seguridad

UTC = timezone.utc


# --- Fechas -----------------------------------------------------------------

def ahora_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def a_local(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        momento = datetime.fromisoformat(str(iso))
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=UTC)
        return momento.astimezone(timezone(timedelta(hours=config.ZONA_UTC)))
    except (ValueError, TypeError):
        return None


def fecha_local(iso: str, formato: str = "%d/%m/%Y %H:%M") -> str:
    momento = a_local(iso)
    return momento.strftime(formato) if momento else "—"


def inicio_dia_utc(dias_atras: int = 0) -> str:
    local = datetime.now(UTC) + timedelta(hours=config.ZONA_UTC)
    inicio = (local - timedelta(days=dias_atras)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (inicio - timedelta(hours=config.ZONA_UTC)).isoformat(timespec="seconds")


# --- Conexión y esquema -----------------------------------------------------

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    clave_hash TEXT NOT NULL,
    edad INTEGER,
    ciudad TEXT,
    experiencia TEXT NOT NULL DEFAULT 'poco',
    como_nos_conocio TEXT,
    consentimiento_en TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL,
    ultimo_acceso TEXT,
    token_version INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS administradores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    clave_hash TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    ultimo_acceso TEXT,
    clave_por_defecto INTEGER NOT NULL DEFAULT 0,
    token_version INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    texto TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'texto',
    estado TEXT NOT NULL DEFAULT 'pendiente',
    intencion_json TEXT,
    acciones_json TEXT,
    ia_usada INTEGER NOT NULL DEFAULT 0,
    ia_modelo TEXT,
    error TEXT,
    duracion_ms INTEGER,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prompts_usuario ON prompts(usuario_id);
CREATE INDEX IF NOT EXISTS idx_prompts_creado ON prompts(creado_en);
CREATE INDEX IF NOT EXISTS idx_prompts_estado ON prompts(estado);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL UNIQUE,
    util INTEGER NOT NULL,
    comentario TEXT,
    creado_en TEXT NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def conectar(ruta: Optional[Path | str] = None) -> sqlite3.Connection:
    ruta = Path(ruta or config.RUTA_DB)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(ruta), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    return con


@contextmanager
def conexion(ruta: Optional[Path | str] = None):
    con = conectar(ruta)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar(ruta: Optional[Path | str] = None) -> Path:
    ruta = Path(ruta or config.RUTA_DB)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = conectar(ruta)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")
        con.executescript(ESQUEMA)
        _sembrar(con)
        con.execute("PRAGMA user_version = 2")
        con.commit()
    finally:
        con.close()
    return ruta


def _sembrar(con: sqlite3.Connection) -> None:
    valores = {
        "ia_activa": "1" if config.IA_ACTIVA else "0",
        "permitir_registro": "1" if config.REGISTRO_ABIERTO else "0",
        "version": config.VERSION,
        "nombre_sitio": config.NOMBRE_APP,
    }
    for clave, valor in valores.items():
        con.execute(
            "INSERT OR IGNORE INTO ajustes (clave, valor) VALUES (?, ?)",
            (clave, valor),
        )

    fila = con.execute("SELECT id FROM administradores LIMIT 1").fetchone()
    if fila is None:
        con.execute(
            """INSERT INTO administradores
               (usuario, nombre, clave_hash, creado_en, clave_por_defecto)
               VALUES (?, ?, ?, ?, ?)""",
            (
                config.ADMIN_USUARIO,
                config.ADMIN_NOMBRE,
                seguridad.hash_clave(config.ADMIN_CLAVE),
                ahora_utc(),
                1 if config.ADMIN_CLAVE_ES_DEFECTO else 0,
            ),
        )
        con.execute(
            "INSERT OR REPLACE INTO ajustes (clave, valor) VALUES ('admin_clave_default', ?)",
            ("1" if config.ADMIN_CLAVE_ES_DEFECTO else "0",),
        )
    elif config.ADMIN_RESET and not config.ADMIN_CLAVE_ES_DEFECTO:
        con.execute(
            "UPDATE administradores SET clave_hash = ?, clave_por_defecto = 0",
            (seguridad.hash_clave(config.ADMIN_CLAVE),),
        )
        con.execute(
            "INSERT OR REPLACE INTO ajustes (clave, valor) VALUES ('admin_clave_default', '0')"
        )


# --- Utilidades internas ----------------------------------------------------

def _fila(fila: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(fila) if fila is not None else None


def _publico(usuario: Optional[dict]) -> Optional[dict]:
    if not usuario:
        return None
    return {k: v for k, v in usuario.items() if k != "clave_hash"}


def _escapar_like(texto: str) -> str:
    return (texto or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _patron(texto: str) -> str:
    return f"%{_escapar_like(texto)}%"


def _json_lista(valor: Any) -> list:
    if isinstance(valor, list):
        return valor
    if not valor:
        return []
    try:
        datos = json.loads(valor)
        return datos if isinstance(datos, list) else []
    except (ValueError, TypeError):
        return []


def _serializar_ordenes(ordenes: Iterable) -> str:
    lista = []
    for orden in ordenes or []:
        if hasattr(orden, "tipo"):
            lista.append(
                {
                    "tipo": getattr(orden, "tipo", ""),
                    "datos": getattr(orden, "datos", {}) or {},
                    "resumen": getattr(orden, "resumen", ""),
                    "texto": getattr(orden, "texto", ""),
                }
            )
        elif isinstance(orden, dict):
            lista.append(
                {
                    "tipo": str(orden.get("tipo", "")),
                    "datos": orden.get("datos", {}) or {},
                    "resumen": str(orden.get("resumen", "")),
                    "texto": str(orden.get("texto", "")),
                }
            )
    return json.dumps(lista, ensure_ascii=False)


def _prompt_publico(fila: dict) -> dict:
    datos = dict(fila)
    datos["intencion"] = _json_lista(datos.get("intencion_json"))
    datos["acciones"] = _json_lista(datos.get("acciones_json"))
    datos["tipos"] = [str(o.get("tipo", "")) for o in datos["intencion"] if isinstance(o, dict)]
    datos["fecha"] = fecha_local(datos.get("creado_en", ""))
    datos["fecha_corta"] = fecha_local(datos.get("creado_en", ""), "%d/%m %H:%M")
    return datos


# --- Usuarios ---------------------------------------------------------------

def crear_usuario(
    telefono: str,
    nombre: str,
    clave: str,
    edad: Optional[int] = None,
    ciudad: str = "",
    experiencia: str = "poco",
    como_nos_conocio: str = "",
    consentimiento: bool = True,
) -> int:
    with conexion() as con:
        cursor = con.execute(
            """INSERT INTO usuarios
               (telefono, nombre, clave_hash, edad, ciudad, experiencia,
                como_nos_conocio, consentimiento_en, activo, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                telefono,
                nombre,
                seguridad.hash_clave(clave),
                edad,
                ciudad or None,
                experiencia,
                como_nos_conocio or None,
                ahora_utc() if consentimiento else None,
                ahora_utc(),
            ),
        )
        return int(cursor.lastrowid)


def obtener_usuario_por_telefono(telefono: str) -> Optional[dict]:
    with conexion() as con:
        return _fila(
            con.execute(
                "SELECT * FROM usuarios WHERE telefono = ?", (telefono,)
            ).fetchone()
        )


def obtener_usuario(usuario_id: int) -> Optional[dict]:
    with conexion() as con:
        return _fila(
            con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        )


def usuario_publico(usuario: Optional[dict]) -> Optional[dict]:
    return _publico(usuario)


def registrar_acceso(usuario_id: int) -> None:
    with conexion() as con:
        con.execute(
            "UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?",
            (ahora_utc(), usuario_id),
        )


def listar_usuarios(busqueda: str = "", pagina: int = 1) -> dict:
    busqueda = (busqueda or "").strip()
    patron = _patron(busqueda)
    where = "WHERE (? = '' OR u.nombre LIKE ? ESCAPE '\\' OR u.telefono LIKE ? ESCAPE '\\')"
    parametros = (busqueda, patron, patron)
    with conexion() as con:
        total = int(
            con.execute(
                f"SELECT COUNT(*) FROM usuarios u {where}", parametros
            ).fetchone()[0]
        )
        filas = con.execute(
            f"""SELECT u.*,
                       (SELECT COUNT(*) FROM prompts p WHERE p.usuario_id = u.id) AS consultas,
                       (SELECT MAX(p.creado_en) FROM prompts p WHERE p.usuario_id = u.id) AS ultima_consulta
                FROM usuarios u
                {where}
                ORDER BY u.creado_en DESC
                LIMIT ? OFFSET ?""",
            parametros + (config.POR_PAGINA, max(0, (pagina - 1)) * config.POR_PAGINA),
        ).fetchall()
    return {
        "filas": [_publico(dict(f)) for f in filas],
        "total": total,
        "pagina": pagina,
        "paginas": max(1, math.ceil(total / config.POR_PAGINA)),
    }


def alternar_usuario(usuario_id: int) -> Optional[int]:
    with conexion() as con:
        fila = con.execute(
            "SELECT activo FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if not fila:
            return None
        nuevo = 0 if int(fila["activo"]) else 1
        con.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (nuevo, usuario_id))
        return nuevo


def resetear_pin(usuario_id: int) -> str:
    nuevo = seguridad.nuevo_pin(4)
    with conexion() as con:
        con.execute(
            """UPDATE usuarios
               SET clave_hash = ?, token_version = token_version + 1
               WHERE id = ?""",
            (seguridad.hash_clave(nuevo), usuario_id),
        )
    return nuevo


def cambiar_pin(usuario_id: int, nueva: str) -> None:
    with conexion() as con:
        con.execute(
            """UPDATE usuarios
               SET clave_hash = ?, token_version = token_version + 1
               WHERE id = ?""",
            (seguridad.hash_clave(nueva), usuario_id),
        )


def eliminar_usuario(usuario_id: int) -> None:
    with conexion() as con:
        con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))


def total_usuarios() -> int:
    with conexion() as con:
        return int(con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0])


# --- Administradores --------------------------------------------------------

def obtener_admin_por_usuario(usuario: str) -> Optional[dict]:
    with conexion() as con:
        return _fila(
            con.execute(
                "SELECT * FROM administradores WHERE usuario = ?", (usuario,)
            ).fetchone()
        )


def obtener_admin(admin_id: int) -> Optional[dict]:
    with conexion() as con:
        return _fila(
            con.execute("SELECT * FROM administradores WHERE id = ?", (admin_id,)).fetchone()
        )


def registrar_acceso_admin(admin_id: int) -> None:
    with conexion() as con:
        con.execute(
            "UPDATE administradores SET ultimo_acceso = ? WHERE id = ?",
            (ahora_utc(), admin_id),
        )


def cambiar_clave_admin(admin_id: int, nueva: str) -> None:
    with conexion() as con:
        con.execute(
            """UPDATE administradores
               SET clave_hash = ?, clave_por_defecto = 0,
                   token_version = token_version + 1
               WHERE id = ?""",
            (seguridad.hash_clave(nueva), admin_id),
        )
        con.execute(
            "INSERT OR REPLACE INTO ajustes (clave, valor) VALUES ('admin_clave_default', '0')"
        )


def admin_usa_clave_defecto() -> bool:
    with conexion() as con:
        fila = con.execute("SELECT valor FROM ajustes WHERE clave = 'admin_clave_default'").fetchone()
        if fila is not None:
            return str(fila["valor"]) == "1"
        fila = con.execute("SELECT clave_por_defecto FROM administradores LIMIT 1").fetchone()
        return bool(fila and int(fila["clave_por_defecto"]))


# --- Prompts ----------------------------------------------------------------

def crear_prompt(
    usuario_id: Optional[int],
    texto: str,
    origen: str,
    estado: str,
    ordenes: Iterable = (),
    ia_usada: bool = False,
    ia_modelo: str = "",
    error: str = "",
    creado_en: Optional[str] = None,
) -> int:
    with conexion() as con:
        cursor = con.execute(
            """INSERT INTO prompts
               (usuario_id, texto, origen, estado, intencion_json, ia_usada,
                ia_modelo, error, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usuario_id,
                texto,
                origen,
                estado,
                _serializar_ordenes(ordenes),
                1 if ia_usada else 0,
                ia_modelo or None,
                error or None,
                creado_en or ahora_utc(),
            ),
        )
        return int(cursor.lastrowid)


def actualizar_prompt(
    prompt_id: int,
    usuario_id: Optional[int],
    estado: str,
    error: str = "",
    duracion_ms: Optional[int] = None,
    acciones: Iterable = (),
) -> bool:
    with conexion() as con:
        cursor = con.execute(
            """UPDATE prompts
               SET estado = ?, error = ?, duracion_ms = ?,
                   acciones_json = ?, actualizado_en = ?
               WHERE id = ? AND (? IS NULL OR usuario_id = ?)""",
            (
                estado,
                error or None,
                duracion_ms,
                _serializar_ordenes(acciones),
                ahora_utc(),
                prompt_id,
                usuario_id,
                usuario_id,
            ),
        )
        return cursor.rowcount > 0


def obtener_prompt(prompt_id: int) -> Optional[dict]:
    with conexion() as con:
        fila = con.execute(
            """SELECT p.*, u.nombre AS usuario_nombre, u.telefono AS usuario_telefono
               FROM prompts p LEFT JOIN usuarios u ON u.id = p.usuario_id
               WHERE p.id = ?""",
            (prompt_id,),
        ).fetchone()
        return _prompt_publico(dict(fila)) if fila else None


def historial_usuario(usuario_id: int, limite: int = 30) -> list[dict]:
    with conexion() as con:
        filas = con.execute(
            """SELECT * FROM prompts
               WHERE usuario_id = ?
               ORDER BY id DESC LIMIT ?""",
            (usuario_id, max(1, min(100, limite))),
        ).fetchall()
    return [_prompt_publico(dict(f)) for f in filas]


def listar_prompts(
    busqueda: str = "",
    estado: str = "",
    origen: str = "",
    ia: str = "",
    usuario_id: Optional[int] = None,
    pagina: int = 1,
    por_pagina: Optional[int] = None,
) -> dict:
    por_pagina = por_pagina or config.POR_PAGINA
    condiciones = []
    parametros: list[Any] = []
    if busqueda:
        condiciones.append(
            "(p.texto LIKE ? ESCAPE '\\' OR u.nombre LIKE ? ESCAPE '\\' OR u.telefono LIKE ? ESCAPE '\\')"
        )
        patron = _patron(busqueda)
        parametros.extend([patron, patron, patron])
    if estado:
        condiciones.append("p.estado = ?")
        parametros.append(estado)
    if origen:
        condiciones.append("p.origen = ?")
        parametros.append(origen)
    if ia in ("0", "1"):
        condiciones.append("p.ia_usada = ?")
        parametros.append(int(ia))
    if usuario_id:
        condiciones.append("p.usuario_id = ?")
        parametros.append(usuario_id)
    where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
    with conexion() as con:
        total = int(
            con.execute(
                f"""SELECT COUNT(*) FROM prompts p
                    LEFT JOIN usuarios u ON u.id = p.usuario_id {where}""",
                parametros,
            ).fetchone()[0]
        )
        filas = con.execute(
            f"""SELECT p.*, u.nombre AS usuario_nombre, u.telefono AS usuario_telefono
                FROM prompts p LEFT JOIN usuarios u ON u.id = p.usuario_id
                {where}
                ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            parametros + [por_pagina, max(0, (pagina - 1)) * por_pagina],
        ).fetchall()
    return {
        "filas": [_prompt_publico(dict(f)) for f in filas],
        "total": total,
        "pagina": pagina,
        "paginas": max(1, math.ceil(total / por_pagina)),
    }


def prompts_para_exportar(limite: int = 5000) -> list[dict]:
    with conexion() as con:
        filas = con.execute(
            """SELECT p.*, u.nombre AS usuario_nombre, u.telefono AS usuario_telefono
               FROM prompts p LEFT JOIN usuarios u ON u.id = p.usuario_id
               ORDER BY p.id DESC LIMIT ?""",
            (limite,),
        ).fetchall()
    return [dict(f) for f in filas]


def estadisticas() -> dict:
    hoy = inicio_dia_utc(0)
    with conexion() as con:
        total_usuarios = int(con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0])
        usuarios_activos = int(
            con.execute("SELECT COUNT(*) FROM usuarios WHERE activo = 1").fetchone()[0]
        )
        nuevos_hoy = int(
            con.execute(
                "SELECT COUNT(*) FROM usuarios WHERE creado_en >= ?", (hoy,)
            ).fetchone()[0]
        )
        total_prompts = int(con.execute("SELECT COUNT(*) FROM prompts").fetchone()[0])
        prompts_hoy = int(
            con.execute(
                "SELECT COUNT(*) FROM prompts WHERE creado_en >= ?", (hoy,)
            ).fetchone()[0]
        )
        ia_total = int(
            con.execute("SELECT COUNT(*) FROM prompts WHERE ia_usada = 1").fetchone()[0]
        )
        pendientes = int(
            con.execute(
                "SELECT COUNT(*) FROM prompts WHERE estado = 'pendiente'"
            ).fetchone()[0]
        )
        por_estado = {
            fila["estado"]: int(fila["n"])
            for fila in con.execute(
                "SELECT estado, COUNT(*) AS n FROM prompts GROUP BY estado"
            ).fetchall()
        }
        recientes = con.execute(
            """SELECT p.*, u.nombre AS usuario_nombre
               FROM prompts p LEFT JOIN usuarios u ON u.id = p.usuario_id
               ORDER BY p.id DESC LIMIT 8"""
        ).fetchall()
        ultimos = con.execute(
            """SELECT p.*, u.nombre AS usuario_nombre
               FROM prompts p LEFT JOIN usuarios u ON u.id = p.usuario_id
               ORDER BY p.id DESC LIMIT 300"""
        ).fetchall()
        por_experiencia = {
            fila["experiencia"]: int(fila["n"])
            for fila in con.execute(
                "SELECT experiencia, COUNT(*) AS n FROM usuarios GROUP BY experiencia"
            ).fetchall()
        }

    serie = []
    for dias in range(6, -1, -1):
        inicio = inicio_dia_utc(dias)
        fin = inicio_dia_utc(dias - 1) if dias else ahora_utc()
        with conexion() as con:
            n = int(
                con.execute(
                    "SELECT COUNT(*) FROM prompts WHERE creado_en >= ? AND creado_en < ?",
                    (inicio, fin),
                ).fetchone()[0]
            )
        etiqueta = fecha_local(inicio, "%d/%m")
        serie.append({"etiqueta": etiqueta, "n": n})

    acciones: dict[str, int] = {}
    for fila in ultimos:
        for orden in _json_lista(fila["intencion_json"]):
            tipo = str(orden.get("tipo", "desconocido"))
            acciones[tipo] = acciones.get(tipo, 0) + 1
    top = sorted(acciones.items(), key=lambda par: -par[1])[:8]

    return {
        "total_usuarios": total_usuarios,
        "usuarios_activos": usuarios_activos,
        "nuevos_hoy": nuevos_hoy,
        "total_prompts": total_prompts,
        "prompts_hoy": prompts_hoy,
        "ia_total": ia_total,
        "ia_porcentaje": round(ia_total * 100 / total_prompts, 1) if total_prompts else 0,
        "pendientes": pendientes,
        "por_estado": por_estado,
        "por_experiencia": por_experiencia,
        "serie": serie,
        "max_serie": max([p["n"] for p in serie] + [1]),
        "top": top,
        "recientes": [_prompt_publico(dict(f)) for f in recientes],
    }


# --- Feedback ---------------------------------------------------------------

def guardar_feedback(prompt_id: int, util: bool, comentario: str = "") -> None:
    with conexion() as con:
        con.execute(
            """INSERT INTO feedback (prompt_id, util, comentario, creado_en)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(prompt_id) DO UPDATE SET
                   util = excluded.util,
                   comentario = excluded.comentario,
                   creado_en = excluded.creado_en""",
            (prompt_id, 1 if util else 0, comentario or None, ahora_utc()),
        )


def feedback_de_prompt(prompt_id: int) -> Optional[dict]:
    with conexion() as con:
        return _fila(
            con.execute(
                "SELECT * FROM feedback WHERE prompt_id = ?", (prompt_id,)
            ).fetchone()
        )


# --- Ajustes ----------------------------------------------------------------

def obtener_ajuste(clave: str, defecto: str = "") -> str:
    with conexion() as con:
        fila = con.execute(
            "SELECT valor FROM ajustes WHERE clave = ?", (clave,)
        ).fetchone()
        return str(fila["valor"]) if fila is not None else defecto


def guardar_ajuste(clave: str, valor: str) -> None:
    with conexion() as con:
        con.execute(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, str(valor)),
        )


def ia_activa() -> bool:
    # El valor de .env solo se usa al crear la base; después manda el panel.
    return obtener_ajuste("ia_activa", "1") == "1"


def registro_abierto() -> bool:
    return obtener_ajuste("permitir_registro", "1") == "1"
