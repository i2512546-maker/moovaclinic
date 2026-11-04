import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from gateway.app import create_app
from shared.config import API_KEY
from tests.internal_client import internal_test_client


class ListadoPacientesLigeroTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = internal_test_client(self.app)
        self.headers = {"X-Api-Key": API_KEY} if API_KEY else {}

    def test_catalogo_ligero_no_consulta_resumen_de_citas(self):
        pacientes = [{
            "id": 7,
            "nombre": "Ana",
            "apellido": "Pérez",
        }]
        with patch(
            "services.pacientes_service.routes.call_proc",
            return_value=pacientes,
        ) as procedimiento, patch(
            "services.pacientes_service.routes.citas_client.get"
        ) as resumen:
            response = self.client.get(
                "/_internal/api/pacientes?incluir_resumen=0",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        procedimiento.assert_called_once_with("sp_listar_pacientes")
        resumen.assert_not_called()
        self.assertEqual(
            response.get_json()["pacientes"],
            [{
                "id": 7,
                "nombre": "Ana",
                "apellido": "Pérez",
                "total_citas": 0,
                "ultima_cita": None,
            }],
        )

    def test_listado_completo_conserva_resumen_por_defecto(self):
        pacientes = [{"id": 7, "nombre": "Ana", "apellido": "Pérez"}]
        with patch(
            "services.pacientes_service.routes.call_proc",
            return_value=pacientes,
        ), patch(
            "services.pacientes_service.routes.citas_client.get",
            return_value=({
                "resumen": [{"paciente_id": 7, "total": 4, "ultima": "2026-11-03"}]
            }, 200),
        ) as resumen:
            response = self.client.get(
                "/_internal/api/pacientes",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        resumen.assert_called_once_with("/api/citas/resumen_pacientes")
        self.assertEqual(response.get_json()["pacientes"][0]["total_citas"], 4)


if __name__ == "__main__":
    unittest.main()
