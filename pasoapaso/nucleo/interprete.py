import re
from dataclasses import dataclass, field

from ..datos.catalogo_apps import CATALOGO, buscar_app
from ..datos.sitios import buscar_sitio
from ..datos.ubicaciones import ETIQUETAS, clave_ubicacion
from ..utilidades.normalizador import limpiar_nombre_archivo, normalizar

ABRIR = "abre|abrir|abreme|abri|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar|enciende|encender|prende|prender|corre|usa|usar|entra|entrar|ve|ir|visita|visitar|navega|muestra|muestrame|mostrar|ver"
CREAR = "crea|crear|creame|haz|hacer|hazme|genera|generar|agrega|agregar|anade|anadir"
OTROS = "toma|tomar|saca|sacar|captura|capturar|busca|buscar|buscame|googlea|investiga|reproduce|reproducir|pon|poner|ponme|escribe|escribir|teclea|sube|subir|baja|bajar|cierra|cerrar|silencia|silenciar|minimiza|minimizar|escucha|escuchar|mira|mirar|play|averigua|encuentra|localiza|aumenta|reduce|quita|apaga|abrela|abrelo|abrelas|abrelos"
VERBOS = "|".join((ABRIR, CREAR, OTROS))

REPRODUCIR = r"(?:reproduce|reproducir|reproduceme|pon|poner|ponme|escucha|escuchar|mira|mirar|ver|play)"
BUSCAR = r"(?:busca|buscar|buscame|googlea|googlear|investiga|investigar|averigua|averiguar|search)"
MEDIOS = r"(?:video|videos|musica|cancion|canciones|clip|clips|tutorial|tutoriales)"
UBICACION = r"(escritorio|desktop|documentos|descargas|imagenes|fotos)"
CONECTORES = r"(?:nueva|nuevo|que se llame|que se llama|que diga|llamada|llamado|nombrada|nombrado|titulada|con el nombre de|con el nombre|con nombre de|con nombre|de nombre|para|de|del|con|y)"
RELLENOS = r"(?:por favor|porfa|porfavor|hola|oye|quiero que me|quiero|necesito|quisiera|me gustaria|me puedes|puedes|podrias|podria|ayudame a|ayudame|me ayudas a|deseo|favor de|ahora|primero)\b\s*"

DOMINIO = re.compile(
    r"((?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|edu|hn|es|io|co|gov|info|app|dev|tv|me)(?:/\S*)?)"
)

SEPARADOR = re.compile(
    r"\s*(?:[,;]|\.(?=\s|$)"
    r"|\by\s+(?:luego|despues|entonces|tambien|por ultimo|finalmente)\b"
    r"|\b(?:despues de eso|por ultimo|luego|despues|entonces|ademas|tambien|finalmente)\b"
    r"|\by\b(?=\s+(?:" + VERBOS + r")\b))\s*"
)

CITAS = re.compile(r'"[^"]*"|“[^”]*”|«[^»]*»')
SIGNOS = " \"'“”«».,"


@dataclass(frozen=True)
class Par:
    n: str
    o: str

    def tramo(self, inicio, fin):
        return Par(self.n[inicio:fin], self.o[inicio:fin])

    def sin_tramo(self, inicio, fin):
        return Par(self.n[:inicio] + self.n[fin:], self.o[:inicio] + self.o[fin:]).limpio()

    def quitar(self, patron):
        n, o = self.n, self.o
        for m in reversed(list(re.finditer(patron, self.n))):
            n = n[: m.start()] + n[m.end():]
            o = o[: m.start()] + o[m.end():]
        return Par(n, o).limpio()

    def recortar_inicio(self, patron):
        m = re.match(patron, self.n)
        if not m or m.end() == 0:
            return self
        return self.tramo(m.end(), len(self.n)).limpio()

    def limpio(self):
        n, o = self.n, self.o
        for m in reversed(list(re.finditer(r"\s+", self.n))):
            n = n[: m.start()] + " " + n[m.end():]
            o = o[: m.start()] + " " + o[m.end():]
        izquierda = len(n) - len(n.lstrip())
        derecha = len(n.rstrip())
        return Par(n[izquierda:derecha], o[izquierda:derecha])


