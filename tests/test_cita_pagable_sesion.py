# ============================================================
# S7(c): los 4 proxies de Yape/Plin del gateway solo los usa la
# sesion que abrio /pago para esa cita.
#
# No tenian _login_required ni filtro ninguno: con saber el id de
# una cita y el de un cobro pagado bastaba para iniciar o consultar
# cobros desde un navegador sin sesion. Ahora la sesion anota la cita
# al abrir /pago y los proxies la exigen.
# ============================================================

import os
import re
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402

CITA = 55
OTRA_CITA = 66
RUTAS = (
    "/api/pagos/yape/iniciar",
    "/api/pagos/plin/iniciar",
    "/api/pagos/yape/estado",
    "/api/pagos/plin/estado",
)


class _Base(unittest.TestCase):
    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "paciente"
            s["usuario_nombre"] = "Ana"

    @staticmethod
    def _pagos_get(url, *a, **k):
        if re.fullmatch(r"/api/pagos/\d+", url):
            return {"pago": {"estado_pago": "pendiente", "monto": 80.0,
                             "metodo_pago": "yape"}}, 200
        return {}, 200

    @staticmethod
    def _citas_get(url, *a, **k):
        if re.fullmatch(r"/api/citas/\d+", url):
            return {"cita": {"id": CITA, "estado": "programada"}}, 200
        return {}, 200

    def _abrir_pago(self, cita_id=CITA, pagos_get=None):
        """GET /pago?cita_id=... con los servicios parcheados."""
        with patch.object(ga.pagos_client, "get",
                          side_effect=pagos_get or self._pagos_get), \
                patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            return self.cliente.get(f"/pago?cita_id={cita_id}")

    def _post(self, ruta, cuerpo, **kwargs):
        """POST a un proxy con pagos_service parcheado. Devuelve
        (respuesta, mock de pagos_client.post)."""
        with patch.object(ga.pagos_client, "post",
                          return_value=({"ok": True, "cobro_id": "cobro-x"}, 200)) as post:
            return self.cliente.post(ruta, json=cuerpo, **kwargs), post

    def _sesion_pagables(self):
        with self.cliente.session_transaction() as s:
            return s.get("citas_pagables")


class FlujoNormalTest(_Base):
    """El camino bueno tiene que seguir funcionando entero."""

    def test_flujo_completo_pago_estado_y_retorno(self):
        # 1. El paciente abre la pagina de pago de su cita.
        r = self._abrir_pago()
        self.assertEqual(r.status_code, 200)

        # 2. Inicia el cobro Yape.
        r, post = self._post(RUTAS[0], {"cita_id": CITA, "cobro_id": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        post.assert_called_once_with(RUTAS[0], {"cita_id": CITA, "cobro_id": "x"})

        # 3. Consulta el estado hasta que la pasarela lo marque pagado.
        r, post = self._post(RUTAS[2], {"cita_id": CITA, "cobro_id": "cobro-x"})
        self.assertEqual(r.status_code, 200)
        post.assert_called_once_with(RUTAS[2], {"cita_id": CITA, "cobro_id": "cobro-x"})

        # 4. El retorno de Niubiz no pasa por la lista y se renderiza
        #    con el pago ya confirmado.
        def pagos_pagado(url, *a, **k):
            if re.fullmatch(r"/api/pagos/\d+", url):
                return {"pago": {"estado_pago": "pagado", "monto": 80.0,
                                 "metodo_pago": "yape"}}, 200
            return {}, 200

        with patch.object(ga.pagos_client, "get", side_effect=pagos_pagado), \
                patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            r = self.cliente.get(f"/retorno?cita_id={CITA}")
        self.assertEqual(r.status_code, 200)

    def test_visitar_pago_anota_la_cita_en_la_sesion(self):
        self._abrir_pago()
        entradas = self._sesion_pagables()
        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0]["cita_id"], str(CITA))
        self.assertIsInstance(entradas[0]["ts"], (int, float))

    def test_pago_ya_pagado_no_anota_nada(self):
        def pagos_pagado(url, *a, **k):
            return {"pago": {"estado_pago": "pagado", "monto": 80.0}}, 200

        r = self._abrir_pago(pagos_get=pagos_pagado)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self._sesion_pagables(), None)


