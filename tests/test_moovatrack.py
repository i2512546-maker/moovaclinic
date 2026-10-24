# ============================================================
# Tests de MoovaTrack (prototipo con datos simulados).
# ============================================================

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-prueba")
os.environ.setdefault("API_KEY", "clave-api")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway  # noqa: E402

RUTA = "/api/moovatrack/lectura"


class MoovaTrackTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _sesion(self, rol="terapeuta"):
        with self.client.session_transaction() as s:
            s["usuario_id"] = 7
            s["usuario_nombre"] = "Jordy"
            s["rol"] = rol

    def test_lectura_sin_sesion_responde_401_en_json(self):
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.is_json)

    def test_lectura_con_sesion_trae_las_claves(self):
        self._sesion()
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 200)
        datos = r.get_json()
        for clave in ("success", "simulado", "angulo", "fuerza", "timestamp"):
            self.assertIn(clave, datos)

    def test_los_datos_estan_marcados_como_simulados(self):
        self._sesion()
        self.assertIs(self.client.get(RUTA).get_json()["simulado"], True)

    def test_angulo_y_fuerza_siempre_en_rango(self):
        self._sesion("admin")
        for _ in range(60):
            datos = self.client.get(RUTA).get_json()
            self.assertGreaterEqual(datos["angulo"], 0)
            self.assertLessEqual(datos["angulo"], 180)
            self.assertGreaterEqual(datos["fuerza"], 0)

    def test_timestamp_en_formato_utc(self):
        self._sesion()
        self.assertTrue(self.client.get(RUTA).get_json()["timestamp"].endswith("Z"))

    def test_pagina_sin_sesion_redirige_al_login(self):
        r = self.client.get("/moovatrack")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_pagina_con_sesion_carga_el_bundle(self):
        self._sesion("terapeuta")
        r = self.client.get("/moovatrack")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('id="moovatrack-root"', html)
        self.assertIn("react/moovatrack.js", html)

    def test_interfaz_enlaza_a_moovatrack(self):
        self._sesion("terapeuta")
        with patch("gateway.app.citas_client.get", return_value=({"success": True, "citas": []}, 200)), \
                patch("gateway.app.pacientes_client.get", return_value=({"success": True, "pacientes": []}, 200)):
            r = self.client.get("/interfaz")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/moovatrack", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