@dataclass
class Orden:
    tipo: str
    datos: dict = field(default_factory=dict)
    resumen: str = ""
    texto: str = ""


def _orden(tipo, resumen, **datos):
    return Orden(tipo=tipo, datos=datos, resumen=resumen)


def _segmentar(par):
    citas = [(m.start(), m.end()) for m in CITAS.finditer(par.n)]
    segmentos = []
    inicio = 0
    for m in SEPARADOR.finditer(par.n):
        if any(a <= m.start() < b for a, b in citas):
            continue
        segmentos.append(par.tramo(inicio, m.start()).limpio())
        inicio = m.end()
    segmentos.append(par.tramo(inicio, len(par.n)).limpio())
    return [s for s in segmentos if s.n]


def _partir(par, patron):
    piezas = []
    inicio = 0
    for m in re.finditer(patron, par.n):
        piezas.append(par.tramo(inicio, m.start()).limpio())
        inicio = m.end()
    piezas.append(par.tramo(inicio, len(par.n)).limpio())
    return piezas


def _sin_rellenos(par):
    par = par.recortar_inicio(r"[¿¡\s]+")
    anterior = None
    while anterior != par:
        anterior = par
        par = par.recortar_inicio(RELLENOS)
    return par.quitar(r"\b(?:por favor|porfa|porfavor|gracias)\b")


def _quitar_conectores(par):
    for _ in range(3):
        siguiente = par.recortar_inicio(CONECTORES + r"\b\s*")
        if siguiente == par:
            break
        par = siguiente
    return par


def _quitar_articulos(par):
    for _ in range(3):
        siguiente = par.recortar_inicio(
            r"(?:el|la|los|las|un|una|unos|unas|mi|mis|programa|aplicacion|app|herramienta|pagina|sitio|web|de|del)\b\s*"
        )
        if siguiente == par:
            break
        par = siguiente
    return par


def _extraer_ubicacion(par, preposiciones):
    m = re.search(
        r"\b" + preposiciones + r"\s+(?:(?:el|la|los|las|mis|mi)\s+)?" + UBICACION + r"\b",
        par.n,
    )
    if not m:
        return par, None
    return par.sin_tramo(m.start(), m.end()), clave_ubicacion(m.group(1))


def _captura(par):
    n = par.n
    if (
        re.search(r"\b(?:captura|capturar|pantallazo|screenshot)\b", n)
        or re.search(r"\bfoto\w*\b.*\bpantalla\b", n)
        or re.search(r"\b(?:toma|tomar|saca|sacar)\b.*\bpantalla\b", n)
    ):
        return [_orden("captura", "Tomar una captura de pantalla")]
    return None


def _crear_carpeta(par):
    n = par.n
    if not re.search(r"\bcarpeta\b", n):
        return None
    pide_crear = (
        re.match(r"(?:%s)\b" % CREAR, n)
        or re.match(r"(?:una\s+)?(?:nueva\s+)?carpeta\b", n)
        or re.search(r"\b(?:%s)\b.*\bcarpeta\b" % CREAR, n)
    )
    if not pide_crear:
        return None
    par, clave = _extraer_ubicacion(par, r"(?:en|dentro de|dentro del|adentro de)")
    m = re.search(r"\bcarpeta\b", par.n)
    resto = _quitar_conectores(par.tramo(m.end(), len(par.n)).limpio())
    nombre = limpiar_nombre_archivo(resto.o.strip(SIGNOS)) or "Nueva carpeta"
    clave = clave or "escritorio"
    return [
        _orden(
            "crear_carpeta",
            f"Crear la carpeta «{nombre}» en {ETIQUETAS[clave]}",
            nombre=nombre,
            ubicacion=clave,
        )
    ]


