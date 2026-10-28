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

    def _post(self, cliente, dni="12345678", ip="192.0.2.10"):
        return cliente.post(
            "/api/verificar_dni",
            json={"dni": dni},
            environ_base={"REMOTE_ADDR": ip},
        )

    def test_sin_sesion_devuelve_json_sin_redireccion(self):
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=({"success": True, "data": {"nombres": "JUAN"}}, 200),
        ):
            respuesta = self._post(self.app.test_client())

        self.assertNotEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.is_json)

    def test_devuelve_respuesta_del_servicio_sin_anidar_data(self):
        respuesta_servicio = {
            "success": True,
            "data": {
                "nombres": "JUAN",
                "apellido_paterno": "PEREZ",
                "apellido_materno": "RAMOS",
            },
        }
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=(respuesta_servicio, 200),
        ):
            respuesta = self._post(self.app.test_client())

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), respuesta_servicio)
        self.assertEqual(respuesta.get_json()["data"]["nombres"], "JUAN")

    def test_refleja_respuesta_404_del_servicio(self):
        respuesta_servicio = {"success": False, "error": "DNI no encontrado"}
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=(respuesta_servicio, 404),
        ):
            respuesta = self._post(self.app.test_client())

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.get_json(), respuesta_servicio)
        self.assertFalse(respuesta.get_json()["success"])

    def test_error_del_servicio_devuelve_502(self):
        with patch(
            "gateway.app.pacientes_client.post",
            side_effect=RuntimeError("servicio no disponible"),
        ):
            respuesta = self._post(self.app.test_client())

        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(
            respuesta.get_json(),
            {"success": False, "error": "No se pudo consultar el DNI"},
        )

    def test_dni_invalido_devuelve_400_sin_consultar_servicio(self):
        with patch("gateway.app.pacientes_client.post") as consulta:
            respuesta = self._post(self.app.test_client(), dni="123")

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.get_json()["success"])
        consulta.assert_not_called()

    def test_conserva_limite_de_cinco_consultas_por_sesion(self):
        cliente = self.app.test_client()
        respuesta_servicio = ({"success": True, "data": {}}, 200)
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=respuesta_servicio,
        ) as consulta:
            for _ in range(5):
                self.assertEqual(self._post(cliente).status_code, 200)
            respuesta = self._post(cliente)

        self.assertEqual(respuesta.status_code, 429)
        self.assertFalse(respuesta.get_json()["success"])
        self.assertEqual(consulta.call_count, 5)

    def test_consulta_16_desde_la_misma_ip_devuelve_429(self):
        respuesta_servicio = ({"success": True, "data": {}}, 200)
        with patch(
            "gateway.app.pacientes_client.post",
            return_value=respuesta_servicio,
        ) as consulta:
            for _ in range(15):
                respuesta = self._post(self.app.test_client())
                self.assertEqual(respuesta.status_code, 200)
            respuesta = self._post(self.app.test_client())

        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(
            respuesta.get_json(),
            {
                "success": False,
                "error": "Demasiadas consultas DNI. Intenta más tarde.",
            },
        )
        self.assertEqual(consulta.call_count, 15)


if __name__ == "__main__":
    unittest.main()
