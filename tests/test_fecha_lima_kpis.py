# ============================================================
# Tests de S5: el panel de KPIs mide "hoy" en America/Lima.
#
# El servidor puede correr en UTC (Render). Con el reloj de la maquina,
# a partir de las 19:00 de Lima el panel ya estaba mostrando el dia
# siguiente. Se congela el reloj en un instante en el que las dos
# fechas NO coinciden: 03:00 UTC del 20/10 es 22:00 del 19/10 en Lima.
# ============================================================

import os
import sys
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-prueba")
os.environ.setdefault("API_KEY", "clave-api")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway
from shared.fechas import hoy_lima  # noqa: E402

# 03:00 UTC del 20 de octubre = 22:00 del 19 de octubre en Lima (UTC-5).
_INSTANTE = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
_FECHA_LIMA = date(2026, 10, 19)
_FECHA_UTC = date(2026, 10, 20)


class _RelojFalso(datetime):
    """Mismo datetime, pero el reloj congelado en _INSTANTE."""

    @classmethod
    def now(cls, tz=None):
        instante = _INSTANTE
        if tz is not None:
            return instante.astimezone(tz)
        return instante.replace(tzinfo=None)


class HoyLimaTest(unittest.TestCase):
    def test_devuelve_la_fecha_de_lima_no_la_del_servidor(self):
        with patch("shared.fechas.datetime", _RelojFalso):
            hoy = hoy_lima()
        self.assertEqual(hoy, _FECHA_LIMA)
        self.assertNotEqual(hoy, _FECHA_UTC)

    def test_devuelve_un_date(self):
        self.assertIsInstance(hoy_lima(), date)


class PanelKpisTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.pedidos = []

    def _falso_get_kpis(self, path, **kwargs):
        self.pedidos.append(path)
        return {"success": True, "resumen": {}, "por_terapeuta": []}, 200

    def _entrar_como_admin(self):
        with self.client.session_transaction() as s:
            s["usuario_id"] = 1
            s["usuario_nombre"] = "Admin"
            s["rol"] = "admin"

    def test_sin_rango_usa_la_fecha_de_lima(self):
        self._entrar_como_admin()
        with patch("shared.fechas.datetime", _RelojFalso), \
                patch("gateway.app.citas_client.get", side_effect=self._falso_get_kpis):
            self.client.get("/panel_admin/kpis.json")
        self.assertEqual(len(self.pedidos), 1)
        self.assertIn("hasta=2026-10-19", self.pedidos[0])
        self.assertIn("desde=2026-09-19", self.pedidos[0])
        # Y explicitamente, NO la fecha del servidor.
        self.assertNotIn("2026-10-20", self.pedidos[0])

    def test_con_rango_explicito_no_se_toca(self):
        self._entrar_como_admin()
        with patch("shared.fechas.datetime", _RelojFalso), \
                patch("gateway.app.citas_client.get", side_effect=self._falso_get_kpis):
            self.client.get("/panel_admin/kpis.json?desde=2026-01-01&hasta=2026-02-01")
        self.assertIn("desde=2026-01-01&hasta=2026-02-01", self.pedidos[0])

    def test_rango_al_reves_usa_la_fecha_de_lima_como_tope(self):
        self._entrar_como_admin()
        with patch("shared.fechas.datetime", _RelojFalso), \
                patch("gateway.app.citas_client.get", side_effect=self._falso_get_kpis):
            self.client.get("/panel_admin/kpis.json?desde=2026-02-01&hasta=2026-01-01")
        self.assertIn("hasta=2026-10-19", self.pedidos[0])


if __name__ == "__main__":
    unittest.main()
