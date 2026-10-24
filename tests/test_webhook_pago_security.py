import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-api-de-pruebas")

import gateway.app as ga


class WebhookPagoSecurityTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.url = "/_internal/api/pagos/webhook"
        self.pago = {"cita_id": 55, "estado": "pagado"}

    def test_sin_token_configurado_falla_cerrado(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN", ""
        ), patch.dict(os.environ, {"ALLOW_INSECURE_WEBHOOK": "0"}), patch(
            "services.pagos_service.routes.confirmar_pago_servicio"
        ) as confirmar:
            respuesta = self.client.post(self.url, json=self.pago)

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(
            respuesta.get_json(),
            {"ok": False, "error": "Webhook no configurado"},
        )
        confirmar.assert_not_called()

    def test_token_incorrecto_devuelve_401(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN",
            "token-esperado",
        ), patch("services.pagos_service.routes.confirmar_pago_servicio") as confirmar:
            respuesta = self.client.post(
                self.url,
                json=self.pago,
                headers={"X-Provider-Token": "token-incorrecto"},
            )

        self.assertEqual(respuesta.status_code, 401)
        confirmar.assert_not_called()

    def test_token_correcto_confirma_pago(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN",
            "token-esperado",
        ), patch(
            "services.pagos_service.routes.confirmar_pago_servicio"
        ) as confirmar:
            respuesta = self.client.post(
                self.url,
                json=self.pago,
                headers={"X-Provider-Token": "token-esperado"},
            )

        self.assertEqual(respuesta.status_code, 200)
        confirmar.assert_called_once_with(
            55, referencia=None, datos_respuesta=self.pago
        )

    def test_sin_token_permite_solo_modo_explicito_de_desarrollo(self):
        with patch(
            "services.pagos_service.routes.WEBHOOK_PROVIDER_TOKEN", ""
        ), patch.dict(os.environ, {"ALLOW_INSECURE_WEBHOOK": "1"}), patch(
            "services.pagos_service.routes.confirmar_pago_servicio"
        ) as confirmar:
            respuesta = self.client.post(self.url, json=self.pago)

        self.assertEqual(respuesta.status_code, 200)
        confirmar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
