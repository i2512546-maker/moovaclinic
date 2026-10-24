import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from gateway.app import create_app


class VerificarDniPublicoTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False

    def test_consulta_publica_y_limite_por_ip(self):
        respuesta_servicio = ({"nombres": "ANA", "apellido_paterno": "PEREZ"}, 200)
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=respuesta_servicio,
        ) as consulta:
            for numero in range(16):
                cliente = self.app.test_client()
                respuesta = cliente.post(
                    "/api/verificar_dni",
                    json={"dni": "12345678"},
                    environ_base={"REMOTE_ADDR": "192.0.2.10"},
                )

                if numero == 0:
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertTrue(respuesta.is_json)
                    self.assertNotEqual(respuesta.status_code, 302)
                elif numero < 15:
                    self.assertEqual(respuesta.status_code, 200)
                else:
                    self.assertEqual(respuesta.status_code, 429)
                    self.assertEqual(
                        respuesta.get_json(),
                        {"error": "Demasiadas consultas DNI. Intenta más tarde."},
                    )

        self.assertEqual(consulta.call_count, 15)


if __name__ == "__main__":
    unittest.main()
