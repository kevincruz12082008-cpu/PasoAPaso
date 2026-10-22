import unittest

from pasoapaso.nucleo.interprete import interpretar


class InterpreteTest(unittest.TestCase):
    def tipos(self, texto):
        return [orden.tipo for orden in interpretar(texto)]

    def test_abrir_varias_apps(self):
        ordenes = interpretar("abre la calculadora y el bloc de notas")
        self.assertEqual([o.tipo for o in ordenes], ["abrir_app", "abrir_app"])
        self.assertEqual(ordenes[0].datos["clave"], "calculadora")
        self.assertEqual(ordenes[1].datos["clave"], "bloc")

    def test_carpeta_y_abrirla(self):
        ordenes = interpretar("crea una carpeta llamada Tareas en el escritorio y ábrela")
        self.assertEqual(ordenes[0].tipo, "crear_carpeta")
        self.assertEqual(ordenes[0].datos["nombre"], "Tareas")
        self.assertEqual(ordenes[0].datos["ubicacion"], "escritorio")
        self.assertEqual(ordenes[1].tipo, "abrir_ultima")

    def test_captura(self):
        self.assertEqual(self.tipos("toma una captura de pantalla"), ["captura"])

    def test_buscar(self):
        ordenes = interpretar("busca recetas de pupusas en google")
        self.assertEqual(ordenes[0].tipo, "buscar_web")
        self.assertIn("pupusas", ordenes[0].datos["consulta"])

    def test_youtube(self):
        ordenes = interpretar("reproduce música de Juan Gabriel en youtube")
        self.assertEqual(ordenes[0].tipo, "youtube")
        self.assertTrue(ordenes[0].datos["reproducir"])
        self.assertIn("Juan Gabriel", ordenes[0].datos["consulta"])

    def test_escribir(self):
        ordenes = interpretar('escribe "hola, mundo"')
        self.assertEqual(ordenes[0].tipo, "escribir")
        self.assertEqual(ordenes[0].datos["texto"], "hola, mundo")

    def test_volumen_y_escritorio(self):
        self.assertEqual(self.tipos("sube el volumen"), ["volumen"])
        self.assertEqual(self.tipos("muestra el escritorio"), ["escritorio"])

    def test_sitio(self):
        ordenes = interpretar("abre facebook.com")
        self.assertEqual(ordenes[0].tipo, "sitio")
        self.assertIn("facebook", ordenes[0].datos["direccion"])

    def test_desconocido(self):
        ordenes = interpretar("hazme un favor raro")
        self.assertEqual(ordenes[0].tipo, "desconocido")

    def test_vacio(self):
        self.assertEqual(interpretar("   "), [])


if __name__ == "__main__":
    unittest.main()
