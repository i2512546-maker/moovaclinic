import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")

from gateway.app import create_app
from shared.config import API_KEY
from tests.internal_client import internal_test_client


class ListarCitasTest(unittest.TestCase):
    def test_serializa_hora_cita_devuelta_como_timedelta(self):
        app = create_app()
        app.config.update(TESTING=False)
        client = internal_test_client(app)

        # Todas las rutas del servicio exigen la API_KEY interna (FASE 1),
        # salvo "/" y "/health".
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}

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
            response = client.get(
                "/_internal/api/citas?fecha=2026-09-24&estado=programada",
                headers=cabeceras,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["citas"][0]["hora_cita"], "09:30:00")


    def test_agenda_diaria_reutiliza_resumen_y_mapas_una_sola_vez(self):
        app = create_app()
        app.config.update(TESTING=False)
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        cita = {
            "id": 2, "historial_id": 2, "paciente_id": 10, "terapeuta_id": 20,
            "fecha_cita": date(2026, 11, 3), "hora_cita": timedelta(hours=10),
            "estado": "programada",
        }

        def fake_call_proc(nombre, params=(), **kwargs):
            if nombre == "sp_listar_citas" and params[0] == "programada":
                return [dict(cita)]
            if nombre == "sp_resumen_pacientes":
                return [{"paciente_id": 10, "total": 3}]
            return []

        with (
            patch("services.citas_service.routes.call_proc", side_effect=fake_call_proc) as proc,
            patch("services.citas_service.routes._mapa_pacientes", return_value={10: {"id": 10, "nombre": "Ana"}}) as mapa_p,
            patch("services.citas_service.routes._mapa_terapeutas", return_value={20: {"ID": 20, "Nombre": "Terapeuta"}}) as mapa_t,
        ):
            response = client.get(
                "/_internal/api/citas/agenda?fecha=2026-11-03",
                headers=cabeceras,
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["citas"][0]["nombre"], "Ana")
        self.assertEqual(body["citas"][0]["terapeuta"], "Terapeuta")
        self.assertEqual(body["citas"][0]["total_visitas"], 3)
        mapa_p.assert_called_once()
        mapa_t.assert_called_once()
        resumen_calls = [call for call in proc.call_args_list if call.args[0] == "sp_resumen_pacientes"]
        self.assertEqual(len(resumen_calls), 1)

    def test_agenda_diaria_exige_fecha_valida(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        response = client.get("/_internal/api/citas/agenda?fecha=ayer", headers=cabeceras)
        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
