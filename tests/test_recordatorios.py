import os
import sys
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway_app
from services.citas_service import scheduler as sch
from services.citas_service.routes import _mensaje_recordatorio, enviar_recordatorios
from shared.config import API_KEY
from tests.internal_client import internal_test_client

RUTA = "/_internal/api/citas/recordatorios/enviar"

CITA = {
    "id": 11,
    "paciente_id": 7,
    "terapeuta_id": 3,
    "fecha_cita": date(2026, 10, 19),
    "hora_cita": timedelta(hours=10),
}

TERAPEUTAS = {3: {"ID": 3, "Nombre": "Dra. Becky", "Especialidad": "Fisioterapia"}}


def _pacientes(telefono="999888777"):
    return {7: {"id": 7, "nombre": "Ana", "apellido": "Torres", "telefono": telefono}}


class _SchedulerFalso:
    """Sustituto de BackgroundScheduler para no arrancar hilos reales."""

    def __init__(self, timezone=None):
        self.timezone = timezone
        self.jobs = []
        self.running = False

    def add_job(self, *args, **kwargs):
        self.jobs.append((args, kwargs))

    def start(self):
        self.running = True

    def shutdown(self, wait=False):
        self.running = False


class RecordatoriosTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway_app()
        self.client = internal_test_client(self.app)
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}
        self.desmarcas = []

    def _ejecutar(self, citas, marcadas=1, sms=True, telefono="999888777",
                  pacientes=None, fecha=date(2026, 10, 19)):
        """Corre enviar_recordatorios con todo simulado y devuelve
        (resumen, mock del envio, mock de auditoria)."""
        self.desmarcas = []

        def _falso_execute(nombre, params=(), db_name=None):
            self.desmarcas.append((nombre, tuple(params)))
            return None

        with patch(
            "services.citas_service.routes.call_proc", return_value=citas
        ) as proc, patch(
            "services.citas_service.routes.call_proc_one",
            return_value={"marcadas": marcadas},
        ), patch(
            "services.citas_service.routes.call_proc_execute",
            side_effect=_falso_execute,
        ), patch(
            "services.citas_service.routes._enviar_sms", return_value=sms
        ) as enviar, patch(
            "services.citas_service.routes._mapa_pacientes",
            return_value=pacientes or _pacientes(telefono),
        ), patch(
            "services.citas_service.routes._mapa_terapeutas",
            return_value=TERAPEUTAS,
        ), patch(
            "services.citas_service.routes.log_accion"
        ) as log:
            with self.app.app_context():
                resumen = enviar_recordatorios(fecha)
        self.proc_pendientes = proc
        self.enviar = enviar
        self.log = log
        return resumen

    # ---------------- enviar_recordatorios ----------------

    def test_envia_y_marca(self):
        resumen = self._ejecutar([CITA], sms=True)
        self.assertEqual(resumen["total"], 1)
        self.assertEqual(resumen["enviados"], 1)
        self.assertEqual(resumen["fallidos"], 0)
        self.assertEqual(resumen["sin_telefono"], 0)
        # Reclama la cita...
        self.proc_pendientes.assert_called_once_with(
            "sp_citas_pendientes_recordatorio", (date(2026, 10, 19),)
        )
        # ...y no la desmarca porque el SMS salio bien.
        self.assertEqual(self.desmarcas, [])

    def test_sms_falla_desmarca_para_reintentar(self):
        resumen = self._ejecutar([CITA], sms=False)
        self.assertEqual(resumen["enviados"], 0)
        self.assertEqual(resumen["fallidos"], 1)
        self.assertEqual(
            self.desmarcas, [("sp_desmarcar_recordatorio", (11,))]
        )

    def test_marcadas_cero_no_reenvia(self):
        # Otro proceso gano la carrera: marcadas=0.
        resumen = self._ejecutar([CITA], marcadas=0, sms=True)
        self.assertEqual(resumen["total"], 1)
        self.assertEqual(resumen["enviados"], 0)
        self.assertEqual(resumen["fallidos"], 0)
        self.assertEqual(resumen["sin_telefono"], 0)
        self.enviar.assert_not_called()
        self.assertEqual(self.desmarcas, [])

    def test_sin_telefono_no_envia_y_desmarca(self):
        resumen = self._ejecutar([CITA], telefono="", sms=True)
        self.assertEqual(resumen["sin_telefono"], 1)
        self.assertEqual(resumen["enviados"], 0)
        self.enviar.assert_not_called()
        self.assertEqual(
            self.desmarcas, [("sp_desmarcar_recordatorio", (11,))]
        )

    def test_por_defecto_usa_el_dia_siguiente(self):
        with patch(
            "services.citas_service.routes.hoy_lima", return_value=date(2026, 10, 18)
        ), patch(
            "services.citas_service.routes.call_proc", return_value=[]
        ) as proc, patch(
            "services.citas_service.routes.log_accion"
        ), patch(
            "services.citas_service.routes._mapa_pacientes", return_value={}
        ), patch(
            "services.citas_service.routes._mapa_terapeutas", return_value={}
        ):
            with self.app.app_context():
                resumen = enviar_recordatorios()
        proc.assert_called_once_with(
            "sp_citas_pendientes_recordatorio", (date(2026, 10, 19),)
        )
        self.assertEqual(resumen["fecha"], "2026-10-19")

    def test_no_reenvia_si_ya_esta_marcada(self):
        # El SP no devuelve filas marcadas: el segundo ciclo no repite SMS.
        resumen = self._ejecutar([], sms=True)
        self.assertEqual(resumen["total"], 0)
        self.assertEqual(resumen["enviados"], 0)
        self.enviar.assert_not_called()

    def test_audita_el_resumen(self):
        self._ejecutar([CITA], sms=True)
        self.log.assert_called_once()
        self.assertEqual(self.log.call_args.kwargs["accion"], "enviar_recordatorios")

    def test_mensaje_en_ascii_sin_tildes_y_con_terapeuta(self):
        mensaje = _mensaje_recordatorio(
            date(2026, 10, 19), timedelta(hours=10), "Dra. Becky"
        )
        mensaje.encode("ascii")  # lanza si alguna vez se cuela una tilde
        self.assertIn("19/10", mensaje)
        self.assertIn("10:00", mensaje)
        self.assertIn("Dra. Becky", mensaje)
        # Sin acentos (el proveedor SMS se lleva mal con UTF-8).
        self.assertIn("anticipacion", mensaje)
        self.assertNotIn("atención", mensaje)

    def test_mensaje_omite_la_hora_si_no_hay(self):
        mensaje = _mensaje_recordatorio(date(2026, 10, 19), None, None)
        self.assertIn("19/10", mensaje)
        self.assertNotIn("a las", mensaje)


