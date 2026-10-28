import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402


class FechasOcupadasServiceTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.client = internal_test_client(self.app)
        self.headers = {"X-Api-Key": API_KEY} if API_KEY else {}

    def test_solo_devuelve_fechas_unicas_programadas_y_confirmadas(self):
        def fake_call_proc(nombre, parametros):
            estado, dni, desde, medico = parametros
            self.assertEqual(nombre, "sp_listar_citas")
            self.assertIsNone(dni)
            self.assertEqual(desde, "2026-10-01")
            self.assertEqual(medico, "12")
            if estado == "programada":
                return [
                    {"fecha_cita": date(2026, 10, 8), "dni": "12345678",
                     "nombre": "Paciente"},
                    {"fecha_cita": date(2026, 10, 4), "telefono": "999999999"},
                    {"fecha_cita": date(2026, 11, 1)},
                ]
            if estado == "confirmada":
                return [
                    {"fecha_cita": date(2026, 10, 8), "apellido": "Apellido"},
                    {"fecha_cita": date(2026, 10, 6)},
                ]
            self.fail(f"Estado no esperado: {estado}")

        with patch(
            "services.citas_service.routes.call_proc", side_effect=fake_call_proc
        ) as call_proc:
            respuesta = self.client.get(
                "/_internal/api/citas/ocupadas?medico_id=12"
                "&desde=2026-10-01&hasta=2026-10-31",
                headers=self.headers,
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.get_json(),
            {"fechas": ["2026-10-04", "2026-10-06", "2026-10-08"]},
        )
        call_proc.assert_has_calls([
            unittest.mock.call(
                "sp_listar_citas", ("programada", None, "2026-10-01", "12")
            ),
            unittest.mock.call(
                "sp_listar_citas", ("confirmada", None, "2026-10-01", "12")
            ),
        ])
        contenido = respuesta.get_data(as_text=True).lower()
        for clave in ("nombre", "apellido", "dni", "telefono", "paciente"):
            self.assertNotIn(clave, contenido)

    def test_rechaza_medico_invalido_y_fechas_no_iso(self):
        for query in (
            "medico_id=abc&desde=2026-10-01&hasta=2026-10-10",
            "medico_id=0&desde=2026-10-01&hasta=2026-10-10",
            "medico_id=12&desde=2026-1-01&hasta=2026-10-10",
        ):
            with self.subTest(query=query):
                respuesta = self.client.get(
                    f"/_internal/api/citas/ocupadas?{query}",
                    headers=self.headers,
                )
                self.assertEqual(respuesta.status_code, 400)

    def test_rechaza_rango_mayor_de_90_dias(self):
        with patch("services.citas_service.routes.call_proc") as call_proc:
            respuesta = self.client.get(
                "/_internal/api/citas/ocupadas?medico_id=12"
                "&desde=2026-01-01&hasta=2026-04-02",
                headers=self.headers,
            )
        self.assertEqual(respuesta.status_code, 400)
        call_proc.assert_not_called()


class DisponibilidadGatewayTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.client = self.app.test_client()

    def test_consulta_publica_sin_sesion_y_reenvia_parametros(self):
        with patch.object(
            ga.citas_client,
            "get",
            return_value=({"fechas": ["2026-10-08"]}, 200),
        ) as consultar:
            respuesta = self.client.get(
                "/api/disponibilidad/12?desde=2026-10-01&hasta=2026-10-31"
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), {"fechas": ["2026-10-08"]})
        consultar.assert_called_once_with(
            "/api/citas/ocupadas",
            params={
                "medico_id": 12,
                "desde": "2026-10-01",
                "hasta": "2026-10-31",
            },
        )

    def test_limita_consultas_por_ip(self):
        with patch.object(
            ga.citas_client, "get", return_value=({"fechas": []}, 200)
        ) as consultar:
            for _ in range(15):
                respuesta = self.client.get("/api/disponibilidad/12")
                self.assertEqual(respuesta.status_code, 200)
            respuesta = self.client.get("/api/disponibilidad/12")

        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(consultar.call_count, 15)


if __name__ == "__main__":
    unittest.main()
