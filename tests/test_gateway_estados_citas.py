import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from gateway.app import create_app


class GatewayEstadosCitasTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        with self.client.session_transaction() as sesion:
            sesion["usuario_id"] = 1
            sesion["rol"] = "admin"

    def test_no_asistio_propaga_error_del_servicio(self):
        cita = {
            "cita": {
                "id": 1,
                "fecha_cita": "2026-11-03",
                "estado": "programada",
                "terapeuta_id": 1,
            }
        }
        with patch(
            "gateway.app.citas_client.get", return_value=(cita, 200)
        ), patch(
            "gateway.app.citas_client.post",
            return_value=(
                {"success": False, "error": "No se pudo marcar la inasistencia."},
                409,
            ),
        ):
            respuesta = self.client.post(
                "/citas/1/no_asistio",
                data={"fecha": "2026-11-03"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.get_json(),
            {"success": False, "error": "No se pudo marcar la inasistencia."},
        )

    def test_no_asistio_confirma_solo_si_el_servicio_confirma(self):
        cita = {
            "cita": {
                "id": 1,
                "fecha_cita": "2026-11-03",
                "estado": "programada",
                "terapeuta_id": 1,
            }
        }
        with patch(
            "gateway.app.citas_client.get", return_value=(cita, 200)
        ), patch(
            "gateway.app.citas_client.post",
            return_value=({"success": True}, 200),
        ):
            respuesta = self.client.post(
                "/citas/1/no_asistio",
                data={"fecha": "2026-11-03"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.get_json(),
            {"success": True, "estado": "no_asistio"},
        )

    def test_cancelacion_admin_propaga_error_del_servicio(self):
        with patch(
            "gateway.app.citas_client.delete",
            return_value=({"error": "Cita no encontrada"}, 404),
        ):
            respuesta = self.client.post(
                "/panel_admin/cancelar_cita/1",
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(
            respuesta.get_json(),
            {"success": False, "error": "Cita no encontrada"},
        )


if __name__ == "__main__":
    unittest.main()
