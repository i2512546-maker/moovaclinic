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

    def test_devuelve_horas_ocupadas_incluyendo_pendientes_de_pago(self):
        filas = [
            {"fecha_cita": date(2026, 10, 8), "hora_cita": "09:00:00"},
            {"fecha_cita": date(2026, 10, 4), "hora_cita": "10:00:00"},
            {"fecha_cita": date(2026, 10, 8), "hora_cita": "11:00:00"},
            {"fecha_cita": date(2026, 10, 6), "hora_cita": "09:00:00"},
            {"fecha_cita": date(2026, 10, 8), "hora_cita": "10:00:00"},
            # La API valida el rango en el borde, aunque el SP ya filtre fechas.
            {"fecha_cita": date(2026, 11, 1), "hora_cita": "12:00:00"},
        ]

        with patch(
            "services.citas_service.routes.call_proc", return_value=filas
        ) as call_proc:
            respuesta = self.client.get(
                "/_internal/api/citas/ocupadas?medico_id=12"
                "&desde=2026-10-01&hasta=2026-10-31",
                headers=self.headers,
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.get_json(),
            {
                "fechas": [],
                "horas_ocupadas": {
                    "2026-10-04": ["10:00"],
                    "2026-10-06": ["09:00"],
                    "2026-10-08": ["09:00", "10:00", "11:00"],
                },
            },
        )
        call_proc.assert_called_once_with(
            "sp_disponibilidad_citas_rango",
            (12, "2026-10-01", "2026-10-31"),
        )
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
            return_value=({"fechas": [], "horas_ocupadas": {"2026-10-08": ["10:00"]}}, 200),
        ) as consultar:
            respuesta = self.client.get(
                "/api/disponibilidad/12?desde=2026-10-01&hasta=2026-10-31"
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), {"fechas": [], "horas_ocupadas": {"2026-10-08": ["10:00"]}})
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
            ga.citas_client, "get", return_value=({"fechas": [], "horas_ocupadas": {}}, 200)
        ) as consultar:
            for _ in range(15):
                respuesta = self.client.get("/api/disponibilidad/12")
                self.assertEqual(respuesta.status_code, 200)
            respuesta = self.client.get("/api/disponibilidad/12")

        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(consultar.call_count, 15)


if __name__ == "__main__":
    unittest.main()
