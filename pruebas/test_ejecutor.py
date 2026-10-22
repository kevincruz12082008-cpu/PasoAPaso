import unittest
from unittest import mock

from pasoapaso.nucleo import ejecutor as modulo_ejecutor
from pasoapaso.nucleo.ejecutor import Ejecutor
from pasoapaso.nucleo.guia import Cancelado
from pasoapaso.nucleo.interprete import Orden


class GuiaFalsa:
    def __init__(self):
        self.finalizado = None
        self.mensajes = []
        self.tareas = []

    def plan(self, resumenes):
        self.resumenes = list(resumenes)

    def pausar(self, segundos):
        pass

    def iniciar_tarea(self, numero, total, resumen):
        self.tareas.append((numero, total, resumen))

    def decir(self, titulo, detalle="", teclas=(), tipo="paso"):
        self.mensajes.append((titulo, detalle, tipo))

    def finalizar(self, completado):
        self.finalizado = completado


class EjecutorTest(unittest.TestCase):
    def test_accion_correcta(self):
        guia = GuiaFalsa()
        llamadas = []

        def accion(g, orden):
            llamadas.append(orden.tipo)

        with mock.patch.object(modulo_ejecutor, "ACCIONES", {"captura": accion}):
            resultado = Ejecutor(guia).correr([Orden("captura", {}, "Tomar captura", "toma captura")])

        self.assertTrue(resultado["completado"])
        self.assertEqual(resultado["errores"], [])
        self.assertEqual(len(resultado["acciones"]), 1)
        self.assertTrue(resultado["acciones"][0]["ok"])
        self.assertEqual(llamadas, ["captura"])
        self.assertTrue(guia.finalizado)

    def test_accion_con_error(self):
        guia = GuiaFalsa()

        def accion(g, orden):
            raise RuntimeError("falló el teclado")

        with mock.patch.object(modulo_ejecutor, "ACCIONES", {"captura": accion}):
            resultado = Ejecutor(guia).correr([Orden("captura", {}, "Tomar captura", "toma captura")])

        self.assertTrue(resultado["completado"])
        self.assertEqual(len(resultado["errores"]), 1)
        self.assertIn("teclado", resultado["errores"][0])
        self.assertFalse(resultado["acciones"][0]["ok"])

    def test_accion_desconocida(self):
        guia = GuiaFalsa()
        with mock.patch.object(modulo_ejecutor, "ACCIONES", {}):
            resultado = Ejecutor(guia).correr([Orden("rara", {}, "Rara", "rara")])
        self.assertTrue(resultado["completado"])
        self.assertFalse(resultado["acciones"][0]["ok"])
        self.assertTrue(any("No entendí" in m[0] for m in guia.mensajes))

    def test_cancelado(self):
        guia = GuiaFalsa()

        def accion(g, orden):
            raise Cancelado()

        with mock.patch.object(modulo_ejecutor, "ACCIONES", {"captura": accion}):
            resultado = Ejecutor(guia).correr([Orden("captura", {}, "Tomar captura", "toma captura")])

        self.assertFalse(resultado["completado"])
        self.assertFalse(guia.finalizado)


if __name__ == "__main__":
    unittest.main()
