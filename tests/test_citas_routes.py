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
            if nombre == "sp_listar_citas_dia":
                return [dict(cita)]
            if nombre == "sp_resumen_pacientes_agenda":
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
        resumen_calls = [
            call for call in proc.call_args_list
            if call.args[0] == "sp_resumen_pacientes_agenda"
        ]
        self.assertEqual(len(resumen_calls), 1)

    def test_agenda_diaria_exige_fecha_valida(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        response = client.get("/_internal/api/citas/agenda?fecha=ayer", headers=cabeceras)
        self.assertEqual(response.status_code, 400)

    def test_resumen_panel_usa_conteos_agrupados(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        cita = {
            "id": 3, "fecha_cita": date(2026, 11, 3), "estado": "programada",
            "paciente_id": 10, "terapeuta_id": 20,
        }

        def fake_call_proc(nombre, params=(), **kwargs):
            if nombre == "sp_listar_citas_dia":
                return [dict(cita)]
            if nombre == "sp_resumen_citas_estados":
                return [
                    {"estado": "cancelada", "total": 4},
                    {"estado": "no_asistio", "total": 2},
                ]
            return []

        with (
            patch("services.citas_service.routes.call_proc", side_effect=fake_call_proc) as proc,
            patch("services.citas_service.routes._mapa_pacientes", return_value={}),
            patch("services.citas_service.routes._mapa_terapeutas", return_value={}),
        ):
            response = client.get(
                "/_internal/api/citas/resumen-panel?fecha=2026-11-03&desde=2026-10-04",
                headers=cabeceras,
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["proximas_citas"]), 1)
        self.assertEqual(body["total_canceladas"], 4)
        self.assertEqual(body["total_no_asistidos"], 2)
        nombres = [call.args[0] for call in proc.call_args_list]
        self.assertEqual(nombres.count("sp_listar_citas_dia"), 1)
        self.assertEqual(nombres.count("sp_resumen_citas_estados"), 1)

    def test_resumen_panel_rechaza_fechas_invalidas(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        response = client.get(
            "/_internal/api/citas/resumen-panel?fecha=hoy&desde=ayer",
            headers=cabeceras,
        )
        self.assertEqual(response.status_code, 400)

    def test_disponibilidad_bloquea_solo_reservas_activas_y_por_hora(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        fecha = date(2026, 11, 10)

        def fake_call_proc(nombre, params=(), **kwargs):
            if nombre != "sp_listar_citas":
                return []
            estado = params[0]
            if estado == "programada":
                return [{"fecha_cita": fecha, "hora_cita": timedelta(hours=10)}]
            # Canceladas y no_asistio no se consultan como ocupadas.
            return []

        with patch("services.citas_service.routes.call_proc", side_effect=fake_call_proc) as proc:
            response = client.get(
                "/_internal/api/citas/ocupadas?medico_id=20&desde=2026-11-10&hasta=2026-11-20",
                headers=cabeceras,
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["horas_ocupadas"], {"2026-11-10": ["10:00"]})
        self.assertEqual(body["fechas"], [])
        estados_consultados = [llamada.args[1][0] for llamada in proc.call_args_list]
        self.assertEqual(set(estados_consultados), {"programada", "confirmada", "pendiente_pago"})


if __name__ == "__main__":
    unittest.main()