class DenegacionTest(_Base):
    """Todo lo que no sea la sesion que abrio /pago se corta."""

    def test_sin_visitar_pago_los_cuatro_devuelven_403(self):
        for ruta in RUTAS:
            with self.subTest(ruta=ruta):
                r, post = self._post(ruta, {"cita_id": CITA})
                self.assertEqual(r.status_code, 403)
                self.assertEqual(r.get_json()["error"], ga.MENSAJE_PAGO_NO_PERMITIDO)
                post.assert_not_called()

    def test_anonimo_tambien_recibe_403_y_no_redireccion(self):
        cliente = self.app.test_client()
        r = cliente.post(RUTAS[0], json={"cita_id": CITA})
        self.assertEqual(r.status_code, 403)

    def test_cita_distinta_de_la_registrada(self):
        self._abrir_pago(cita_id=CITA)
        r, post = self._post(RUTAS[0], {"cita_id": OTRA_CITA})
        self.assertEqual(r.status_code, 403)
        post.assert_not_called()

    def test_cuerpo_sin_cita(self):
        self._abrir_pago()
        for cuerpo in ({}, {"cita_id": None}, {"cita_id": ""}):
            with self.subTest(cuerpo=cuerpo):
                r, _ = self._post(RUTAS[2], cuerpo)
                self.assertEqual(r.status_code, 403)

    def test_body_no_json_tambien_se_corta(self):
        self._abrir_pago()
        r = self.cliente.post(RUTAS[0], data="cita_id=55",
                              content_type="text/plain")
        self.assertEqual(r.status_code, 403)

    def test_el_mismo_mensaje_para_todos_los_casos(self):
        """403 con texto generico: no distingue entre "no existe",
        "no es tuya" y "caduco", que es lo que evita usarlo de sonda."""
        mensajes = set()
        for ruta in RUTAS:
            r, _ = self._post(ruta, {"cita_id": CITA})
            mensajes.add(r.get_json()["error"])
        self._abrir_pago()
        r, _ = self._post(RUTAS[0], {"cita_id": OTRA_CITA})
        mensajes.add(r.get_json()["error"])
        self.assertEqual(mensajes, {ga.MENSAJE_PAGO_NO_PERMITIDO})


class VigenciaTest(_Base):
    def _vejez(self, ts):
        """Envejece la entrada de la sesion (reescribiendo la lista
        entera, que es lo que marca la sesion como modificada)."""
        with self.cliente.session_transaction() as s:
            entradas = list(s.get("citas_pagables") or [])
            entradas[0]["ts"] = ts
            s["citas_pagables"] = entradas

    def test_dentro_de_las_dos_horas_pasa(self):
        self._abrir_pago()
        self._vejez(time.time() - (2 * 3600) + 60)
        r, post = self._post(RUTAS[0], {"cita_id": CITA})
        self.assertEqual(r.status_code, 200)
        post.assert_called_once()

    def test_pasadas_das_horas_se_corta(self):
        self._abrir_pago()
        self._vejez(time.time() - (2 * 3600) - 1)
        r, post = self._post(RUTAS[2], {"cita_id": CITA})
        self.assertEqual(r.status_code, 403)
        post.assert_not_called()

    def test_ts_no_numerico_se_corta(self):
        self._abrir_pago()
        self._vejez("ayer")
        r, _ = self._post(RUTAS[0], {"cita_id": CITA})
        self.assertEqual(r.status_code, 403)

    def test_como_maximo_diez_citas(self):
        """Si un navegador abre muchas paginas de pago no crece sin
        limite: se quedan las diez ultimas."""
        with patch.object(ga.pagos_client, "get", side_effect=self._pagos_get), \
                patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            for cita_id in range(1, 12):
                self.assertEqual(self._abrir_pago(cita_id=cita_id).status_code, 200)

        entradas = self._sesion_pagables()
        self.assertEqual(len(entradas), ga.MAX_CITAS_PAGABLES)
        citase = [e["cita_id"] for e in entradas]
        self.assertNotIn("1", citase)          # la mas antigua se cayo
        self.assertIn("11", citase)            # y la ultima esta
        self.assertEqual(citase, sorted(citase, key=int))

    def test_reabrir_la_misma_cita_no_duplica(self):
        self._abrir_pago()
        self._abrir_pago()
        entradas = self._sesion_pagables()
        self.assertEqual(len(entradas), 1)


class FueraDeAlcanceTest(_Base):
    """Lo que S7(c) NO toca."""

    def test_el_retorno_de_niubiz_no_exige_la_lista(self):
        def pagos_pagado(url, *a, **k):
            if re.fullmatch(r"/api/pagos/\d+", url):
                return {"pago": {"estado_pago": "pagado", "monto": 80.0}}, 200
            return {}, 200

        with patch.object(ga.pagos_client, "get", side_effect=pagos_pagado), \
                patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            r = self.cliente.get(f"/retorno?cita_id={CITA}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._sesion_pagables(), None)

    def test_el_webhook_no_pasa_por_el_gateway(self):
        reglas = {regla.rule for regla in self.app.url_map.iter_rules()}
        self.assertNotIn("/api/pagos/webhook", reglas)
        # Sigue existiendo en pagos_service, donde lo autentica el
        # token del proveedor (X-Provider-Token), no la sesion.
        from services.pagos_service.app import create_app as crear_pagos
        rutas = {r.rule for r in crear_pagos().url_map.iter_rules()}
        self.assertIn("/api/pagos/webhook", rutas)

    def test_el_gateway_no_expone_otras_rutas_de_pagos(self):
        """Si el gateway solo publica estas cuatro bajo /api/pagos/,
        esas cuatro son el unico trozo a gatear."""
        reglas = {regla.rule for regla in self.app.url_map.iter_rules()}
        self.assertEqual(sorted(r for r in reglas if r.startswith("/api/pagos/")),
                         sorted(RUTAS))


if __name__ == "__main__":
    unittest.main()
