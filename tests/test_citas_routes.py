import unittest
from datetime import date, timedelta
from unittest.mock import patch

from services.citas_service.app import create_app


class ListarCitasTest(unittest.TestCase):
    def test_serializa_hora_cita_devuelta_como_timedelta(self):
        app = create_app()
        app.config.update(TESTING=False)
        client = app.test_client()

        cita = {
            "id": 1,
            "historial_id": 1,
            "paciente_id": 10,
            "terapeuta_id": 20,
            "servicio_id": None,
            "fecha_cita": date(2026, 9, 24),
            "hora_cita": timedelta(hours=9, minutes=30),
            "estado": "programada",
            "descripcion": None,
        }

        def fake_call_proc(name, params=(), **kwargs):
            if name == "sp_listar_citas":
                return [cita]
            if name == "sp_resumen_pacientes":
                return [{"paciente_id": 10, "total": 1, "ultima": date(2026, 9, 24)}]
            return []

        with (
            patch("services.citas_service.routes.call_proc", side_effect=fake_call_proc),
            patch("services.citas_service.routes._mapa_pacientes", return_value={}),
            patch("services.citas_service.routes._mapa_terapeutas", return_value={}),
        ):
            response = client.get("/api/citas?fecha=2026-09-24&estado=programada")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["citas"][0]["hora_cita"], "09:30:00")


if __name__ == "__main__":
    unittest.main()
