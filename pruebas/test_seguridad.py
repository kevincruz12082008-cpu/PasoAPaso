import time
import unittest

from servidor import config, seguridad


class SeguridadTest(unittest.TestCase):
    def test_telefono(self):
        self.assertEqual(seguridad.normalizar_telefono("+504 9999-1234"), "50499991234")
        self.assertTrue(seguridad.telefono_valido("99991234"))
        self.assertFalse(seguridad.telefono_valido("123"))
        self.assertFalse(seguridad.telefono_valido("1" * 16))

    def test_pin(self):
        self.assertTrue(seguridad.pin_valido("1234"))
        self.assertTrue(seguridad.pin_valido("12345678"))
        self.assertFalse(seguridad.pin_valido("123"))
        self.assertFalse(seguridad.pin_valido("abcd"))
        self.assertEqual(seguridad.normalizar_pin("12-34"), "1234")

    def test_hash(self):
        guardado = seguridad.hash_clave("1234")
        self.assertTrue(guardado.startswith("pbkdf2_sha256$"))
        self.assertTrue(seguridad.verificar_clave("1234", guardado))
        self.assertFalse(seguridad.verificar_clave("4321", guardado))
        self.assertFalse(seguridad.verificar_clave("1234", "basura"))
        self.assertNotEqual(guardado, seguridad.hash_clave("1234"))

    def test_tokens(self):
        token = seguridad.crear_token({"sub": "7", "rol": "usuario"}, 1)
        datos = seguridad.leer_token(token)
        self.assertEqual(datos["sub"], "7")
        self.assertEqual(datos["rol"], "usuario")
        self.assertIsNone(seguridad.leer_token(token[:-1] + ("a" if token[-1] != "a" else "b")))
        expirado = seguridad.crear_token({"sub": "7"}, -1)
        self.assertIsNone(seguridad.leer_token(expirado))
        self.assertIsNone(seguridad.leer_token("no-es-un-token"))

    def test_cookie(self):
        cookie = seguridad.hacer_cookie("pa_sesion", "abc", 60, True)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("Max-Age=60", cookie)

    def test_limitador(self):
        limitador = seguridad.Limitador(2, 60)
        self.assertTrue(limitador.permitido("x"))
        limitador.fallo("x")
        self.assertTrue(limitador.permitido("x"))
        limitador.fallo("x")
        self.assertFalse(limitador.permitido("x"))
        limitador.limpiar("x")
        self.assertTrue(limitador.permitido("x"))

    def test_texto(self):
        self.assertEqual(seguridad.limpiar_texto("  hola\x00  mundo  "), "hola mundo")
        self.assertEqual(seguridad.limpiar_nombre("  María   López  "), "María López")
        self.assertEqual(len(seguridad.limpiar_texto("a" * 1000, 50)), 50)
        self.assertEqual(seguridad.normalizar_experiencia("otra"), "poco")


if __name__ == "__main__":
    unittest.main()