def _abrir_carpeta(par):
    n = par.n
    if not re.match(r"(?:%s|busca|buscar|encuentra|localiza)\b" % ABRIR, n):
        return None
    if re.search(r"\bcarpeta\b", n):
        par, clave = _extraer_ubicacion(par, r"(?:en|dentro del|dentro de|del|de la|de|desde)")
        m = re.search(r"\bcarpeta\b", par.n)
        resto = _quitar_conectores(par.tramo(m.end(), len(par.n)).limpio())
        nombre = resto.o.strip(SIGNOS)
        como_lugar = clave_ubicacion(resto.n.strip(SIGNOS))
        if como_lugar:
            clave, nombre = como_lugar, ""
        if nombre:
            resumen = f"Abrir la carpeta «{nombre}»"
        elif clave:
            resumen = f"Abrir {ETIQUETAS[clave]}"
        else:
            resumen = "Abrir el Explorador de archivos"
        return [_orden("abrir_carpeta", resumen, nombre=nombre or None, ubicacion=clave)]
    m = re.match(
        r"(?:%s)\s+(?:(?:el|la|los|las|mis|mi)\s+)*(documentos|descargas|imagenes|fotos)$" % ABRIR,
        n,
    )
    if m:
        clave = clave_ubicacion(m.group(1))
        return [_orden("abrir_carpeta", f"Abrir {ETIQUETAS[clave]}", nombre=None, ubicacion=clave)]
    return None


def _youtube(par):
    n = par.n
    tiene = bool(re.search(r"\byou\s?tube\b", n))
    medio = bool(re.search(r"\b%s\b" % MEDIOS, n))
    reproduce = bool(re.match(r"%s\b" % REPRODUCIR, n))
    busca = bool(re.match(r"(?:busca|buscar|buscame|encuentra)\b", n))
    if not (tiene or (reproduce and medio) or (busca and medio)):
        return None
    consulta = par.quitar(r"\b(?:en|por|de|desde|a traves de|usando|con)\s+you\s?tube\b")
    consulta = consulta.quitar(r"\byou\s?tube\b")
    for _ in range(3):
        consulta = consulta.recortar_inicio(
            r"(?:%s|%s|busca|buscar|buscame|encuentra|a)\b\s*" % (ABRIR, REPRODUCIR)
        )
    consulta = consulta.recortar_inicio(
        r"(?:(?:un|el|la|los|las|unos|unas)\s+)?%s\b\s*(?:(?:de la|de los|de las|del|de|sobre|que se llama|llamada|llamado)\b\s*)?"
        % MEDIOS
    )
    consulta = consulta.recortar_inicio(r"(?:de la|de los|del|de|a|al)\b\s*")
    texto = consulta.o.strip(SIGNOS)
    if not texto:
        resumen = "Abrir YouTube"
    elif reproduce:
        resumen = f"Reproducir «{texto}» en YouTube"
    else:
        resumen = f"Buscar «{texto}» en YouTube"
    return [_orden("youtube", resumen, consulta=texto, reproducir=reproduce and bool(texto))]


def _buscar(par):
    m = re.match(BUSCAR + r"\b\s*", par.n)
    if not m:
        return None
    resto = par.tramo(m.end(), len(par.n)).limpio()
    navegador = "chrome"
    mn = re.search(
        r"\b(?:en|con|usando|desde)\s+(?:el\s+)?(?:navegador\s+)?(google chrome|chrome|microsoft edge|edge|firefox|mozilla firefox)\b",
        resto.n,
    )
    if mn:
        nombre = mn.group(1)
        navegador = "edge" if "edge" in nombre else "firefox" if "firefox" in nombre else "chrome"
        resto = resto.sin_tramo(mn.start(), mn.end())
    resto = resto.quitar(
        r"\b(?:en|por|con|usando|desde)\s+(?:google|internet|la web|la red|el navegador|el buscador)\b"
    )
    consulta = resto.o.strip(SIGNOS)
    resumen = f"Buscar «{consulta}» en internet" if consulta else "Abrir el navegador"
    return [_orden("buscar_web", resumen, consulta=consulta, navegador=navegador)]


def _escritorio(par):
    n = par.n
    if re.search(r"\bescritorio\b", n) and re.match(
        r"(?:%s|minimiza|minimizar|esconde|oculta)\b" % ABRIR, n
    ):
        return [_orden("escritorio", "Mostrar el escritorio")]
    if re.search(r"\bminimiza\w*\b.*\bventanas\b", n):
        return [_orden("escritorio", "Mostrar el escritorio")]
    return None


