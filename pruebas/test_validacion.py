import unittest

from pasoapaso.nucleo.validacion import validar_ordenes


class ValidacionTest(unittest.TestCase):
    def test_abrir_app_catalogo(self):
        ordenes = validar_ordenes(
            [{"tipo": "abrir_app", "datos": {"clave": "calculadora"}, "resumen": "Abrir calculadora"}]
        )
        self.assertEqual(len(ordenes), 1)
        self.assertEqual(ordenes[0].tipo, "abrir_app")
        self.assertEqual(ordenes[0].datos["clave"], "calculadora")

    def test_abrir_app_termino(self):
        ordenes = validar_ordenes(
            [{"tipo": "abrir_app", "datos": {"termino": 'Photo "Shop" <x>'}}]
        )
        self.assertEqual(ordenes[0].datos["termino"], "Photo Shop x")

    def test_crear_carpeta_limpia(self):
        ordenes = validar_ordenes(
            [
                {
                    "tipo": "crear_carpeta",
                    "datos": {"nombre": "Tareas:/?*", "ubicacion": "el escritorio"},
                }
            ]
        )
        self.assertEqual(ordenes[0].datos["nombre"], "Tareas")
        self.assertEqual(ordenes[0].datos["ubicacion"], "escritorio")

    def test_crear_carpeta_sin_nombre(self):
        ordenes = validar_ordenes([{"tipo": "crear_carpeta", "datos": {}}])
        self.assertEqual(ordenes[0].datos["nombre"], "Nueva carpeta")

    def test_sitio_seguro(self):
        ordenes = validar_ordenes(
            [{"tipo": "sitio", "datos": {"direccion": "facebook.com", "nombre": "Facebook"}}]
        )
        self.assertEqual(ordenes[0].datos["direccion"], "https://facebook.com/")

    def test_sitio_peligroso(self):
        for direccion in (
            "javascript:alert(1)",
            "file:///C:/Windows/System32",
            "http://127.0.0.1/admin",
            "http://192.168.1.1/",
            "http://localhost:8000/",
            "http://ejemplo.com:99999/",
        ):
            with self.subTest(direccion=direccion):
                with self.assertRaises(ValueError):
                    validar_ordenes([{"tipo": "sitio", "datos": {"direccion": direccion}}])

    def test_tipos_y_campos_invalidos(self):
        with self.assertRaises(ValueError):
            validar_ordenes([{"tipo": "borrar_todo", "datos": {}}])
        with self.assertRaises(ValueError):
            validar_ordenes([{"tipo": "volumen", "datos": {"accion": "explotar"}}])
        with self.assertRaises(ValueError):
            validar_ordenes([{"tipo": "buscar_web", "datos": {}}])
        with self.assertRaises(ValueError):
            validar_ordenes([{"tipo": "escribir", "datos": {"texto": "   "}}])

    def test_limite_ordenes(self):
        crudas = [
            {"tipo": "captura", "datos": {}, "resumen": f"Captura {i}"} for i in range(20)
        ]
        self.assertEqual(len(validar_ordenes(crudas, maximo=8)), 8)

    def test_campos_extra_se_descartan(self):
        ordenes = validar_ordenes(
            [{"tipo": "captura", "datos": {"peligro": "rm -rf"}, "resumen": "Captura"}]
        )
        self.assertEqual(ordenes[0].datos, {})

    def test_volumen_y_youtube(self):
        ordenes = validar_ordenes(
            [
                {"tipo": "volumen", "datos": {"accion": "subir"}},
                {"tipo": "youtube", "datos": {"consulta": "cumbias", "reproducir": True}},
            ]
        )
        self.assertEqual(len(ordenes), 2)
        self.assertTrue(ordenes[1].datos["reproducir"])

    def test_orden_desconocida_sola(self):
        with self.assertRaises(ValueError):
            validar_ordenes([{"tipo": "desconocido", "datos": {}}])


if __name__ == "__main__":
    unittest.main()
