import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.pagos_service.app import create_app
from shared.config import API_KEY

RUTA = "/api/pagos/mantenimiento/liberar_vencidos"


class LiberarPagosVencidosTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}

    def _patch_proc(self, vencidos):
        """Simula sp_liberar_pagos_vencidos devolviendo N filas."""
        return patch(
            "services.pagos_service.routes.call_proc_one",
            return_value={"vencidos": vencidos},
        )

    def test_exige_api_key_interna(self):
        with patch("services.pagos_service.routes.call_proc_one") as proc:
            resp = self.client.post(RUTA, json={"horas": 24})
        self.assertEqual(resp.status_code, 401)
        proc.assert_not_called()

    def test_devuelve_cuantos_vencieron(self):
        with self._patch_proc(3), patch(
            "services.pagos_service.routes.log_accion"
        ):
            resp = self.client.post(
                RUTA, json={"horas": 24}, headers=self.cab
            )
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.get_json()
        self.assertTrue(cuerpo["success"])
        self.assertEqual(cuerpo["vencidos"], 3)
        self.assertEqual(cuerpo["horas"], 24)

    def test_audita_solo_si_hubo_vencidos(self):
        with self._patch_proc(2), patch(
            "services.pagos_service.routes.log_accion"
        ) as log:
            self.client.post(RUTA, json={"horas": 24}, headers=self.cab)
        log.assert_called_once()
        self.assertEqual(
            log.call_args.kwargs["accion"], "liberar_pagos_vencidos"
        )

        with self._patch_proc(0), patch(
            "services.pagos_service.routes.log_accion"
        ) as log:
            self.client.post(RUTA, json={"horas": 24}, headers=self.cab)
        log.assert_not_called()

    def test_rechaza_horas_invalidas(self):
        for horas in (0, -5, "abc", 99999):
            with self._patch_proc(0), patch(
                "services.pagos_service.routes.call_proc_one"
            ) as proc:
                resp = self.client.post(
                    RUTA, json={"horas": horas}, headers=self.cab
                )
            self.assertEqual(resp.status_code, 400, f"horas={horas}")
            proc.assert_not_called()

    def test_sin_cuerpo_usa_24_horas(self):
        with self._patch_proc(0), patch(
            "services.pagos_service.routes.log_accion"
        ):
            resp = self.client.post(RUTA, headers=self.cab)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["horas"], 24)

    def test_auditoria_caida_no_rompe_el_job(self):
        """Si audit_service no responde, el job debe responder igual."""
        with self._patch_proc(5), patch(
            "services.pagos_service.routes.log_accion",
            side_effect=Exception("audit caido"),
        ):
            resp = self.client.post(RUTA, json={"horas": 24}, headers=self.cab)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["vencidos"], 5)


class ScriptCronTest(unittest.TestCase):
    """El script de cron no debe llamar al servicio sin API_KEY."""

    def test_falla_sin_api_key(self):
        import importlib.util

        ruta = os.path.join(
            os.path.dirname(__file__),
            "..",
            "scripts",
            "liberar_pagos_vencidos.py",
        )
        spec = importlib.util.spec_from_file_location("liberar", ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        env_sin = {"PATH": os.environ.get("PATH", "")}
        with patch.dict(os.environ, env_sin, clear=True):
            with patch("sys.argv", ["liberar_pagos_vencidos.py"]):
                self.assertEqual(mod.main(), 1)


if __name__ == "__main__":
    unittest.main()
