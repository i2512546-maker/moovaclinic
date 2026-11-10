"""Pruebas del OTP obligatorio para agendar citas desde el gateway."""
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app

DNI = "12345678"


class OTPAgendarGatewayTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sesion:
            sesion["cita_identidad_verificada"] = {
                "dni": DNI, "nombre": "ana", "apellido": "perez",
            }

    def test_solicitar_otp_usa_telefono_registrado(self):
        with (
            patch(
                "gateway.app.citas_client.post",
                return_value=({"success": True, "tel_mask": "987***321"}, 200),
            ) as post_otp,
            patch(
                "gateway.app.pacientes_client.get",
                return_value=({"paciente": {"telefono": "987654321"}}, 200),
            ),
        ):
            respuesta = self.client.post("/api/citas/otp/solicitar", json={
                "dni": DNI, "telefono": "111111111",
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(post_otp.call_args.args[0], "/api/citas/otp/solicitar")
        self.assertEqual(post_otp.call_args.args[1]["accion"], "agendar")
        with self.client.session_transaction() as sesion:
            self.assertEqual(
                sesion["otp_agendar_pendiente"]["telefono"], "987654321"
            )

    def test_solicitar_otp_acepta_telefono_de_paciente_nuevo(self):
        with (
            patch(
                "gateway.app.citas_client.post",
                return_value=({"success": True, "tel_mask": "987***321"}, 200),
            ) as post_otp,
            patch(
                "gateway.app.pacientes_client.get",
                return_value=({"error": "No encontrado"}, 404),
            ),
        ):
            respuesta = self.client.post("/api/citas/otp/solicitar", json={
                "dni": DNI, "telefono": "987-654-321",
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            post_otp.call_args.args[1]["telefono"], "987654321"
        )
        with self.client.session_transaction() as sesion:
            self.assertEqual(
                sesion["otp_agendar_pendiente"]["telefono"], "987654321"
            )

    def test_verificar_otp_deja_sello_de_agendar(self):
        with self.client.session_transaction() as sesion:
            sesion["otp_agendar_pendiente"] = {
                "dni": DNI, "telefono": "987654321", "ts": __import__("time").time(),
            }
        with patch(
            "gateway.app.citas_client.post",
            return_value=({"resultado": "ok"}, 200),
        ) as post_otp:
            respuesta = self.client.post("/api/citas/otp/verificar", json={
                "dni": DNI, "otp": "123456",
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(post_otp.call_args.args[1]["accion"], "agendar")
        with self.client.session_transaction() as sesion:
            self.assertEqual(sesion["otp_agendar_verificado"]["dni"], DNI)
            self.assertEqual(sesion["otp_verificado"]["agendar"]["dni"], DNI)

    def test_no_solicita_codigo_sin_identidad_verificada(self):
        with self.client.session_transaction() as sesion:
            sesion.pop("cita_identidad_verificada", None)
        with patch("gateway.app.citas_client.post") as post_otp:
            respuesta = self.client.post("/api/citas/otp/solicitar", json={
                "dni": DNI, "telefono": "987654321",
            })
        self.assertEqual(respuesta.status_code, 403)
        post_otp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
