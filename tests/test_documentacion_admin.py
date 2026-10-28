# ============================================================
# S7(e): /apidocs y /apispec_1.json solo para administradores.
#
# flasgger los monta sin proteger y el gateway no tenia ningun
# before_request: cualquiera podia leer el plano completo de la API
# interna, endpoints de pago incluidos.
# ============================================================

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402

# Rutas que flasgger sirve de verdad.
DOCS = ("/apidocs/", "/apispec_1.json")
# Otras dos formas de llegar: sin la barra final y por el index.html,
# que flasgger redirige a su vez a /apidocs/. Ninguna de las dos puede
# acabar en /login si no esta bloqueada.
DOCS_REDIREGIDAS = ("/apidocs", "/apidocs/index.html")


class DocumentacionSoloAdminTest(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()

    def _sesion(self, rol):
        with self.cliente.session_transaction() as s:
            s.clear()
            if rol is not None:
                s["usuario_id"] = 1
                s["rol"] = rol
                s["usuario_nombre"] = "Ana"

    def _leer(self, rol, ruta):
        self._sesion(rol)
        return self.cliente.get(ruta)

    # ---- quien ve la documentacion ----

    def test_admin_ve_las_docs(self):
        for ruta in DOCS:
            with self.subTest(ruta=ruta):
                r = self._leer("admin", ruta)
                self.assertEqual(r.status_code, 200)

    def test_admin_en_las_rutas_redirigidas_acaba_en_las_docs(self):
        """Sin bloquear, /apidocs y /apidocs/index.html acaban en
        /apidocs/ (308 de Flask y 302 de flasgger)."""
        for ruta in DOCS_REDIREGIDAS:
            with self.subTest(ruta=ruta):
                r = self._leer("admin", ruta)
                self.assertIn(r.status_code, (301, 302, 308))
                self.assertIn("/apidocs/", r.headers.get("Location", ""))

    def test_anonimo_se_va_a_login(self):
        for ruta in DOCS + DOCS_REDIREGIDAS:
            with self.subTest(ruta=ruta):
                r = self._leer(None, ruta)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/login", r.headers.get("Location", ""))

    def test_sesion_no_admin_tambien_se_va_a_login(self):
        for rol in ("paciente", "terapeuta"):
            for ruta in DOCS + DOCS_REDIREGIDAS:
                with self.subTest(rol=rol, ruta=ruta):
                    r = self._leer(rol, ruta)
                    self.assertEqual(r.status_code, 302)
                    self.assertIn("/login", r.headers.get("Location", ""))

    def test_solo_admin_con_sesion_valida(self):
        """Rol admin sin usuario en la sesion no vale."""
        with self.cliente.session_transaction() as s:
            s["rol"] = "admin"
        r = self.cliente.get("/apidocs/")
        self.assertEqual(r.status_code, 302)

    def test_el_apispec_no_entra_por_la_puerta_de_apispec_1(self):
        """El numero de spec es una variable: /apispec_2.json tambien
        se corta, no solo el que usa la plantilla."""
        self._sesion(None)
        self.assertEqual(self.cliente.get("/apispec_2.json").status_code, 302)
        self._sesion("admin")
        # que el admin sigue viendo el de verdad
        self.assertEqual(self.cliente.get("/apispec_1.json").status_code, 200)

    # ---- que no se lleve por delante al resto ----

    def test_las_rutas_publicas_siguen_publicas(self):
        for ruta in ("/", "/login"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self._leer(None, ruta).status_code, 200)

    def test_las_demas_rutas_siguen_pidiendo_sesion(self):
        r = self._leer(None, "/panel_admin")
        self.assertEqual(r.status_code, 302)

    def test_estadisticas_publicas_solo_devuelven_agregados(self):
        agregados = {
            "pacientes_recuperados": 12,
            "especialistas": 4,
            "anios_experiencia": 3,
            "tasa_exito": 95,
        }
        with patch("gateway.app.citas_client.get", return_value=(agregados, 200)):
            r = self._leer(None, "/api/estadisticas")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), agregados)
        self.assertEqual(
            set(r.get_json()),
            {
                "pacientes_recuperados",
                "especialistas",
                "anios_experiencia",
                "tasa_exito",
            },
        )

    def test_los_proxies_de_pagos_no_se_ven_afectados(self):
        """El before_request de S7(e) solo mira /apidocs y /apispec:
        los proxies de pago siguen respondiendo con su 403 de S7(c),
        no con redireccion a /login."""
        self._sesion(None)
        r = self.cliente.post("/api/pagos/yape/iniciar", json={"cita_id": 55})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], ga.MENSAJE_PAGO_NO_PERMITIDO)


class ElApispecContieneLoQueProtegemos(unittest.TestCase):
    """El propio spec es lo que estaba expuesto: comprueba que sigue
    existiendo (y por tanto que merece seguir protegido)."""

    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "admin"

    def test_el_spec_deja_ver_las_rutas_de_pago(self):
        r = self.cliente.get("/apispec_1.json")
        self.assertEqual(r.status_code, 200)
        rutas = r.get_json()["paths"]
        self.assertIn("/api/pagos/yape/iniciar", rutas)
        self.assertIn("/api/pagos/plin/estado", rutas)


if __name__ == "__main__":
    unittest.main()
