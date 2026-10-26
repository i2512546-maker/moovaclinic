import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from gateway.app import create_app


class TerapeutaAgendaSeguridadTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _sesion(self, usuario_id=10, rol="terapeuta"):
        with self.client.session_transaction() as sesion:
            sesion["usuario_id"] = usuario_id
            sesion["usuario_nombre"] = "Terapeuta"
            sesion["rol"] = rol

    def _terapeutas(self, url, **kwargs):
        return {
            "terapeutas": [
                {"ID": 101, "usuario_id": 10},
                {"ID": 202, "usuario_id": 20},
            ]
        }, 200

    def test_terapeuta_solo_ve_sus_citas_en_interfaz(self):
        self._sesion()
        citas = [
            {
                "historial_id": 1,
                "terapeuta_id": 101,
                "fecha_cita": "2026-10-25",
                "nombre": "PacientePropio",
                "apellido": "Uno",
                "total_visitas": 2,
            },
            {
                "historial_id": 2,
                "terapeuta_id": 202,
                "fecha_cita": "2026-10-25",
                "nombre": "PacienteAjeno",
                "apellido": "Dos",
                "total_visitas": 1,
            },
        ]
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"citas": citas}, 200),
            ),
            patch(
                "gateway.app.pacientes_client.get",
                side_effect=self._terapeutas,
            ),
        ):
            respuesta = self.client.get("/interfaz?fecha=2026-10-25")

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("PacientePropio", html)
        self.assertNotIn("PacienteAjeno", html)

    def test_admin_ve_todas_las_citas_en_interfaz(self):
        self._sesion(rol="admin")
        citas = [
            {
                "historial_id": 1,
                "terapeuta_id": 101,
                "fecha_cita": "2026-10-25",
                "nombre": "PacienteUno",
                "total_visitas": 2,
            },
            {
                "historial_id": 2,
                "terapeuta_id": 202,
                "fecha_cita": "2026-10-25",
                "nombre": "PacienteDos",
                "total_visitas": 1,
            },
        ]
        with patch(
            "gateway.app.citas_client.get",
            return_value=({"citas": citas}, 200),
        ):
            respuesta = self.client.get("/interfaz?fecha=2026-10-25")

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("PacienteUno", html)
        self.assertIn("PacienteDos", html)

    def test_terapeuta_no_puede_completar_cita_ajena(self):
        self._sesion()
        cita = {"id": 5, "terapeuta_id": 202}
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"cita": cita}, 200),
            ),
            patch("gateway.app.citas_client.put") as completar,
            patch(
                "gateway.app.pacientes_client.get",
                side_effect=self._terapeutas,
            ),
        ):
            respuesta = self.client.post(
                "/guardar_descripcion",
                data={"historial_id": "5", "descripcion": "Nota ajena"},
            )

        completar.assert_not_called()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/interfaz")

    def test_terapeuta_puede_completar_su_cita(self):
        self._sesion()
        cita = {"id": 5, "terapeuta_id": 101}
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"cita": cita}, 200),
            ),
            patch("gateway.app.citas_client.put") as completar,
            patch(
                "gateway.app.pacientes_client.get",
                side_effect=self._terapeutas,
            ),
        ):
            respuesta = self.client.post(
                "/guardar_descripcion",
                data={"historial_id": "5", "descripcion": "Nota propia"},
            )

        self.assertEqual(respuesta.status_code, 302)
        completar.assert_called_once_with(
            "/api/citas/5/completar",
            {"descripcion": "Nota propia"},
        )

    def test_admin_puede_completar_cualquier_cita(self):
        self._sesion(rol="admin")
        with patch("gateway.app.citas_client.put") as completar:
            respuesta = self.client.post(
                "/guardar_descripcion",
                data={"historial_id": "5", "descripcion": "Nota administrativa"},
            )

        self.assertEqual(respuesta.status_code, 302)
        completar.assert_called_once_with(
            "/api/citas/5/completar",
            {"descripcion": "Nota administrativa"},
        )

    def test_terapeuta_id_de_sesion_da_acceso_a_sus_notas(self):
        self._sesion()
        cita = {"id": 9, "paciente_id": 4, "terapeuta_id": 101}
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"cita": cita}, 200),
            ),
            patch(
                "gateway.app.pacientes_client.get",
                side_effect=self._terapeutas,
            ),
            patch(
                "gateway.app.notas_client.get",
                return_value=({"notas": []}, 200),
            ),
        ):
            respuesta = self.client.get("/notas/9")

        self.assertEqual(respuesta.status_code, 200)

    def test_terapeuta_no_puede_abrir_notas_de_otra_cita(self):
        self._sesion()
        cita = {"id": 9, "paciente_id": 4, "terapeuta_id": 202}
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"cita": cita}, 200),
            ),
            patch(
                "gateway.app.pacientes_client.get",
                side_effect=self._terapeutas,
            ),
            patch("gateway.app.notas_client.get") as obtener_notas,
        ):
            respuesta = self.client.get("/notas/9")

        self.assertEqual(respuesta.status_code, 302)
        obtener_notas.assert_not_called()

    def test_admin_puede_abrir_notas_de_cualquier_cita(self):
        self._sesion(rol="admin")
        cita = {"id": 9, "paciente_id": 4, "terapeuta_id": 202}
        with (
            patch(
                "gateway.app.citas_client.get",
                return_value=({"cita": cita}, 200),
            ),
            patch(
                "gateway.app.notas_client.get",
                return_value=({"notas": []}, 200),
            ) as obtener_notas,
        ):
            respuesta = self.client.get("/notas/9")

        self.assertEqual(respuesta.status_code, 200)
        obtener_notas.assert_called_once_with("/api/notas/9")


if __name__ == "__main__":
    unittest.main()
