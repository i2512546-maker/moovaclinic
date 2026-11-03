import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga


class LandingMarcaTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.client = self.app.test_client()

    def test_landing_activa_muestra_logo_y_promos(self):
        with patch("gateway.app.PROMO_ACTIVA", True):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("logo-moova-recortado.png", html)
        for i in range(1, 6):
            self.assertIn(f"promo{i}.jpg", html)

    def test_landing_inactiva_no_muestra_seccion(self):
        with patch("gateway.app.PROMO_ACTIVA", False):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertNotIn('id="promos"', html)


if __name__ == "__main__":
    unittest.main()
