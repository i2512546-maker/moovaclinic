"""El pago de una cita solo se da por bueno si pagos_service lo confirmo.

Antes el frontend simulaba el exito de Yape/Plin con un setTimeout y el
gateway dejaba pasar a /retorno cualquier cita creada en la sesin, incluso
sin pagar. Estas pruebas fijan el comportamiento real: se consulta al
servicio y, sin confirmacion, se vuelve al paso de pago.
"""
import os
import re
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402

PLANTILLA_PAGO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "templates", "pago.html")


class VerificacionCobroTest(unittest.TestCase):
    """El JS de pago.html debe consultar la pasarela, no simular el exito."""

    def setUp(self):
        self.html = open(PLANTILLA_PAGO, encoding="utf-8").read()

    def test_modo_demo_tiene_confirmacion_servidor_y_continuar(self):
        self.assertIn("{% if pagos_modo_demo %}", self.html)
        self.assertIn("fetch('/api/pagos/demo/confirmar'", self.html)
        self.assertIn("respuesta.data.pagado", self.html)
        self.assertIn("habilitarContinuar()", self.html)
        self.assertIn("/api/pagos/yape/estado", self.html)
        self.assertIn("/api/pagos/plin/estado", self.html)

    def test_modo_real_sigue_verificando_el_estado_de_la_pasarela(self):
        inicio = self.html.find("function verificarCobro")
        self.assertGreater(inicio, -1, "falta verificarCobro")
        ventana = self.html[inicio:inicio + 1200]
        self.assertIn("res.pagado", ventana)
        self.assertNotIn("setTimeout", ventana)

    def test_verificar_yape_y_plin_usan_el_endpoint_real(self):
        self.assertRegex(self.html, r"function\s+verificarYape\s*\(\s*\)\s*\{\s*verificarCobro\(")
        self.assertRegex(self.html, r"function\s+verificarPlin\s*\(\s*\)\s*\{\s*verificarCobro\(")


class RetornoPageTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "admin"
            s["usuario_nombre"] = "Admin"
            s["cita_pendiente_id"] = 55

    def _get_retorno(self, estado_pago):
        def pagos_get(url, *a, **k):
            if re.fullmatch(r"/api/pagos/\d+", url):
                return {"pago": {"estado_pago": estado_pago, "monto": 80,
                                 "metodo_pago": "yape"}}, 200
            return {}, 200

        with patch.object(ga.pagos_client, "get", side_effect=pagos_get), \
                patch.object(ga.citas_client, "get", side_effect=lambda *a, **k: ({}, 200)):
            return self.cliente.get("/retorno?cita_id=55")

    def test_retorno_bloquea_si_el_pago_no_esta_confirmado(self):
        """Una cita pendiente de pago no debe mostrar la confirmacion,
        aunque se haya creado en esta misma sesion."""
        r = self._get_retorno("pendiente")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/pago", r.headers.get("Location", ""))

    def test_retorno_permite_si_el_pago_esta_confirmado(self):
        r = self._get_retorno("pagado")
        self.assertEqual(r.status_code, 200)

    def test_los_proxies_de_pagos_existen(self):
        reglas = {r.rule for r in self.app.url_map.iter_rules()}
        for ruta in ("/api/pagos/yape/estado", "/api/pagos/plin/estado",
                     "/api/pagos/yape/iniciar", "/api/pagos/plin/iniciar"):
            self.assertIn(ruta, reglas)
        # La confirmación simulada solo debe existir si el modo demo está activado.
        self.assertNotIn("/api/pagos/demo/confirmar", reglas)

    def test_proxy_demo_solo_se_registra_en_modo_demo(self):
        with patch("gateway.app.PAGOS_MODO_DEMO", True):
            app_demo = ga.create_app()
        reglas = {r.rule for r in app_demo.url_map.iter_rules()}
        self.assertIn("/api/pagos/demo/confirmar", reglas)


if __name__ == "__main__":
    unittest.main()
