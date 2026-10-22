from . import aplicaciones, carpetas, navegador, pantalla, sistema

ACCIONES = {
    "abrir_app": aplicaciones.abrir_app,
    "crear_carpeta": carpetas.crear_carpeta,
    "abrir_carpeta": carpetas.abrir_carpeta,
    "abrir_ultima": carpetas.abrir_ultima,
    "captura": pantalla.tomar_captura,
    "buscar_web": navegador.buscar_web,
    "youtube": navegador.reproducir_youtube,
    "sitio": navegador.abrir_sitio,
    "volumen": sistema.ajustar_volumen,
    "escritorio": sistema.mostrar_escritorio,
    "cerrar_ventana": sistema.cerrar_ventana,
    "escribir": sistema.escribir_texto,
}
