import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-api-de-pruebas")

import gateway.app as ga


class InternalGatewaySecurityTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_ruta_interna_exige_api_key_y_acepta_la_correcta(self):
        with patch("shared.service_auth.API_KEY", "clave-interna"), patch(
            "services.pagos_service.routes.call_proc_one",
            return_value={"estado_pago": "pendiente"},
        ):
            sin_clave = self.client.get("/_internal/api/pagos/55")
            con_clave = self.client.get(
                "/_internal/api/pagos/55",
                headers={"X-Api-Key": "clave-interna"},
            )

        self.assertEqual(sin_clave.status_code, 401)
        self.assertEqual(con_clave.status_code, 200)

    def test_webhook_no_exige_api_key_pero_valida_token_proveedor(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN",
            "token-esperado",
        ):
            respuesta = self.client.post(
                "/_internal/api/pagos/webhook",
                json={"cita_id": 55},
                headers={"X-Provider-Token": "token-invalido"},
            )

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(
            respuesta.get_json()["error"], "Token no autorizado"
        )

    def test_rutas_publicas_gateway_no_exigen_api_key_interna(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)


if __name__ == "__main__":
    unittest.main()
