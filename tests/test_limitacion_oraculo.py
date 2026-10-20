# ============================================================
# S7(d): el oráculo de existencia de citas queda documentado como
# limitación aceptada, y estos tests impiden que el README se
# desincronice del código.
#
# Si alguno de estos falla es que alguien ha tocado el comportamiento
# (por ejemplo añadiendo validación de propiedad en el gateway): hay
# que actualizar el apartado "Oráculo de existencia de citas" de
# README.md, no tapar el test.
# ============================================================

import os
import re
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

import gateway.app as ga  # noqa: E402
from services.pagos_service.app import create_app as crear_pagos  # noqa: E402
from shared.config import API_KEY  # noqa: E402

CABECERAS = {"X-Api-Key": API_KEY} if API_KEY else {}

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "README.md")
APARTADO = "### Oráculo de existencia de citas (limitación aceptada)"


class ReadmeDocumentaElOraculoTest(unittest.TestCase):
    def setUp(self):
        with open(README, encoding="utf-8") as f:
            self.texto = f.read()
        # Texto sin saltos de linea ni marcas de blockquote, para poder
        # buscar frases que en el archivo estan partidas.
        sin_citas = [linea.lstrip("> ") for linea in self.texto.splitlines()]
        self.plano = " ".join(" ".join(sin_citas).split())

    def test_el_apartado_existe(self):
        self.assertIn(APARTADO, self.texto)

    def test_las_tres_respuestas_medidas_estan_en_la_tabla(self):
        """La tabla tiene que seguir describiendo lo que hace el código:
        302 pagada / 200 con 0.00 inexistente / 200 con el importe."""
        for tramo in ("`302` a `/retorno`", "`S/ 0.00`", "existe y está pendiente"):
            with self.subTest(tramo=tramo):
                self.assertIn(tramo, self.texto)

    def test_se_marca_como_aceptada_y_explica_que_quedo_fuera_de_s7(self):
        plano = self.plano
        self.assertIn("Limitación aceptada", plano)
        self.assertIn("queda fuera de S7", plano)
        # y deja constancia de lo que S7 sí cerró
        self.assertIn("ya no pisa pagos pagados", plano)
        self.assertIn("los cuatro proxies de Yape/Plin exigen", plano)


class OraculoEnElCodigoTest(unittest.TestCase):
    """Comportamiento real que describe el apartado del README."""

    def setUp(self):
        self.app = ga.create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "paciente"

    @staticmethod
    def _citas_get(url, *a, **k):
        if re.fullmatch(r"/api/citas/(55|56)", url):
            return {"cita": {"id": 55, "nombre": "Ana", "apellido": "Perez"}}, 200
        return {}, 200

    def _get_pago(self, pagos_get):
        with patch.object(ga.pagos_client, "get", side_effect=pagos_get), \
                patch.object(ga.citas_client, "get", side_effect=self._citas_get):
            return self.cliente.get("/pago?cita_id=%s")

    def test_inexistente_devuelve_200_con_cero(self):
        def pagos_get(url, *a, **k):
            return {}, 200

        r = self._get_pago(pagos_get)
        self.assertEqual(r.status_code, 200)
        self.assertIn("S/ 0.00", r.get_data(as_text=True))

    def test_pendiente_devuelve_200_con_su_importe(self):
        def pagos_get(url, *a, **k):
            return {"pago": {"estado_pago": "pendiente", "monto": 80.0,
                             "metodo_pago": "yape"}}, 200

        r = self._get_pago(pagos_get)
        self.assertEqual(r.status_code, 200)
        self.assertIn("S/ 80.00", r.get_data(as_text=True))

    def test_pagada_devuelve_302_al_retorno(self):
        def pagos_get(url, *a, **k):
            return {"pago": {"estado_pago": "pagado", "monto": 80.0}}, 200

        r = self._get_pago(pagos_get)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/retorno", r.headers.get("Location", ""))


class PagosServiceNoDistingueTest(unittest.TestCase):
    """El medio del recorrido no da informacion: "no existe" y "ya
    estaba pagada" se responden igual."""

    def setUp(self):
        self.app = crear_pagos()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _estado(self, fila):
        with patch("services.pagos_service.routes.call_proc_one",
                   return_value=fila), \
                patch("services.pagos_service.routes.YapeClient") as yape:
            r = self.client.post("/api/pagos/yape/estado",
                                 json={"cita_id": 55}, headers=CABECERAS)
            return r, yape

    def test_no_existe_y_pagada_se_responden_igual(self):
        r_no_existe, yape_no = self._estado(None)
        r_pagada, yape_pag = self._estado(
            {"cita_id": 55, "estado_pago": "pagado", "monto": 80.0}
        )
        self.assertEqual(r_no_existe.status_code, r_pagada.status_code)
        self.assertEqual(r_no_existe.get_json()["error"], r_pagada.get_json()["error"])
        # ademas ninguno llega a consultar a la pasarela
        yape_no.return_value.consultar_pago.assert_not_called()
        yape_pag.return_value.consultar_pago.assert_not_called()


if __name__ == "__main__":
    unittest.main()
