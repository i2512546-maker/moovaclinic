# ============================================================
# Tests de /panel_admin/kpis.json (panel de KPIs en React).
#
# La ruta alimenta al componente React: sin sesion debe responder 401 y
# sin rol admin 403, ambos en JSON. Un redirect a /login haria que el
# navegador reciba HTML y el panel falle al leer la respuesta.
# El servicio de citas se parchea: estos tests nunca tocan MySQL.
# ============================================================

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-prueba")
os.environ.setdefault("API_KEY", "clave-api")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway  # noqa: E402

RUTA = "/panel_admin/kpis.json"

# Forma real de lo que devuelve GET /api/kpis del servicio de citas.
RESPUESTA_KPIS = {
    "success": True,
    "resumen": {
        "total_citas": 10, "citas_completadas": 6, "citas_programadas": 2,
        "citas_canceladas": 2, "tasa_completadas": 60.0, "tasa_cancelacion": 20.0,
        "ingresos_confirmados": 480.0, "ingresos_pendientes": 120.0,
        "paquetes_vendidos": 3, "sesiones_consumidas": 6,
    },
    "por_terapeuta": [
        {"terapeuta_id": 1, "terapeuta_nombre": "Dra. Becky", "total_citas": 10,
         "citas_completadas": 6, "tasa_completadas": 60.0, "ingresos": 480.0},
    ],
}


class KpisJsonTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _sesion(self, rol):
        with self.client.session_transaction() as s:
            s["usuario_id"] = 1
            s["usuario_nombre"] = "Ana"
            s["rol"] = rol

    def test_sin_sesion_responde_401_en_json(self):
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.is_json)
        self.assertFalse(r.get_json()["success"])

    def test_terapeuta_no_es_admin_responde_403_en_json(self):
        self._sesion("terapeuta")
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.is_json)

    def test_admin_recibe_la_forma_esperada(self):
        self._sesion("admin")
        with patch("gateway.app.citas_client.get", return_value=(RESPUESTA_KPIS, 200)):
            r = self.client.get(RUTA + "?desde=2026-01-01&hasta=2026-02-01")
        self.assertEqual(r.status_code, 200)
        datos = r.get_json()
        for clave in ("desde", "hasta", "resumen", "por_terapeuta", "error"):
            self.assertIn(clave, datos)
        self.assertEqual(datos["desde"], "2026-01-01")
        self.assertEqual(datos["hasta"], "2026-02-01")
        self.assertEqual(datos["resumen"]["total_citas"], 10)
        self.assertEqual(datos["por_terapeuta"][0]["terapeuta_nombre"], "Dra. Becky")
        self.assertIsNone(datos["error"])

    def test_si_el_servicio_falla_devuelve_error_y_no_revienta(self):
        self._sesion("admin")
        with patch("gateway.app.citas_client.get", side_effect=RuntimeError("caido")):
            r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 200)
        datos = r.get_json()
        self.assertEqual(datos["error"], "Servicio de KPIs no disponible")
        self.assertIsNone(datos["resumen"])
        self.assertEqual(datos["por_terapeuta"], [])

    def test_la_pagina_html_sigue_exigiendo_admin(self):
        r = self.client.get("/panel_admin/kpis")
        self.assertEqual(r.status_code, 302)

    def test_la_pagina_carga_el_bundle_react(self):
        self._sesion("admin")
        r = self.client.get("/panel_admin/kpis")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('id="kpis-root"', html)
        self.assertIn("react/kpis.js", html)
        self.assertIn(RUTA, html)


class BundlesReactTest(unittest.TestCase):
    """Los bundles compilados van commiteados: se comprueba que se sirvan y no esten vacios."""

    def setUp(self):
        self.client = crear_gateway().test_client()

    def test_los_dos_bundles_se_sirven_y_traen_react(self):
        for nombre in ("kpis.js", "moovatrack.js"):
            r = self.client.get(f"/static/react/{nombre}")
            self.assertEqual(r.status_code, 200, nombre)
            # React + recharts pesan cientos de KB; un bundle vacio pesa unos pocos.
            self.assertGreater(len(r.data), 100_000, nombre)
            r.close()

    def test_los_bundles_son_distintos(self):
        a = self.client.get("/static/react/kpis.js").data
        b = self.client.get("/static/react/moovatrack.js").data
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
