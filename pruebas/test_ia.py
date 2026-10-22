import os
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from servidor import base_datos, config, ia


class IATest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.carpeta = config.RAIZ / ".pruebas_tmp"
        cls.carpeta.mkdir(exist_ok=True)
        cls.ruta = cls.carpeta / f"ia_{os.getpid()}_{time.time_ns()}.db"
        base_datos.inicializar(cls.ruta)
        config.RUTA_DB = cls.ruta
        config.IA_ACTIVA = True
        config.GEMINI_API_KEY = "clave-de-prueba"
        base_datos.guardar_ajuste("ia_activa", "1")

    @classmethod
    def tearDownClass(cls):
        for sufijo in ("", "-wal", "-shm"):
            try:
                Path(str(cls.ruta) + sufijo).unlink(missing_ok=True)
            except OSError:
                pass

    def test_reglas_locales_no_llaman_ia(self):
        with mock.patch.object(ia, "_llamar_gemini") as llamar:
            resultado = ia.resolver("abre la calculadora")
            llamar.assert_not_called()
        self.assertEqual(resultado.motivo, "local")
        self.assertEqual(resultado.ordenes[0].tipo, "abrir_app")

    def test_ia_cuando_las_reglas_no_entienden(self):
        crudo = [
            {
                "tipo": "abrir_app",
                "datos": {"clave": "calculadora"},
                "resumen": "Abrir la Calculadora",
            }
        ]
        with mock.patch.object(ia, "_llamar_gemini", return_value=crudo):
            resultado = ia.resolver("quiero que me abras la calculadora")
        self.assertTrue(resultado.ia_usada)
        self.assertEqual(resultado.motivo, "ia")
        self.assertEqual(resultado.ordenes[0].datos["clave"], "calculadora")

    def test_ia_invalida_cae_en_reglas(self):
        crudo = [{"tipo": "borrar_todo", "datos": {}}]
        with mock.patch.object(ia, "_llamar_gemini", return_value=crudo):
            resultado = ia.resolver("quiero que me abras la calculadora")
        self.assertFalse(resultado.ia_usada)
        self.assertEqual(resultado.motivo, "error_ia")
        self.assertEqual(resultado.ordenes[0].tipo, "desconocido")

    def test_ia_desactivada(self):
        base_datos.guardar_ajuste("ia_activa", "0")
        try:
            with mock.patch.object(ia, "_llamar_gemini") as llamar:
                resultado = ia.resolver("quiero que me abras la calculadora")
                llamar.assert_not_called()
            self.assertEqual(resultado.motivo, "ia_desactivada")
        finally:
            base_datos.guardar_ajuste("ia_activa", "1")

    def test_sin_clave(self):
        clave = config.GEMINI_API_KEY
        config.GEMINI_API_KEY = ""
        try:
            with mock.patch.object(ia, "_llamar_gemini") as llamar:
                resultado = ia.resolver("quiero que me abras la calculadora")
                llamar.assert_not_called()
            self.assertEqual(resultado.motivo, "sin_clave")
        finally:
            config.GEMINI_API_KEY = clave

    def test_extraer_json(self):
        self.assertEqual(ia._extraer_json('{"ordenes": []}'), {"ordenes": []})
        self.assertEqual(
            ia._extraer_json('```json\n{"ordenes": [1]}\n```'), {"ordenes": [1]}
        )
        with self.assertRaises(ia.ErrorIA):
            ia._extraer_json("no es json")


if __name__ == "__main__":
    unittest.main()