class RecordatoriosEndpointTest(unittest.TestCase):
    def setUp(self):
        app = crear_gateway_app()
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = internal_test_client(app)
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}

    def test_exige_api_key_interna(self):
        with patch(
            "services.citas_service.routes.enviar_recordatorios"
        ) as enviar:
            resp = self.client.post(RUTA, json={})
        self.assertEqual(resp.status_code, 401)
        enviar.assert_not_called()

    def test_dispara_el_envio_y_devuelve_resumen(self):
        with patch(
            "services.citas_service.routes.enviar_recordatorios",
            return_value={
                "fecha": "2026-10-19",
                "total": 2,
                "enviados": 1,
                "fallidos": 1,
                "sin_telefono": 0,
            },
        ) as enviar:
            resp = self.client.post(RUTA, json={}, headers=self.cab)
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.get_json()
        self.assertTrue(cuerpo["success"])
        self.assertEqual(cuerpo["enviados"], 1)
        self.assertEqual(cuerpo["fallidos"], 1)
        # Sin fecha: el dia siguiente.
        enviar.assert_called_once_with(None)

    def test_acepta_fecha_opcional(self):
        with patch(
            "services.citas_service.routes.enviar_recordatorios",
            return_value={
                "fecha": "2026-11-02",
                "total": 0,
                "enviados": 0,
                "fallidos": 0,
                "sin_telefono": 0,
            },
        ) as enviar:
            resp = self.client.post(
                RUTA, json={"fecha": "2026-11-02"}, headers=self.cab
            )
        self.assertEqual(resp.status_code, 200)
        enviar.assert_called_once_with(date(2026, 11, 2))

    def test_fecha_mala_devuelve_400(self):
        with patch(
            "services.citas_service.routes.enviar_recordatorios"
        ) as enviar:
            resp = self.client.post(
                RUTA, json={"fecha": "no-es-fecha"}, headers=self.cab
            )
        self.assertEqual(resp.status_code, 400)
        enviar.assert_not_called()


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway_app()

    def tearDown(self):
        sch.detener_scheduler()

    def test_create_app_no_inicia_el_planificador_por_defecto(self):
        # RECORDATORIOS_ENABLED=0 (default): no debe arrancar nada.
        self.assertEqual(sch.RECORDATORIOS_ENABLED, "0")
        crear_gateway_app()
        self.assertIsNone(sch._scheduler)

    def test_create_app_arranca_si_esta_habilitado(self):
        with patch("shared.config.RECORDATORIOS_ENABLED", "1"), patch.object(
            sch, "RECORDATORIOS_ENABLED", "1"
        ), patch.object(
            sch, "BackgroundScheduler", _SchedulerFalso
        ), patch.object(sch, "_scheduler", None):
            crear_gateway_app()
            self.assertIsNotNone(sch._scheduler)
            self.assertTrue(sch._scheduler.running)
            args, kwargs = sch._scheduler.jobs[0]
            self.assertEqual(args, (sch._job_recordatorios,))
            self.assertEqual(kwargs["id"], "recordatorios_citas")
            self.assertEqual(
                kwargs["minutes"], sch.RECORDATORIO_INTERVALO_MIN
            )

    def test_no_arranca_dos_planificadores(self):
        falso = _SchedulerFalso(timezone=None)
        falso.running = True
        with patch("shared.config.RECORDATORIOS_ENABLED", "1"), patch.object(
            sch, "RECORDATORIOS_ENABLED", "1"
        ), patch.object(
            sch, "BackgroundScheduler", _SchedulerFalso
        ), patch.object(sch, "_scheduler", falso):
            crear_gateway_app()
            # Reutiliza el que ya corre; no crea otro.
            self.assertIs(sch._scheduler, falso)

    def test_job_no_envia_antes_de_la_hora_configurada(self):
        with patch.object(sch, "_hora_pasada", return_value=False), patch(
            "services.citas_service.routes.enviar_recordatorios"
        ) as enviar:
            with self.app.app_context():
                sch._job_recordatorios(self.app)
        enviar.assert_not_called()

    def test_job_envia_si_ya_paso_la_hora(self):
        with patch.object(sch, "_hora_pasada", return_value=True), patch(
            "services.citas_service.routes.enviar_recordatorios",
            return_value={"total": 0, "enviados": 0, "fallidos": 0},
        ) as enviar:
            with self.app.app_context():
                sch._job_recordatorios(self.app)
        enviar.assert_called_once_with()

    def test_job_atrapa_errores(self):
        # Un fallo del job no debe tumbar el proceso.
        with patch.object(sch, "_hora_pasada", return_value=True), patch(
            "services.citas_service.routes.enviar_recordatorios",
            side_effect=RuntimeError("boom"),
        ):
            with self.app.app_context():
                sch._job_recordatorios(self.app)  # no lanza

    def test_hora_pasada_compara_con_lima(self):
        # 18:05 en Lima: ya es hora de avisar el dia siguiente...
        reloj = type("Reloj", (), {
            "now": staticmethod(lambda tz=None: datetime(2026, 10, 18, 18, 5, tzinfo=sch.ZONA)),
        })
        with patch.object(sch, "datetime", reloj):
            self.assertTrue(sch._hora_pasada("18:00"))
            # ...pero no si la hora minima es mas tarde.
            self.assertFalse(sch._hora_pasada("18:06"))

    def test_hora_pasada_malformada_usa_el_defecto(self):
        reloj = type("Reloj", (), {
            "now": staticmethod(lambda tz=None: datetime(2026, 10, 18, 10, 0, tzinfo=sch.ZONA)),
        })
        with patch.object(sch, "datetime", reloj):
            # "basura" cae al 18:00 por defecto: a las 10am no envia.
            self.assertFalse(sch._hora_pasada("basura"))


if __name__ == "__main__":
    unittest.main()
