import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402
from services.citas_service.routes import medico_disponible  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402

RUTA_LIBERAR = "/_internal/api/pagos/mantenimiento/liberar_vencidos"
CABECERAS = {"X-Api-Key": API_KEY} if API_KEY else {}


class ExpirarPagoYCancelarCitaTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.client = internal_test_client(self.app)

    def _expirar_con_estado(self, estado_inicial):
        cita = {"estado": estado_inicial, "descripcion": "nota previa"}

        def ejecutar_proc(nombre, parametros):
            if nombre == "sp_cancelar_cita_pago_vencido":
                if cita["estado"] != "programada":
                    return {"actualizadas": 0}
                cita["estado"] = "cancelada"
                cita["descripcion"] += " | pago vencido"
                return {"actualizadas": 1}
            if nombre == "sp_medico_disponible":
                return {
                    "n": int(cita["estado"] in ("programada", "confirmada"))
                }
            raise AssertionError(f"Procedimiento inesperado: {nombre}")

        with patch(
            "services.pagos_service.routes.call_proc",
            return_value=[{"cita_id": 31}, {"vencidos": 1}],
        ), patch(
            "services.pagos_service.routes.call_proc_execute"
        ) as marcar_liberada, patch(
            "services.citas_service.routes.call_proc_one",
            side_effect=ejecutar_proc,
        ), patch(
            "services.citas_service.routes.log_accion"
        ):
            respuesta = self.client.post(
                RUTA_LIBERAR, json={"horas": 24}, headers=CABECERAS
            )

        return respuesta, cita, marcar_liberada, ejecutar_proc

    def test_pago_vencido_cancela_cita_y_libera_el_dia(self):
        respuesta, cita, marcar_liberada, ejecutar_proc = (
            self._expirar_con_estado("programada")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(cita["estado"], "cancelada")
        self.assertTrue(cita["descripcion"].endswith("pago vencido"))
        marcar_liberada.assert_called_once_with(
            "sp_marcar_citas_pago_vencido_liberadas", (31,)
        )
        with patch(
            "services.citas_service.routes.call_proc_one",
            side_effect=ejecutar_proc,
        ):
            self.assertTrue(medico_disponible(3, "2099-10-24"))

    def test_no_modifica_una_cita_completada(self):
        respuesta, cita, marcar_liberada, _ = self._expirar_con_estado(
            "completada"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(cita, {
            "estado": "completada",
            "descripcion": "nota previa",
        })
        marcar_liberada.assert_called_once()

    def test_pago_anticipo_no_devuelve_201_si_el_procedimiento_no_crea_fila(self):
        with patch(
            "services.pagos_service.routes.call_proc_one", return_value=None
        ):
            respuesta = self.client.post(
                "/_internal/api/pagos/anticipo",
                json={
                    "cita_id": 31,
                    "paciente_id": 42,
                    "monto": 50,
                    "metodo_pago": "yape",
                },
                headers=CABECERAS,
            )
        self.assertEqual(respuesta.status_code, 500)
        self.assertFalse(respuesta.get_json()["success"])


class LimiteCrearCitasTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _post(self, dni=None):
        form = {"dni": dni} if dni else {}
        with patch.object(
            ga.citas_client, "get", return_value=({}, 200)
        ), patch.object(
            ga.pacientes_client, "get", return_value=({}, 200)
        ):
            return self.client.post("/citas", data=form)

    def test_maximo_cinco_intentos_por_ip_por_hora(self):
        for _ in range(5):
            self.assertNotEqual(self._post().status_code, 429)
        respuesta = self._post()
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Límite de citas", respuesta.get_json()["error"])

    def test_maximo_tres_intentos_por_dni_por_hora(self):
        for _ in range(3):
            self.assertNotEqual(self._post("12345678").status_code, 429)
        respuesta = self._post("12345678")
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Límite de citas", respuesta.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
