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


    def test_seguimiento_citas_filtra_semana_completa_y_enriquece(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        filas = [
            {
                "id": 21, "historial_id": 21, "paciente_id": 10, "terapeuta_id": 20,
                "fecha_cita": date(2026, 11, 3), "hora_cita": timedelta(hours=10),
                "estado": "cancelada",
            },
            {
                "id": 22, "historial_id": 22, "paciente_id": 11, "terapeuta_id": 20,
                "fecha_cita": date(2026, 11, 8), "hora_cita": timedelta(hours=11),
                "estado": "no_asistio",
            },
            {
                "id": 23, "historial_id": 23, "paciente_id": 12, "terapeuta_id": 20,
                "fecha_cita": date(2026, 11, 9), "hora_cita": timedelta(hours=12),
                "estado": "cancelada",
            },
        ]

        def fake_call_proc(nombre, params=(), **kwargs):
            if nombre == "sp_listar_citas":
                estado, _, desde, _ = params
                return [dict(f) for f in filas if f["estado"] == estado and f["fecha_cita"] >= date.fromisoformat(str(desde))]
            return []

        with (
            patch("services.citas_service.routes.call_proc", side_effect=fake_call_proc),
            patch("services.citas_service.routes._mapa_pacientes", return_value={
                10: {"id": 10, "nombre": "Ana", "apellido": "Luz", "telefono": "999111222"},
                11: {"id": 11, "nombre": "Luis", "apellido": "Paz", "telefono": "999333444"},
            }),
            patch("services.citas_service.routes._mapa_terapeutas", return_value={
                20: {"ID": 20, "Nombre": "Dra. Vega"},
            }),
        ):
            response = client.get(
                "/_internal/api/citas/seguimiento?desde=2026-11-02&hasta=2026-11-08",
                headers=cabeceras,
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["canceladas"], 1)
        self.assertEqual(body["no_asistidos"], 1)
        self.assertEqual([c["fecha_cita"] for c in body["citas"]], ["2026-11-03", "2026-11-08"])
        self.assertEqual(body["citas"][0]["nombre"], "Ana")
        self.assertEqual(body["citas"][0]["terapeuta"], "Dra. Vega")

    def test_seguimiento_citas_rechaza_rango_invalido(self):
        app = create_app()
        client = internal_test_client(app)
        cabeceras = {"X-Api-Key": API_KEY} if API_KEY else {}
        response = client.get(
            "/_internal/api/citas/seguimiento?desde=2026-11-09&hasta=2026-11-02",
            headers=cabeceras,
        )
        self.assertEqual(response.status_code, 400)


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
            if nombre == "sp_disponibilidad_citas_rango":
                return [{"fecha_cita": fecha, "hora_cita": timedelta(hours=10)}]
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
        proc.assert_called_once_with(
            "sp_disponibilidad_citas_rango", (20, "2026-11-10", "2026-11-20")
        )


if __name__ == "__main__":
    unittest.main()
