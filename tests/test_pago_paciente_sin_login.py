"""El paciente puede completar el pago y ver el retorno sin cuenta."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402


class PagoPacienteSinLoginTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()

    @staticmethod
    def _pagos_get(estado_pago="pendiente"):
        def pagos_get(url, *args, **kwargs):
            return {
                "pago": {
                    "estado_pago": estado_pago,
                    "monto": 80.0,
                    "metodo_pago": "yape",
                },
            }, 200

        return pagos_get

    @staticmethod
    def _citas_get(url, *args, **kwargs):
        return {
            "cita": {
                "id": 55,
                "nombre": "Ana",
                "apellido": "Perez",
                "estado": "programada",
                "fecha_cita": "2026-10-24",
                "terapeuta": "Terapeuta",
                "Especialidad": "Fisioterapia",
            },
        }, 200

    def _get_pago(self, url, estado_pago="pendiente"):
        with patch.object(
            ga.pagos_client, "get", side_effect=self._pagos_get(estado_pago)
        ), patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            return self.cliente.get(url)

    def _set_cita_pendiente(self, cita_id=55):
        with self.cliente.session_transaction() as session:
            session["cita_pendiente_id"] = cita_id

    def _assert_citas_redirect(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/citas"))
        self.assertNotIn("/login", response.headers["Location"])

    def test_paciente_puede_abrir_su_pago(self):
        self._set_cita_pendiente()
        response = self._get_pago("/pago?cita_id=55")
        self.assertEqual(response.status_code, 200)

    def test_no_puede_abrir_pago_de_otra_cita(self):
        self._set_cita_pendiente()
        self._assert_citas_redirect(self._get_pago("/pago?cita_id=56"))

    def test_pago_sin_cita_en_sesion_redirige_a_citas(self):
        self._assert_citas_redirect(self._get_pago("/pago?cita_id=55"))

    def test_pago_exige_id_numerico(self):
        for url in ("/pago", "/pago?cita_id=abc", "/pago?cita_id=5%20OR%201"):
            with self.subTest(url=url):
                self._assert_citas_redirect(self._get_pago(url))

    def test_retorno_pagado_se_puede_recargar(self):
        self._set_cita_pendiente()
        with patch.object(
            ga.pagos_client, "get", side_effect=self._pagos_get("pagado")
        ), patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            first_response = self.cliente.get("/retorno?cita_id=55")
            second_response = self.cliente.get("/retorno?cita_id=55")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        with self.cliente.session_transaction() as session:
            self.assertNotIn("cita_pendiente_id", session)
            self.assertEqual(session["cita_recien_pagada"], "55")

    def test_retorno_pendiente_redirige_a_pago(self):
        self._set_cita_pendiente()
        response = self._get_pago(
            "/retorno?cita_id=55", estado_pago="pendiente"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/pago?cita_id=55", response.headers["Location"])

    def test_retorno_no_autorizado_redirige_a_citas(self):
        self._set_cita_pendiente()
        self._assert_citas_redirect(self._get_pago("/retorno?cita_id=99"))

    def test_personal_logueado_conserva_acceso_a_pago(self):
        with self.cliente.session_transaction() as session:
            session["usuario_id"] = 1
            session["rol"] = "admin"
        response = self._get_pago("/pago?cita_id=77")
        self.assertEqual(response.status_code, 200)

    def test_rutas_internas_siguen_exigiendo_login(self):
        for url in ("/notas/55", "/panel_admin"):
            with self.subTest(url=url):
                response = self.cliente.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
