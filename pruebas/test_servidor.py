import http.cookiejar
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from servidor import base_datos, config, servidor


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def abrir(sin_redireccion=False):
    jar = http.cookiejar.CookieJar()
    manejadores = [urllib.request.HTTPCookieProcessor(jar)]
    if sin_redireccion:
        manejadores.append(SinRedireccion())
    return urllib.request.build_opener(*manejadores), jar


class ServidorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.IA_ACTIVA = False
        config.GEMINI_API_KEY = ""
        cls.carpeta = config.RAIZ / ".pruebas_tmp"
        cls.carpeta.mkdir(exist_ok=True)
        cls.ruta_db = cls.carpeta / f"prueba_{os.getpid()}_{time.time_ns()}.db"
        cls.servidor = servidor.crear_servidor("127.0.0.1", 0, cls.ruta_db)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        cls.contador = 0

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.hilo.join(timeout=3)
        for sufijo in ("", "-wal", "-shm"):
            try:
                Path(str(cls.ruta_db) + sufijo).unlink(missing_ok=True)
            except OSError:
                pass

    # --- Ayudas ----------------------------------------------------------
    def _telefono(self):
        type(self).contador += 1
        return f"9999{self.contador:04d}"

    def _json(self, metodo, ruta, datos=None, token=None):
        cuerpo = json.dumps(datos).encode() if datos is not None else None
        cabeceras = {"Content-Type": "application/json"} if datos is not None else {}
        if token:
            cabeceras["Authorization"] = "Bearer " + token
        solicitud = urllib.request.Request(
            self.base + ruta, data=cuerpo, headers=cabeceras, method=metodo
        )
        try:
            with urllib.request.urlopen(solicitud, timeout=6) as respuesta:
                return respuesta.status, json.loads(respuesta.read().decode() or "{}")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode() or "{}")

    def _get(self, ruta, token=None, op=None, sin_redireccion=False):
        if op is None:
            op, _ = abrir(sin_redireccion)
        cabeceras = {"Authorization": "Bearer " + token} if token else {}
        solicitud = urllib.request.Request(self.base + ruta, headers=cabeceras)
        try:
            with op.open(solicitud, timeout=6) as respuesta:
                return respuesta.status, respuesta.read().decode(), respuesta.geturl()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(), error.headers.get("Location", "")

    def _form(self, op, ruta, datos):
        cuerpo = urllib.parse.urlencode(datos).encode()
        solicitud = urllib.request.Request(
            self.base + ruta,
            data=cuerpo,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with op.open(solicitud, timeout=6) as respuesta:
                return respuesta.status, respuesta.read().decode(), respuesta.geturl()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(), error.headers.get("Location", "")

    @staticmethod
    def _csrf(html):
        coincidencia = re.search(r'name="_csrf" value="([^"]+)"', html)
        if not coincidencia:
            raise AssertionError("No encontré el token CSRF en la página.")
        return coincidencia.group(1)

    def _registrar(self, telefono=None, clave="1234", nombre="Persona de Prueba"):
        telefono = telefono or self._telefono()
        codigo, datos = self._json(
            "POST",
            "/api/registro",
            {
                "telefono": telefono,
                "nombre": nombre,
                "clave": clave,
                "clave2": clave,
                "edad": 60,
                "ciudad": "Tegucigalpa",
                "experiencia": "poco",
                "consentimiento": True,
            },
        )
        self.assertEqual(codigo, 201, datos)
        return telefono, clave, datos["token"], datos["usuario"]

    def _admin(self):
        op, _ = abrir()
        _, html, _ = self._get("/admin/entrar", op=op)
        csrf = self._csrf(html)
        codigo, cuerpo, url = self._form(
            op,
            "/admin/entrar",
            {"_csrf": csrf, "usuario": config.ADMIN_USUARIO, "clave": config.ADMIN_CLAVE},
        )
        self.assertEqual(codigo, 200)
        self.assertTrue(url.endswith("/admin"), url)
        return op

    # --- Pruebas ---------------------------------------------------------
    def test_salud(self):
        codigo, datos = self._json("GET", "/api/estado")
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["app"], "PasoAPaso")
        self.assertFalse(datos["ia_configurada"])

    def test_paginas_publicas_sin_placeholders(self):
        for ruta in ("/", "/entrar", "/registro", "/privacidad", "/soporte/"):
            codigo, html, _ = self._get(ruta)
            self.assertEqual(codigo, 200, ruta)
            self.assertNotIn("{{", html, ruta)

    def test_registro_login_y_perfil(self):
        telefono, clave, token, usuario = self._registrar(nombre="Ana de Prueba")
        self.assertEqual(usuario["telefono"], telefono)
        codigo, perfil = self._json("GET", "/api/perfil", token=token)
        self.assertEqual(codigo, 200)
        self.assertEqual(perfil["usuario"]["nombre"], "Ana de Prueba")

        codigo, datos = self._json(
            "POST", "/api/login", {"telefono": telefono, "clave": clave}
        )
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["token"])

        codigo, _ = self._json(
            "POST", "/api/login", {"telefono": telefono, "clave": "0000"}
        )
        self.assertEqual(codigo, 401)

        codigo, _ = self._json(
            "POST",
            "/api/registro",
            {"telefono": telefono, "nombre": "Otra", "clave": clave, "clave2": clave, "consentimiento": True},
        )
        self.assertEqual(codigo, 409)

    def test_interpretar_y_resultado(self):
        _, _, token, _ = self._registrar()
        codigo, datos = self._json(
            "POST",
            "/api/interpretar",
            {"texto": "abre la calculadora y el bloc de notas", "origen": "voz"},
            token=token,
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(datos["estado"], "pendiente")
        self.assertEqual([o["tipo"] for o in datos["ordenes"]], ["abrir_app", "abrir_app"])
        self.assertFalse(datos["ia_usada"])
        prompt_id = datos["prompt_id"]

        codigo, datos = self._json(
            "POST",
            f"/api/prompts/{prompt_id}/resultado",
            {"estado": "completado", "duracion_ms": 1500, "acciones": datos["ordenes"]},
            token=token,
        )
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["ok"])

        codigo, historial = self._json("GET", "/api/historial", token=token)
        self.assertEqual(codigo, 200)
        self.assertEqual(historial["consultas"][0]["estado"], "completado")

    def test_consulta_sin_entender(self):
        _, _, token, _ = self._registrar()
        codigo, datos = self._json(
            "POST",
            "/api/interpretar",
            {"texto": "hazme un favor raro que no entiendo", "origen": "texto"},
            token=token,
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(datos["estado"], "sin_entender")
        self.assertEqual(datos["ordenes"][0]["tipo"], "desconocido")
        self.assertTrue(datos["sugerencias"])

    def test_offline(self):
        _, _, token, _ = self._registrar()
        codigo, datos = self._json(
            "POST",
            "/api/prompts/offline",
            {
                "texto": "toma una captura",
                "origen": "voz",
                "estado": "completado",
                "ordenes": [{"tipo": "captura", "datos": {}, "resumen": "Tomar captura"}],
                "creado_en": base_datos.ahora_utc(),
                "duracion_ms": 900,
            },
            token=token,
        )
        self.assertEqual(codigo, 200, datos)
        self.assertTrue(datos["prompt_id"])
        _, historial = self._json("GET", "/api/historial", token=token)
        self.assertEqual(historial["consultas"][0]["origen"], "offline")

    def test_permisos(self):
        codigo, _ = self._json("GET", "/api/perfil")
        self.assertEqual(codigo, 401)

        _, _, token1, _ = self._registrar()
        _, datos = self._json(
            "POST", "/api/interpretar", {"texto": "abre la calculadora"}, token=token1
        )
        prompt_id = datos["prompt_id"]
        _, _, token2, _ = self._registrar()
        codigo, _ = self._json(
            "POST",
            f"/api/prompts/{prompt_id}/resultado",
            {"estado": "completado"},
            token=token2,
        )
        self.assertEqual(codigo, 404)

        codigo, _, ubicacion = self._get("/admin", sin_redireccion=True)
        self.assertEqual(codigo, 303)
        self.assertIn("/admin/entrar", ubicacion)

        op, _ = abrir(sin_redireccion=True)
        codigo, _, _ = self._form(op, "/admin/entrar", {"usuario": "admin", "clave": "x"})
        self.assertEqual(codigo, 403)

    def test_admin_panel_y_csv(self):
        _, _, token, usuario = self._registrar(nombre="Carlos Admin")
        self._json(
            "POST", "/api/interpretar", {"texto": "toma una captura"}, token=token
        )
        op = self._admin()
        for ruta in (
            "/admin",
            "/admin/usuarios",
            f"/admin/usuarios/{usuario['id']}",
            "/admin/prompts",
            "/admin/ia",
            "/admin/clave",
        ):
            codigo, html, _ = self._get(ruta, op=op)
            self.assertEqual(codigo, 200, ruta)
            self.assertNotIn("{{", html, ruta)
            self.assertIn("PasoAPaso", html, ruta)
        codigo, html, _ = self._get("/admin/usuarios", op=op)
        self.assertIn("Carlos Admin", html)
        codigo, csv, _ = self._get("/admin/exportar.csv", op=op)
        self.assertEqual(codigo, 200)
        self.assertIn("ID;Fecha;Usuario", csv)

    def test_portal_web(self):
        op, _ = abrir()
        _, html, _ = self._get("/registro", op=op)
        csrf = self._csrf(html)
        telefono = self._telefono()
        codigo, cuerpo, url = self._form(
            op,
            "/registro",
            {
                "_csrf": csrf,
                "telefono": telefono,
                "nombre": "Luisa Web",
                "clave": "4321",
                "clave2": "4321",
                "edad": "55",
                "ciudad": "Comayagua",
                "experiencia": "poco",
                "consentimiento": "1",
            },
        )
        self.assertEqual(codigo, 200)
        self.assertIn("/portal", url)
        self.assertIn("Luisa Web", cuerpo)
        codigo, html, _ = self._get("/portal", op=op)
        self.assertEqual(codigo, 200)
        self.assertIn("Luisa Web", html)
        self.assertNotIn("{{", html)

    def test_csrf_admin_incorrecto(self):
        op, _ = abrir()
        codigo, _, _ = self._form(
            op,
            "/admin/entrar",
            {"_csrf": "inventado", "usuario": "admin", "clave": config.ADMIN_CLAVE},
        )
        self.assertEqual(codigo, 403)


if __name__ == "__main__":
    unittest.main()
