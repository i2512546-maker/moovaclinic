# ============================================================
# Tests de S3: cabeceras de seguridad del gateway.
#
# Todas se fijan en un unico after_request, asi que se comprueban en
# varios tipos de respuesta: plantilla, redirect, 404 y error.
# ============================================================

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-prueba")
os.environ.setdefault("API_KEY", "clave-api")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import jsonify  # noqa: E402
from gateway.app import create_app as crear_gateway  # noqa: E402

CABECERAS_FIJAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class CabecerasFijasTest(unittest.TestCase):
    """Las tres cabeceras que van siempre."""

    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _comprobar(self, respuesta):
        for cabecera, valor in CABECERAS_FIJAS.items():
            self.assertEqual(
                respuesta.headers.get(cabecera), valor,
                f"{cabecera}: {respuesta.headers.get(cabecera)!r}",
            )

    def test_en_una_pagina_normal(self):
        self._comprobar(self.client.get("/"))

    def test_en_una_pagina_que_pide_sesion(self):
        # /interfaz sin sesion redirige a /login; la cabecera tiene que
        # viajar tambien en el redirect.
        self._comprobar(self.client.get("/interfaz"))

    def test_en_un_404(self):
        self._comprobar(self.client.get("/esto-no-existe"))

    def test_en_un_error_de_csrf(self):
        # Sin token y con XHR el errorhandler devuelve JSON 403.
        self.app.config["WTF_CSRF_ENABLED"] = True
        respuesta = self.client.post(
            "/login", data={"correo": "a@b.c", "clave": "x"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(respuesta.status_code, 403)
        self._comprobar(respuesta)

    def test_en_una_ruta_de_api(self):
        self._comprobar(self.client.get("/api/citas?dni=12345678&estado=programada"))

    def test_en_una_respuesta_que_la_ruta_ya_ha_marcado(self):
        # setdefault: lo que una ruta fije a proposito no se pisa.
        @self.app.route("/cabecera-propia")
        def _cabecera_propia():
            respuesta = jsonify({"ok": True})
            respuesta.headers["X-Frame-Options"] = "DENY"
            respuesta.headers["X-Content-Type-Options"] = "custom"
            return respuesta

        respuesta = self.client.get("/cabecera-propia")
        self.assertEqual(respuesta.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(respuesta.headers.get("X-Content-Type-Options"), "custom")
        # Las demas siguen puestas.
        self.assertEqual(
            respuesta.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin"
        )


class HSTSTest(unittest.TestCase):
    """Strict-Transport-Security solo en produccion."""

    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_no_se_envia_en_desarrollo(self):
        respuesta = self.client.get("/")
        self.assertIsNone(respuesta.headers.get("Strict-Transport-Security"))

    def test_no_se_envia_si_flask_env_esta_vacio(self):
        with patch.dict(os.environ, {"FLASK_ENV": ""}):
            respuesta = self.client.get("/")
        self.assertIsNone(respuesta.headers.get("Strict-Transport-Security"))

    def test_se_envia_en_produccion(self):
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            respuesta = self.client.get("/")
        self.assertEqual(
            respuesta.headers.get("Strict-Transport-Security"), "max-age=31536000"
        )

    def test_se_envia_tambien_en_un_404(self):
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            respuesta = self.client.get("/esto-no-existe")
        self.assertEqual(
            respuesta.headers.get("Strict-Transport-Security"), "max-age=31536000"
        )


if __name__ == "__main__":
    unittest.main()
