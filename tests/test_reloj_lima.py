# ============================================================
# S7(f): "hoy" se decide en America/Lima y en un solo sitio.
#
# gateway, citas_service y la ficha PDF tenian cada uno su cuenta de
# "cual es hoy" (dos veces la misma funcion, mas cinco
# datetime.today() y un datetime.now() en el gateway). Con el servidor
# en UTC, a partir de las 19:00 de Lima todo eso miraba ya al dia
# siguiente.
# ============================================================

import os
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

RAIZ = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, str(RAIZ))

import gateway.app as ga  # noqa: E402
from gateway import ficha_pdf  # noqa: E402
from services.citas_service import routes as rutas_citas  # noqa: E402
from shared import fechas  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402

CABECERAS = {"X-Api-Key": API_KEY} if API_KEY else {}

# 03:00 UTC del 20 de octubre = 22:00 del 19 de octubre en Lima (UTC-5).
# Es el instante en el que las dos fechas NO coinciden.
_INSTANTE = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
_FECHA_LIMA = date(2026, 10, 19)
_FECHA_UTC = date(2026, 10, 20)


class _RelojFalso(datetime):
    """Mismo datetime, pero el reloj congelado en _INSTANTE."""

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _INSTANTE.astimezone(tz)
        return _INSTANTE.replace(tzinfo=None)


class RelojUnicoTest(unittest.TestCase):
    def test_hoy_lima_da_la_fecha_de_lima(self):
        with patch.object(fechas, "datetime", _RelojFalso):
            hoy = fechas.hoy_lima()
        self.assertEqual(hoy, _FECHA_LIMA)
        self.assertNotEqual(hoy, _FECHA_UTC)

    def test_hoy_lima_es_un_date(self):
        self.assertIsInstance(fechas.hoy_lima(), date)

    def test_ahora_lima_devuelve_la_hora_de_lima_con_zona(self):
        with patch.object(fechas, "datetime", _RelojFalso):
            ahora = fechas.ahora_lima()
        self.assertEqual((ahora.year, ahora.month, ahora.day), (_FECHA_LIMA.year,
                                                               _FECHA_LIMA.month, _FECHA_LIMA.day))
        self.assertEqual((ahora.hour, ahora.minute), (22, 0))
        self.assertEqual(ahora.utcoffset().total_seconds(), -5 * 3600)

    def test_nadie_conserva_su_propia_copia_de_hoy_lima(self):
        """La version de S5 seguia en gateway y otra en citas_service.
        Ahora los dos usan el mismo objeto de shared.fechas."""
        self.assertFalse(hasattr(ga, "_hoy_lima"))
        self.assertFalse(hasattr(rutas_citas, "_hoy_lima"))
        self.assertIs(ga.hoy_lima, fechas.hoy_lima)
        self.assertIs(rutas_citas.hoy_lima, fechas.hoy_lima)
        self.assertIs(ficha_pdf.ahora_lima, fechas.ahora_lima)


# Relojes que SI se aceptan: el que define el propio modulo y dos que
# no son de calendario (la caducidad del OTP es un contador de minutos
# que escribe y lee el mismo servidor, y el scheduler ya lleva ZONA).
RELOJES_PERMITIDOS = {
    "shared/fechas.py": ("datetime.now(ZONA_LIMA)",),
    "services/citas_service/routes.py": (
        "datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)",
        'datetime.now() > otp["expira_en"]',
    ),
    "services/citas_service/scheduler.py": ("datetime.now(ZONA)",),
}
PATRONES_PROHIBIDOS = ("datetime.now(", "datetime.today(", "date.today(",
                       "datetime.utcnow(", "utcfromtimestamp(")


class NoQuedanRelojesDeMaquinaTest(unittest.TestCase):
    """Barrido por todo el codigo (sin tests) para que nadie vuelva a
    preguntar 'que dia es' con el reloj de la maquina."""

    def _ficheros(self):
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in ("tests", ".venv", "__pycache__") or ".venv" in partes:
                continue
            yield ruta

    def test_solo_los_permitidos_usan_el_reloj_de_la_maquina(self):
        hallazgos = []
        for ruta in self._ficheros():
            rel = ruta.relative_to(RAIZ).as_posix()
            permitidos = RELOJES_PERMITIDOS.get(rel, ())
            with open(ruta, encoding="utf-8") as f:
                for numero, linea in enumerate(f, 1):
                    texto = linea.strip()
                    if not any(p in texto for p in PATRONES_PROHIBIDOS):
                        continue
                    if any(p in texto for p in permitidos):
                        continue
                    hallazgos.append(f"{rel}:{numero}: {texto}")
        self.assertEqual(
            hallazgos, [],
            "Reloj de maquina sin America/Lima (usa hoy_lima/ahora_lima "
            "de shared/fechas.py):\n" + "\n".join(hallazgos),
        )


class InterfazAbreElDiaDeLimaTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "paciente"
            s["usuario_nombre"] = "Ana"

    def _get(self, ruta="/interfaz"):
        with patch.object(fechas, "datetime", _RelojFalso), \
                patch.object(ga.citas_client, "get", return_value=({"citas": []}, 200)), \
                patch.object(
                    ga.pacientes_client,
                    "get",
                    return_value=({"terapeutas": []}, 200),
                ):
            return self.cliente.get(ruta).get_data(as_text=True)

    def test_por_defecto_abre_el_dia_de_lima(self):
        html = self._get()
        # El dia de Lima, no el del servidor (que en UTC ya es el 20).
        self.assertIn(">19/10/2026<", html)
        self.assertNotIn(">20/10/2026<", html)
        self.assertIn('mt-1">Hoy</span>', html)

    def test_el_dia_del_servidor_no_es_hoy(self):
        # 2026-10-20 es "hoy" en UTC y "manana" en Lima: no puede salir
        # la insignia "Hoy" ni pasar por fecha_actual.
        html = self._get("/interfaz?fecha=2026-10-20")
        self.assertNotIn('mt-1">Hoy</span>', html)
        self.assertIn(">20/10/2026<", html)

    def test_pidiendo_el_dia_de_lima_si_es_hoy(self):
        html = self._get("/interfaz?fecha=2026-10-19")
        self.assertIn('mt-1">Hoy</span>', html)


class PanelYDescripcionTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()

    def _entrar(self, rol="admin"):
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = rol
            s["usuario_nombre"] = "Ana"

    def test_la_busqueda_del_panel_usa_la_fecha_de_lima(self):
        self._entrar()
        pedidos = []

        def _citas(ruta, *a, **k):
            pedidos.append(ruta)
            return {"citas": []}, 200

        with patch.object(fechas, "datetime", _RelojFalso), \
                patch.object(ga.pacientes_client, "get", return_value=({}, 200)), \
                patch.object(ga.auth_client, "get", return_value=({}, 200)), \
                patch.object(ga.citas_client, "get", side_effect=_citas):
            self.cliente.get("/panel_admin")
        # El dia 19 en Lima, no el 20 que es "hoy" en el servidor UTC.
        self.assertEqual(pedidos, ["/api/citas?fecha=2026-10-19&estado=programada"])

    def test_guardar_descripcion_vuelve_al_dia_de_lima(self):
        self._entrar("admin")
        with patch.object(fechas, "datetime", _RelojFalso), \
                patch.object(ga.citas_client, "put", return_value=({}, 200)), \
                patch.object(ga, "log_accion"):
            r = self.cliente.post("/guardar_descripcion",
                                  data={"historial_id": "55", "descripcion": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("fecha=2026-10-19", r.headers.get("Location", ""))


class CitasServiceCuentaEnLimaTest(unittest.TestCase):
    """crear_cita rechaza las fechas anteriores a 'hoy'. Con el reloj de
    la maquina en UTC, 2026-10-19 contaria como pasada a las 22:00 de
    Lima del dia 19."""

    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = internal_test_client(self.app)

    def _crear(self, fecha):
        cuerpo = {"nombre": "Ana", "apellido": "Perez", "dni": "45678912",
                  "telefono": "999888777", "medico_id": 1, "fecha_cita": fecha,
                  "servicio_id": 2, "metodo_pago": "yape"}
        with patch.object(fechas, "datetime", _RelojFalso), \
                patch("services.citas_service.routes.medico_disponible",
                      return_value=False):
            return self.client.post(
                "/_internal/api/citas", json=cuerpo, headers=CABECERAS
            )

    def test_la_fecha_de_lima_no_se_rechaza_como_pasada(self):
        r = self._crear("2026-10-19")
        # Llega hasta la disponibilidad del medico, asi que supero la
        # comprobacion de fecha (409 es el medico ocupado, no el pasado).
        self.assertEqual(r.status_code, 409)
        self.assertNotIn("pasada", r.get_json()["error"])

    def test_un_dia_anterior_si_se_rechaza(self):
        r = self._crear("2026-10-18")
        self.assertEqual(r.status_code, 400)
        self.assertIn("en el pasado", r.get_json()["error"])


class FichaPdfTest(unittest.TestCase):
    def test_este_emision_en_lima(self):
        """El pie del PDF se firma con la hora de Lima."""
        with patch.object(fechas, "datetime", _RelojFalso):
            texto = fechas.ahora_lima().strftime("%d/%m/%Y a las %H:%M")
        self.assertEqual(texto, "19/10/2026 a las 22:00")


if __name__ == "__main__":
    unittest.main()
