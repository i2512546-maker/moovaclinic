import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga
from shared.service_client import auth_client


class InternalLoopbackOnlyTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.api_key = auth_client.headers["X-Api-Key"]

    def test_llamada_externa_a_auth_con_api_key_devuelve_404(self):
        with patch("services.auth_service.routes.call_proc", return_value=[]):
            respuesta = self.client.get(
                "/_internal/api/auth/usuarios",
                headers={"X-Api-Key": self.api_key},
            )

        self.assertEqual(respuesta.status_code, 404)

    def test_auth_client_interno_puede_acceder(self):
        with patch("services.auth_service.routes.call_proc", return_value=[]):
            data, status = auth_client.get("/api/auth/usuarios")

        self.assertEqual(status, 200)
        self.assertEqual(data["usuarios"], [])

    def test_webhook_externo_sigue_accesible_con_token(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN",
            "token-valido",
        ), patch(
            "services.pagos_service.routes.confirmar_pago_servicio"
        ) as confirmar:
            respuesta = self.client.post(
                "/_internal/api/pagos/webhook",
                json={"cita_id": 55, "estado": "pagado"},
                headers={"X-Provider-Token": "token-valido"},
            )

        self.assertEqual(respuesta.status_code, 200)
        confirmar.assert_called_once()

    def test_mantenimiento_externo_exige_api_key_y_sigue_alcanzable(self):
        ruta = "/_internal/api/pagos/mantenimiento/liberar_vencidos"
        with patch(
            "services.pagos_service.routes.call_proc",
            return_value=[],
        ), patch(
            "services.pagos_service.routes.call_proc_one",
            return_value={"vencidos": 0},
        ):
            sin_clave = self.client.post(ruta, json={"horas": 24})
            con_clave = self.client.post(
                ruta,
                json={"horas": 24},
                headers={"X-Api-Key": self.api_key},
            )

        self.assertEqual(sin_clave.status_code, 401)
        self.assertEqual(con_clave.status_code, 200)


if __name__ == "__main__":
    unittest.main()
