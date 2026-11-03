import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway
from shared.config import API_KEY
from tests.internal_client import internal_test_client

RUTA = "/_internal/api/citas/riesgo"
PANEL = "/panel_admin/seguimiento"

# Fila tal como la devuelve sp_pacientes_en_riesgo.
FILA = {
    "paciente_id": 7,
    "ultima_cita": date(2026, 8, 30),
    "dias_desde_ultima": 48,
    "citas_programadas": 0,
    "completadas": 5,
    "canceladas": 1,
    "faltas": 2,
}

PACIENTES = {
    7: {"id": 7, "nombre": "Ana", "apellido": "Torres",
        "dni": "47896066", "telefono": "999888777"},
}


class RiesgoEndpointTest(unittest.TestCase):
    def setUp(self):
        app = crear_gateway()
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = internal_test_client(app)
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}

    def _get(self, filas, **params):
        ruta = RUTA
        if params:
            ruta += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        with patch(
            "services.citas_service.routes.call_proc", return_value=filas
        ) as proc, patch(
            "services.citas_service.routes._mapa_pacientes", return_value=PACIENTES
        ):
            resp = self.client.get(ruta, headers=self.cab)
            return resp, proc

    def test_exige_api_key_interna(self):
        with patch("services.citas_service.routes.call_proc") as proc:
            resp = self.client.get(RUTA)
        self.assertEqual(resp.status_code, 401)
        proc.assert_not_called()

    def test_lista_riesgo_con_nombre_y_telefono(self):
        resp, _ = self._get([FILA])
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.get_json()
        self.assertTrue(cuerpo["success"])
        self.assertEqual(cuerpo["total"], 1)
        p = cuerpo["pacientes"][0]
        self.assertEqual(p["paciente_id"], 7)
        # El nombre/telefono vienen de pacientes_service, no de la BD de citas.
        self.assertEqual(p["nombre"], "Ana")
        self.assertEqual(p["apellido"], "Torres")
        self.assertEqual(p["telefono"], "999888777")
        self.assertEqual(p["dni"], "47896066")
        self.assertEqual(p["ultima_cita"], "2026-08-30")

    def test_nivel_medio_si_no_llega_al_doble_del_umbral(self):
        # Umbral 30: el doble es 60. 48 dias con 2 faltas -> medio.
        resp, _ = self._get([FILA])
        p = resp.get_json()["pacientes"][0]
        self.assertEqual(p["nivel"], "medio")

    def test_nivel_alto_por_doble_del_umbral(self):
        fila = dict(FILA, dias_desde_ultima=61)
        resp, _ = self._get([fila])
        p = resp.get_json()["pacientes"][0]
        self.assertEqual(p["nivel"], "alto")

    def test_nivel_alto_por_tres_faltas(self):
        # Con cita futura, pero falto tres veces: tambien es alto.
        fila = dict(FILA, faltas=3, citas_programadas=2, dias_desde_ultima=5)
        resp, _ = self._get([fila])
        cuerpo = resp.get_json()
        p = cuerpo["pacientes"][0]
        self.assertEqual(p["nivel"], "alto")
        self.assertEqual(cuerpo["alto"], 1)
        self.assertEqual(cuerpo["medio"], 0)

    def test_motivo_explica_la_senal(self):
        resp, _ = self._get([FILA])
        p = resp.get_json()["pacientes"][0]
        self.assertEqual(p["motivo"], "Sin cita programada hace 48 dias")

    def test_motivo_cuenta_las_faltas(self):
        fila = dict(FILA, faltas=3, dias_desde_ultima=5)
        resp, _ = self._get([fila])
        self.assertEqual(
            resp.get_json()["pacientes"][0]["motivo"], "3 citas perdidas"
        )

    def test_usa_hoy_en_lima_por_defecto(self):
        with patch(
            "services.citas_service.routes.hoy_lima", return_value=date(2026, 10, 18)
        ), patch(
            "services.citas_service.routes.call_proc", return_value=[]
        ) as proc, patch(
            "services.citas_service.routes._mapa_pacientes", return_value={}
        ):
            resp = self.client.get(RUTA, headers=self.cab)
        proc.assert_called_once_with(
            "sp_pacientes_en_riesgo", (date(2026, 10, 18), 30)
        )
        self.assertEqual(resp.get_json()["fecha"], "2026-10-18")

    def test_acepta_fecha_y_umbral(self):
        resp, proc = self._get([], fecha="2026-11-02", dias_umbral=14)
        self.assertEqual(resp.status_code, 200)
        proc.assert_called_once_with(
            "sp_pacientes_en_riesgo", (date(2026, 11, 2), 14)
        )
        cuerpo = resp.get_json()
        self.assertEqual(cuerpo["dias_umbral"], 14)
        self.assertEqual(cuerpo["total"], 0)
        self.assertEqual(cuerpo["pacientes"], [])

    def test_fecha_invalida_devuelve_400(self):
        resp, proc = self._get([], fecha="ayer")
        self.assertEqual(resp.status_code, 400)
        proc.assert_not_called()

    def test_umbral_no_numerico_devuelve_400(self):
        resp, proc = self._get([], dias_umbral="mucho")
        self.assertEqual(resp.status_code, 400)
        proc.assert_not_called()

    def test_umbral_fuera_de_rango_devuelve_400(self):
        resp, _proc = self._get([], dias_umbral=0)
        self.assertEqual(resp.status_code, 400)
        resp, _proc = self._get([], dias_umbral=999)
        self.assertEqual(resp.status_code, 400)


class RiesgoPanelTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _admin(self):
        with self.client.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "admin"
            s["usuario_nombre"] = "Admin"

    def test_requiere_sesion_de_admin(self):
        r = self.client.get(PANEL)
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r.headers["Location"])

    def test_terapeuta_no_entra(self):
        with self.client.session_transaction() as s:
            s["usuario_id"] = 2
            s["rol"] = "terapeuta"
            s["usuario_nombre"] = "Doc"
        r = self.client.get(PANEL)
        self.assertEqual(r.status_code, 302)

    def test_renderiza_canceladas_y_ausencias_de_la_semana(self):
        self._admin()
        def responder(ruta):
            if "estado=cancelada" in ruta:
                return ({"citas": [{
                    "fecha_cita": "2026-11-03", "hora_cita": "10:00",
                    "nombre": "Ana", "apellido": "Torres", "telefono": "999888777",
                    "terapeuta": "Dra. Vega", "estado": "cancelada", "dni": "47896066",
                }]}, 200)
            return ({"citas": [{
                "fecha_cita": "2026-11-04", "hora_cita": "11:00",
                "nombre": "Luis", "apellido": "Paz", "telefono": "988777666",
                "terapeuta": "Dr. Rojas", "estado": "no_asistio", "dni": "12345678",
            }]}, 200)
        with patch("gateway.app.citas_client.get", side_effect=responder):
            r = self.client.get(PANEL + "?mes=2026-11&semana=2")
        self.assertEqual(r.status_code, 200)
        cuerpo = r.get_data(as_text=True)
        self.assertIn("Ana", cuerpo)
        self.assertIn("Luis", cuerpo)
        self.assertIn("Cancelada", cuerpo)
        self.assertIn("No asistió", cuerpo)
        self.assertIn("Semana del mes", cuerpo)

    def test_consulta_el_rango_de_la_semana_seleccionada(self):
        self._admin()
        with patch(
            "gateway.app.citas_client.get",
            return_value=({"citas": []}, 200),
        ) as get:
            r = self.client.get(PANEL + "?mes=2026-11&semana=2")
        self.assertEqual(r.status_code, 200)
        rutas = [llamada.args[0] for llamada in get.call_args_list]
        self.assertTrue(any("estado=cancelada&fecha=2026-11-02" in ruta for ruta in rutas))
        self.assertTrue(any("estado=no_asistio&fecha=2026-11-02" in ruta for ruta in rutas))

    def test_muestra_error_si_el_servicio_no_responde(self):
        self._admin()
        with patch(
            "gateway.app.citas_client.get", side_effect=RuntimeError("caido")
        ):
            r = self.client.get(PANEL)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Servicio de citas no disponible", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