def _abrir(par):
    m = re.match(r"(?:%s)\s+(.+)$" % ABRIR, par.n)
    if not m:
        return None
    objetivo = par.tramo(m.start(1), m.end(1))
    dominio = DOMINIO.search(objetivo.n)
    if dominio:
        direccion = objetivo.o[dominio.start(1): dominio.end(1)]
        return [_orden("sitio", f"Abrir la página {direccion}", direccion=direccion, nombre=direccion)]
    ordenes = []
    for parte in _partir(objetivo, r"\s*(?:,|;|\by\b|\be\b)\s*"):
        parte = _quitar_articulos(parte)
        if not parte.n:
            continue
        sitio = buscar_sitio(parte.n)
        if sitio:
            ordenes.append(
                _orden("sitio", f"Abrir la página de {sitio[0]}", direccion=sitio[1], nombre=sitio[0])
            )
            continue
        clave = buscar_app(parte.n)
        if clave:
            ordenes.append(_orden("abrir_app", f"Abrir {CATALOGO[clave].nombre}", clave=clave))
            continue
        ordenes.append(_orden("abrir_app", f"Abrir «{parte.o}»", termino=parte.o))
    return ordenes or None


def _volumen(par):
    n = par.n
    if re.search(r"\b(?:volumen|sonido|audio)\b", n):
        if re.search(r"\b(?:sube|subir|aumenta|aumentar|mas|alto|fuerte|subele)\b", n):
            return [_orden("volumen", "Subir el volumen", accion="subir")]
        if re.search(r"\b(?:baja|bajar|disminuye|reduce|menos|bajo|bajale)\b", n):
            return [_orden("volumen", "Bajar el volumen", accion="bajar")]
        if re.search(r"\b(?:silencia|silenciar|mute|quita|quitar|apaga|apagar|mutea)\b", n):
            return [_orden("volumen", "Silenciar el sonido", accion="silenciar")]
    if re.search(r"\b(?:silencia|silenciar|mutea|mute)\b", n):
        return [_orden("volumen", "Silenciar el sonido", accion="silenciar")]
    return None


def _abrir_ultima(par):
    if re.match(r"(?:abrela|abrelo|abrelas|abrelos)\b", par.n):
        return [_orden("abrir_ultima", "Abrir la carpeta que acabo de crear")]
    return None


def _cerrar(par):
    if re.match(r"(?:cierra|cerrar|cierralo|cierrala)\b", par.n):
        return [_orden("cerrar_ventana", "Cerrar la ventana actual")]
    return None


def _escribir(par):
    m = re.match(r"(?:escribe|escribir|teclea|teclear|digita|redacta)\s+(.+)$", par.n)
    if not m:
        return None
    texto = par.o[m.start(1): m.end(1)].strip(" \"“”«»")
    if not texto:
        return None
    return [_orden("escribir", f"Escribir «{texto}»", texto=texto)]


def _pregunta(par):
    if re.match(
        r"(?:que|quien|quienes|como|cuando|donde|cuanto|cuantos|cuanta|cuantas|cual|cuales|por que|porque|para que)\b",
        par.n,
    ):
        consulta = par.quitar(r"[¿?¡!]").o
        return [_orden("buscar_web", f"Buscar «{consulta}» en internet", consulta=consulta, navegador="chrome")]
    return None


REGLAS = (
    _captura,
    _crear_carpeta,
    _abrir_carpeta,
    _youtube,
    _buscar,
    _volumen,
    _escritorio,
    _abrir_ultima,
    _abrir,
    _cerrar,
    _escribir,
    _pregunta,
)


def _clausula(par):
    par = _sin_rellenos(par)
    if not par.n:
        return []
    for regla in REGLAS:
        ordenes = regla(par)
        if ordenes:
            for orden in ordenes:
                orden.texto = par.o
            return ordenes
    return [Orden("desconocido", {}, f"No entendí: «{par.o}»", par.o)]


def interpretar(texto):
    par = Par(normalizar(texto), texto).limpio()
    ordenes = []
    for segmento in _segmentar(par):
        ordenes.extend(_clausula(segmento))
    return ordenes
