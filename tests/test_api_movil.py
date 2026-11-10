"""Pruebas de autenticación, autorización y contrato de la API móvil."""
import os
import sys
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-pruebas")
os.environ.setdefault("API_KEY", "api-pruebas")
os.environ.setdefault("JWT_SECRET", "jwt-pruebas-distinta")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import jwt
from gateway.app import create_app


class ApiMovilTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False,
                               JWT_SECRET="jwt-pruebas-distinta")
        self.client = self.app.test_client()

    def token(self, rol="admin", exp=None):
        now = int(time.time())
        return jwt.encode({
            "sub": "7", "rol": rol, "nombre": "Prueba", "iat": now - 1,
            "exp": exp if exp is not None else now + 300,
            "iss": "moova-clinic", "aud": "moova-mobile",
        }, self.app.config["JWT_SECRET"], algorithm="HS256")

    def test_cookie_de_sesion_no_autentica(self):
        with self.client.session_transaction() as session:
            session["usuario_id"] = 7
            session["rol"] = "admin"
        response = self.client.get("/api/movil/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["codigo"], "TOKEN_REQUERIDO")

    def test_rechaza_sin_bearer(self):
        response = self.client.get("/api/movil/me")
        self.assertEqual(response.status_code, 401)

    def test_rechaza_rol_incorrecto(self):
        response = self.client.get("/api/movil/estadisticas",
                                   headers={"Authorization": f"Bearer {self.token('terapeuta')}"})
        self.assertEqual(response.status_code, 403)

    def test_rechaza_jwt_vencido(self):
        response = self.client.get("/api/movil/me",
                                   headers={"Authorization": f"Bearer {self.token(exp=int(time.time()) - 10)}"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["codigo"], "JWT_EXPIRADO")

    def test_login_entrega_jwt_y_envelope(self):
        usuario = {"id": 7, "nombre": "Ana", "correo": "ana@example.com", "rol": "admin"}
        with patch("gateway.movil.auth_client.post", return_value=({"success": True, "usuario": usuario}, 200)):
            response = self.client.post("/api/movil/auth/login",
                                        json={"correo": "ana@example.com", "clave": "secreta"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], 200)
        self.assertEqual(body["data"]["token_type"], "Bearer")

    def test_crear_cita_exige_otp(self):
        response = self.client.post("/api/movil/citas",
                                    json={"dni": "12345678"},
                                    headers={"Authorization": f"Bearer {self.token()}"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "OTP_REQUERIDO")

    def test_modificar_cita_exige_otp(self):
        response = self.client.put(
            "/api/movil/citas/12", json={"fecha_cita": "2026-11-10"},
            headers={"Authorization": f"Bearer {self.token()}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "OTP_REQUERIDO")

    def test_cancelar_cita_exige_otp(self):
        response = self.client.delete(
            "/api/movil/citas/12",
            headers={"Authorization": f"Bearer {self.token()}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "OTP_REQUERIDO")

    def test_terapeuta_no_consulta_cita_ajena(self):
        headers = {"Authorization": f"Bearer {self.token('terapeuta')}"}
        with (
            patch("gateway.movil.pacientes_client.get",
                  return_value=({"terapeutas": [{"ID": 99, "usuario_id": 7}]}, 200)),
            patch("gateway.movil.citas_client.get",
                  return_value=({"cita": {"terapeuta_id": 100}}, 200)),
        ):
            response = self.client.get("/api/movil/citas/12", headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "CITA_NO_AUTORIZADA")

    def test_otp_no_autoriza_otra_accion(self):
        from gateway.movil import _verificacion_serializer
        sello = _verificacion_serializer().dumps({"dni": "12345678", "accion": "consultar"})
        response = self.client.post(
            "/api/movil/citas", json={"dni": "12345678"},
            headers={"Authorization": f"Bearer {self.token()}",
                     "X-Verificacion": sello},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "OTP_ACCION_INCORRECTA")

    def test_paciente_no_puede_consultar_otro_dni(self):
        from gateway.movil import _verificacion_serializer
        sello = _verificacion_serializer().dumps({"dni": "12345678", "accion": "consultar"})
        response = self.client.get(
            "/api/movil/pacientes/87654321",
            headers={"X-Verificacion": sello},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["codigo"], "PACIENTE_NO_AUTORIZADO")

    def test_otp_solicitud_reenvia_accion_y_telefono(self):
        with patch("gateway.movil.citas_client.post",
                   return_value=({"success": True, "tel_mask": "987***321"}, 200)) as llamada:
            response = self.client.post(
                "/api/movil/auth/otp/solicitar",
                json={"dni": "12345678", "accion": "agendar", "telefono": "987654321"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(llamada.call_args.args[1]["accion"], "agendar")
        self.assertEqual(llamada.call_args.args[1]["telefono"], "987654321")

    def test_otp_verificacion_genera_sello_de_accion(self):
        with patch("gateway.movil.citas_client.post",
                   return_value=({"resultado": "ok"}, 200)):
            response = self.client.post("/api/movil/auth/otp/verificar",
                                        json={"dni": "12345678", "otp": "123456", "accion": "agendar"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("verificacion", response.get_json()["data"])
        self.assertEqual(response.get_json()["data"]["accion"], "agendar")


if __name__ == "__main__":
    unittest.main()
