import time

import pyautogui

from ..acciones.registro import ACCIONES
from .guia import Cancelado

INTERRUPCIONES = (Cancelado, pyautogui.FailSafeException)


class Ejecutor:
    def __init__(self, guia):
        self.guia = guia

    def correr(self, ordenes):
        """Ejecuta las órdenes y devuelve un resumen para guardar en el servidor."""
        guia = self.guia
        resultado = {
            "completado": False,
            "errores": [],
            "acciones": [],
            "inicio": time.monotonic(),
        }
        try:
            guia.plan([orden.resumen for orden in ordenes])
            guia.pausar(2.5 + 1.0 * len(ordenes))
            total = len(ordenes)
            for numero, orden in enumerate(ordenes, 1):
                guia.iniciar_tarea(numero, total, orden.resumen)
                accion = ACCIONES.get(orden.tipo)
                if accion is None:
                    guia.decir(
                        "No entendí esta parte",
                        f"«{orden.texto}». Prueba escribirlo de otra forma, por ejemplo: abre la calculadora.",
                        tipo="aviso",
                    )
                    guia.pausar(3.5)
                    resultado["acciones"].append(
                        {
                            "tipo": orden.tipo,
                            "resumen": orden.resumen,
                            "ok": False,
                            "error": "Acción no reconocida",
                        }
                    )
                    continue
                try:
                    accion(guia, orden)
                except INTERRUPCIONES:
                    raise
                except Exception as error:
                    mensaje = str(error) or error.__class__.__name__
                    guia.decir("Algo salió mal en este paso", mensaje, tipo="aviso")
                    guia.pausar(3.5)
                    resultado["errores"].append(f"{orden.resumen}: {mensaje}")
                    resultado["acciones"].append(
                        {
                            "tipo": orden.tipo,
                            "resumen": orden.resumen,
                            "ok": False,
                            "error": mensaje[:300],
                        }
                    )
                else:
                    resultado["acciones"].append(
                        {
                            "tipo": orden.tipo,
                            "resumen": orden.resumen,
                            "ok": True,
                            "error": "",
                        }
                    )
                guia.pausar(1.5)
            guia.finalizar(True)
            resultado["completado"] = True
        except INTERRUPCIONES:
            guia.finalizar(False)
            resultado["completado"] = False
        finally:
            resultado["duracion_ms"] = int((time.monotonic() - resultado["inicio"]) * 1000)
        return resultado
