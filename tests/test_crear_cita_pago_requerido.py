import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402


class CrearCitaPagoRequeridoTest(unittest.TestCase):
    def setUp(self):
        self.client = internal_test_client(ga.create_app())
        self.headers = {"X-Api-Key": API_KEY} if API_KEY else {}
        self.datos = {
            "nombre": "Ana",
            "apellido": "Quispe",
            "dni": "12345678",
            "telefono": "999888777",
            "medico_id": "3",
            "fecha_cita": "2099-10-24",
            "servicio_id": "2",
            "metodo_pago": "yape",
        }

    @staticmethod
    def _pacientes_get(url, *args, **kwargs):
        if url == "/api/terapeutas/3":
            return {"terapeuta": {"precio": 100}}, 200
        if url == "/api/servicios":
            return {"servicios": [{"id": 2, "activo": 1}]}, 200
        if url == "/api/pacientes/dni/12345678":
            return {"id": 42}, 200
        raise AssertionError(f"Llamada inesperada: {url}")

    def _with_prerequisites(self, pacientes_get=None):
        patches = [
            patch(
                "services.citas_service.routes.medico_disponible",
                return_value=True,
            ),
            patch(
                "services.citas_service.routes.pacientes_client.get",
                side_effect=pacientes_get or self._pacientes_get,
            ),
            patch("services.citas_service.routes.log_accion"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def _post(self):
        return self.client.post(
            "/_internal/api/citas", json=self.datos, headers=self.headers
        )

    def test_precio_no_configurado_no_crea_paciente_ni_cita(self):
        self._with_prerequisites(
            pacientes_get=lambda url, *a, **k: (
                {"terapeuta": {"precio": 0}}, 200
            )
        )
        with patch(
            "services.citas_service.routes.call_proc_one"
        ) as proc, patch(
            "services.citas_service.routes.pacientes_client.post"
        ) as pacientes_post:
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.get_json()["error"],
            "Este especialista aún no tiene precio configurado",
        )
        proc.assert_not_called()
        pacientes_post.assert_not_called()

    def test_servicio_inexistente_o_inactivo_rechazado_antes_de_crear_cita(self):
        def sin_servicio(url, *args, **kwargs):
            if url == "/api/terapeutas/3":
                return {"terapeuta": {"precio": 100}}, 200
            if url == "/api/servicios":
                return {"servicios": [{"id": 5}]}, 200
            raise AssertionError(f"Llamada inesperada: {url}")

        self._with_prerequisites(pacientes_get=sin_servicio)
        with patch(
            "services.citas_service.routes.call_proc_one"
        ) as proc, patch(
            "services.citas_service.routes.pacientes_client.post"
        ) as pacientes_post:
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.get_json()["error"], "Servicio no disponible")
        proc.assert_not_called()
        pacientes_post.assert_not_called()

    def test_metodo_pago_invalido_es_rechazado(self):
        self.datos["metodo_pago"] = "bitcoin"
        with patch(
            "services.citas_service.routes.medico_disponible"
        ) as disponible:
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 400)
        disponible.assert_not_called()

    def test_pago_no_creado_cancela_cita_y_no_devuelve_201(self):
        self._with_prerequisites()
        with patch(
            "services.citas_service.routes.call_proc_one",
            side_effect=[
                {"id": 88},
                {"actualizadas": 1},
            ],
        ) as proc, patch(
            "services.citas_service.routes.pagos_client.post",
            return_value=({"error": "fallo"}, 503),
        ), patch(
            "services.citas_service.routes.call_proc_execute"
        ):
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(
            respuesta.get_json()["error"],
            "No se pudo iniciar el pago, intenta de nuevo",
        )
        self.assertEqual(
            proc.call_args_list[-1].args,
            ("sp_cancelar_cita", (88,)),
        )

    def test_excepcion_al_iniciar_pago_cancela_cita(self):
        self._with_prerequisites()
        with patch(
            "services.citas_service.routes.call_proc_one",
            side_effect=[
                {"id": 89},
                {"actualizadas": 1},
            ],
        ) as proc, patch(
            "services.citas_service.routes.pagos_client.post",
            side_effect=RuntimeError("pagos fuera de servicio"),
        ):
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(len(proc.call_args_list), 2)
        self.assertEqual(
            proc.call_args_list[-1].args,
            ("sp_cancelar_cita", (89,)),
        )

    def test_respuesta_201_sin_pago_creado_cancela_cita(self):
        self._with_prerequisites()
        with patch(
            "services.citas_service.routes.call_proc_one",
            side_effect=[{"id": 91}, {"actualizadas": 1}],
        ) as proc, patch(
            "services.citas_service.routes.pagos_client.post",
            return_value=({"success": True, "id": None}, 201),
        ):
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(
            proc.call_args_list[-1].args,
            ("sp_cancelar_cita", (91,)),
        )

    def test_creacion_exige_pago_exitoso(self):
        self._with_prerequisites()
        with patch(
            "services.citas_service.routes.call_proc_one",
            return_value={"id": 90},
        ), patch(
            "services.citas_service.routes.pagos_client.post",
            return_value=({"success": True, "id": 17}, 201),
        ):
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.get_json()["cita_id"], 90)


class PagoPageSinPagoTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["usuario_id"] = 1
            session["rol"] = "paciente"

    def test_sin_registro_de_pago_redirige_a_citas_con_mensaje(self):
        for status, data in ((404, {}), (200, {}), (200, {"pago": None})):
            with self.subTest(status=status, data=data), patch.object(
                ga.pagos_client, "get", return_value=(data, status)
            ), patch.object(ga.citas_client, "get") as citas_get:
                respuesta = self.client.get("/pago?cita_id=55")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/citas", respuesta.headers["Location"])
            citas_get.assert_not_called()
            with self.client.session_transaction() as session:
                self.assertEqual(session["_flashes"][-1][1],
                                 "No encontramos el pago de esta cita. Vuelve a agendarla.")


if __name__ == "__main__":
    unittest.main()
