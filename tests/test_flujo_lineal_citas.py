"""El formulario de citas permanece accesible y el pago pendiente es opcional."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402


class FlujoLinealCitasTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()

    def _pagos_get(self, estado_pago="pendiente", status=200):
        def obtener_pago(url, *args, **kwargs):
            if url == "/api/pagos/55":
                return {"pago": {"estado_pago": estado_pago}}, status
            if url == "/api/pagos/56":
                return {"pago": {"estado_pago": "pendiente"}}, status
            return {}, status

        return obtener_pago

    @staticmethod
    def _citas_get(url, *args, **kwargs):
        if url == "/api/citas/terapeutas":
            return {"terapeutas": []}, 200
        if url in ("/api/citas/55", "/api/citas/56"):
            return {
                "cita": {
                    "id": int(url.rsplit("/", 1)[1]),
                    "nombre": "Ana",
                    "apellido": "Perez",
                    "estado": "programada",
                    "fecha_cita": "2026-10-24",
                    "terapeuta": "Terapeuta",
                    "Especialidad": "Fisioterapia",
                },
            }, 200
        return {}, 200

    @staticmethod
    def _servicios_get(url, *args, **kwargs):
        return {"servicios": []}, 200

    def _get_citas(self, pagos_get=None):
        with patch.object(
            ga.pagos_client, "get", side_effect=pagos_get or self._pagos_get()
        ), patch.object(
            ga.citas_client, "get", side_effect=self._citas_get
        ), patch.object(
            ga.pacientes_client, "get", side_effect=self._servicios_get
        ):
            return self.cliente.get("/citas")

    def test_citas_sin_sesion_muestra_el_formulario_sin_aviso(self):
        response = self._get_citas()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("pendiente de pago", response.get_data(as_text=True))

    def test_cita_pendiente_muestra_aviso_sin_bloquear_formulario(self):
        with self.cliente.session_transaction() as session:
            session["cita_pendiente_id"] = "55"
        response = self._get_citas()
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("pendiente de pago", html)
        self.assertIn("/pago?cita_id=55", html)

    def test_cita_pagada_limpia_sesion_y_no_muestra_aviso(self):
        with self.cliente.session_transaction() as session:
            session["cita_pendiente_id"] = "55"
        response = self._get_citas(self._pagos_get("pagado"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("pendiente de pago", response.get_data(as_text=True))
        with self.cliente.session_transaction() as session:
            self.assertNotIn("cita_pendiente_id", session)

    def test_pago_inexistente_limpia_sesion_y_no_muestra_aviso(self):
        with self.cliente.session_transaction() as session:
            session["cita_pendiente_id"] = "55"
        response = self._get_citas(self._pagos_get(status=404))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("pendiente de pago", response.get_data(as_text=True))
        with self.cliente.session_transaction() as session:
            self.assertNotIn("cita_pendiente_id", session)

    def test_agendamiento_publico_continua_a_pago_y_confirmacion(self):
        datos = {
            "nombre": "Ana",
            "apellido": "Perez",
            "dni": "12345678",
            "telefono": "999999999",
            "medico_id": "3",
            "fecha_cita": "2026-10-24",
            "metodo_pago": "yape",
            "servicio_id": "2",
        }
        with patch.object(ga, "_validar_datos_cita_rapida", return_value=None), \
                patch.object(
                    ga.citas_client,
                    "post",
                    return_value=({"success": True, "cita_id": 55}, 201),
                ), patch.object(
                    ga.pagos_client, "get", side_effect=self._pagos_get("pendiente")
                ), patch.object(
                    ga.citas_client, "get", side_effect=self._citas_get
                ), patch.object(
                    ga.pacientes_client, "get", side_effect=self._servicios_get
                ):
            response = self.cliente.post(
                "/citas",
                data=datos,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.get_json()["redirect"], "/pago?cita_id=55")

            with self.cliente.session_transaction() as session:
                self.assertEqual(session["cita_pendiente_id"], "55")

            pago = self.cliente.get("/pago?cita_id=55")
            self.assertEqual(pago.status_code, 200)

        with patch.object(
            ga.pagos_client, "get", side_effect=self._pagos_get("pagado")
        ), patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            retorno = self.cliente.get("/retorno?cita_id=55")
        self.assertEqual(retorno.status_code, 200)

    def test_nuevo_agendamiento_reemplaza_la_cita_pendiente(self):
        with self.cliente.session_transaction() as session:
            session["cita_pendiente_id"] = "55"
        datos = {
            "nombre": "Ana",
            "apellido": "Perez",
            "dni": "12345678",
            "telefono": "999999999",
            "medico_id": "3",
            "fecha_cita": "2026-10-24",
            "metodo_pago": "yape",
            "servicio_id": "2",
        }
        with patch.object(ga, "_validar_datos_cita_rapida", return_value=None), \
                patch.object(
                    ga.citas_client,
                    "post",
                    return_value=({"success": True, "cita_id": 56}, 201),
                ), patch.object(
                    ga.pagos_client, "get", side_effect=self._pagos_get("pendiente")
                ), patch.object(
                    ga.citas_client, "get", side_effect=self._citas_get
                ), patch.object(
                    ga.pacientes_client, "get", side_effect=self._servicios_get
                ):
            response = self.cliente.post(
                "/citas",
                data=datos,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
        self.assertEqual(response.status_code, 201)
        with self.cliente.session_transaction() as session:
            self.assertEqual(session["cita_pendiente_id"], "56")


if __name__ == "__main__":
    unittest.main()
