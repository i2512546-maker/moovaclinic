import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as gateway_app  # noqa: E402
from services.pagos_service import providers  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402

CITA_ID = 77
MONTO = 80.0
RUTAS = {
    "yape": (
        "YapeClient",
        "/_internal/api/pagos/yape/iniciar",
        "/_internal/api/pagos/yape/estado",
    ),
    "plin": (
        "PlinClient",
        "/_internal/api/pagos/plin/iniciar",
        "/_internal/api/pagos/plin/estado",
    ),
}


class PagosModoDemoTest(unittest.TestCase):
    def setUp(self):
        self.app = gateway_app.create_app()
        self.client = internal_test_client(self.app)
        self.headers = {"X-Api-Key": API_KEY} if API_KEY else {}
        self.pago = {
            "cita_id": CITA_ID,
            "monto": MONTO,
            "referencia": None,
        }

    def _sin_credenciales(self, proveedor):
        prefijo = proveedor.upper()
        return patch.multiple(
            providers,
            **{
                f"{prefijo}_API_URL": "",
                f"{prefijo}_CLIENT_ID": "",
                f"{prefijo}_CLIENT_SECRET": "",
                f"{prefijo}_MERCHANT_ID": "",
            },
        )

    def _datos_pendientes(self, _cita_id):
        return self.pago

    def _guardar_referencia(self, _cita_id, referencia):
        self.pago["referencia"] = referencia

    def test_demo_inicia_y_confirma_por_el_camino_de_validacion_normal(self):
        for proveedor, (_, ruta_inicio, ruta_estado) in RUTAS.items():
            with self.subTest(proveedor=proveedor):
                self.pago["referencia"] = None
                with patch.object(providers, "PAGOS_MODO_DEMO", True), \
                        self._sin_credenciales(proveedor), \
                        patch(
                            "services.pagos_service.routes._obtener_pago_pendiente",
                            side_effect=self._datos_pendientes,
                        ), patch(
                            "services.pagos_service.routes._guardar_referencia",
                            side_effect=self._guardar_referencia,
                        ), patch(
                            "services.pagos_service.routes.confirmar_pago_servicio"
                        ) as confirmar:
                    iniciar = self.client.post(
                        ruta_inicio, json={"cita_id": CITA_ID},
                        headers=self.headers,
                    )
                    self.assertEqual(iniciar.status_code, 200)
                    datos_inicio = iniciar.get_json()
                    self.assertTrue(datos_inicio["ok"])
                    self.assertEqual(datos_inicio["cobro_id"], "DEMO-77-80.00")
                    self.assertTrue(
                        datos_inicio["qr"].startswith("data:image/svg+xml,")
                    )

                    estado = self.client.post(
                        ruta_estado, json={"cita_id": CITA_ID},
                        headers=self.headers,
                    )
                    self.assertEqual(estado.status_code, 200)
                    self.assertTrue(estado.get_json()["pagado"])
                    confirmar.assert_called_once()
                    self.assertEqual(confirmar.call_args.args[0], CITA_ID)
                    self.assertEqual(
                        confirmar.call_args.kwargs["referencia"], "DEMO-77-80.00"
                    )

    def test_demo_apagado_sin_credenciales_falla_como_antes(self):
        with patch.object(providers, "PAGOS_MODO_DEMO", False), \
                self._sin_credenciales("yape"), \
                patch(
                    "services.pagos_service.routes._obtener_pago_pendiente",
                    return_value=self.pago,
                ):
            respuesta = self.client.post(
                RUTAS["yape"][1], json={"cita_id": CITA_ID},
                headers=self.headers,
            )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("faltan credenciales", respuesta.get_json()["error"])

    def test_con_credenciales_usa_la_pasarela_real_aunque_demo_este_activo(self):
        for proveedor in RUTAS:
            with self.subTest(proveedor=proveedor):
                prefijo = proveedor.upper()
                client_class = getattr(providers, RUTAS[proveedor][0])
                oauth = MagicMock(status_code=200)
                oauth.json.return_value = {"access_token": "token-real"}
                cobro_real = MagicMock(status_code=201)
                cobro_real.json.return_value = {
                    "id": "PROVEEDOR-123",
                    "qr": "qr-real",
                }
                with patch.object(providers, "PAGOS_MODO_DEMO", True), \
                        patch.object(
                            providers, f"{prefijo}_API_URL",
                            f"https://{proveedor}.test",
                        ), patch.object(
                            providers, f"{prefijo}_CLIENT_ID", "client"
                        ), patch.object(
                            providers, f"{prefijo}_CLIENT_SECRET", "secret"
                        ), patch.object(
                            providers, f"{prefijo}_MERCHANT_ID", "merchant"
                        ), patch.object(
                            providers.requests, "post",
                            side_effect=[oauth, cobro_real],
                        ) as post:
                    resultado = client_class().crear_cobro(
                        MONTO, "Cita", str(CITA_ID)
                    )

                self.assertEqual(resultado["cobro_id"], "PROVEEDOR-123")
                self.assertEqual(resultado["qr_base64"], "qr-real")
                self.assertEqual(post.call_count, 2)
                self.assertIn("/oauth/token", post.call_args_list[0].args[0])
                self.assertIn(
                    "/api/v1/cobros", post.call_args_list[1].args[0]
                )

    def test_consultar_pago_rechaza_ids_ajenos_al_formato_demo(self):
        for proveedor, (client_name, _, _) in RUTAS.items():
            with self.subTest(proveedor=proveedor):
                with patch.object(providers, "PAGOS_MODO_DEMO", True), \
                        self._sin_credenciales(proveedor):
                    with self.assertRaises(providers.PaymentProviderError):
                        getattr(providers, client_name)().consultar_pago(
                            "cobro-real-123"
                        )

    def test_gateway_muestra_aviso_en_ambos_modales_en_modo_demo(self):
        app = gateway_app.create_app()
        cliente = app.test_client()
        with cliente.session_transaction() as session:
            session["usuario_id"] = 1
            session["rol"] = "paciente"

        with patch.object(gateway_app, "PAGOS_MODO_DEMO", True), \
                patch.object(
                    gateway_app.pagos_client,
                    "get",
                    return_value=({"pago": {"estado_pago": "pendiente",
                                            "monto": MONTO}}, 200),
                ), patch.object(
                    gateway_app.citas_client,
                    "get",
                    return_value=({"cita": {}}, 200),
                ):
            respuesta = cliente.get("/pago?cita_id=77")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.get_data(as_text=True).count(
                "MODO DEMOSTRACIÓN: no se cobra dinero real"
            ),
            2,
        )

    def test_arranque_registra_warning_de_modo_demo(self):
        with patch.object(gateway_app, "PAGOS_MODO_DEMO", True), \
                self.assertLogs("gateway.app", level="WARNING") as logs:
            gateway_app.create_app()
        self.assertTrue(any(
            "Pagos en MODO DEMOSTRACIÓN: no se cobra dinero real" in linea
            for linea in logs.output
        ))


if __name__ == "__main__":
    unittest.main()
