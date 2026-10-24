# ============================================================
# S7(a): la confirmacion de pago Yape/Plin sale solo de la referencia
# guardada en la base.
#
# Antes /estado aceptaba el cobro_id que mandara el navegador y lo
# consultaba tal cual, asi que cualquiera podia pasarle el id de un
# cobro pagado distinto y marcar su cita como pagada. Ademas, aunque
# consultara el correcto, no comprobaba ni la referencia ni el monto.
# ============================================================

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app  # noqa: E402
from services.pagos_service.routes import _cobro_valido_para_cita  # noqa: E402
from shared.config import API_KEY  # noqa: E402
from tests.internal_client import internal_test_client  # noqa: E402

CABECERAS = {"X-Api-Key": API_KEY} if API_KEY else {}

# Marca para "devuelve el pago pendiente por defecto" en los helpers.
_DEFECTO = object()

CITA_ID = 77
PAGO_PENDIENTE = {
    "cita_id": CITA_ID,
    "estado_pago": "pendiente",
    "monto": 80.0,
    "referencia": "cobro-guardado",
}


def _respuesta(monto=80.0, referencia=CITA_ID, incluir_monto=True, pagado=True):
    """Cuerpo que devuelve consultar_pago()."""
    datos = {"estado": "pagado" if pagado else "pendiente"}
    if referencia is not None:
        datos["referencia"] = referencia
    if incluir_monto:
        datos["monto"] = monto
    return {"pagado": pagado, "datos_respuesta": datos}


class CobroValidoParaCitaTest(unittest.TestCase):
    """La comprobacion en si."""

    def test_acepta_referencia_y_monto_correctos(self):
        self.assertTrue(_cobro_valido_para_cita(_respuesta(), CITA_ID, 80.0))

    def test_rechaza_ajena(self):
        self.assertFalse(_cobro_valido_para_cita(_respuesta(referencia=999), CITA_ID, 80.0))

    def test_rechaza_referencia_vacia(self):
        self.assertFalse(_cobro_valido_para_cita(_respuesta(referencia=None), CITA_ID, 80.0))

    def test_rechaza_monto_distinto(self):
        self.assertFalse(_cobro_valido_para_cita(_respuesta(monto=1.0), CITA_ID, 80.0))

    def test_rechaza_si_no_devuelve_monto(self):
        # Sin monto no hay con que comparar: no se da por bueno.
        self.assertFalse(
            _cobro_valido_para_cita(_respuesta(incluir_monto=False), CITA_ID, 80.0)
        )

    def test_compara_monto_con_centsima_de_tolerancia(self):
        self.assertTrue(_cobro_valido_para_cita(_respuesta(monto=80.005), CITA_ID, 80.0))
        self.assertFalse(_cobro_valido_para_cita(_respuesta(monto=80.02), CITA_ID, 80.0))

    def test_rechaza_si_la_respuesta_no_tiene_cuerpo(self):
        self.assertFalse(_cobro_valido_para_cita({"pagado": True}, CITA_ID, 80.0))
        self.assertFalse(_cobro_valido_para_cita(None, CITA_ID, 80.0))

    def test_acepta_nombres_alternativos_de_campo(self):
        self.assertTrue(
            _cobro_valido_para_cita(
                {"pagado": True, "datos_respuesta": {"reference": str(CITA_ID),
                                                     "amount": 80.0}},
                CITA_ID, 80.0,
            )
        )

    def test_ignora_campos_vacios_y_usa_los_que_vienen(self):
        self.assertTrue(
            _cobro_valido_para_cita(
                {"pagado": True,
                 "datos_respuesta": {"referencia": "", "reference": str(CITA_ID),
                                     "monto": None, "importe": 80.0}},
                CITA_ID, 80.0,
            )
        )


class _BaseEstado(unittest.TestCase):
    """Monta pagos_service con el proveedor y la cita parcheados."""

    proveedor = None      # "YapeClient" o "PlinClient"
    ruta = None

    def setUp(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = internal_test_client(self.app)
        self.confirmaciones = []

    def _pago_pendiente(self, **cambios):
        pago = dict(PAGO_PENDIENTE)
        pago.update(cambios)
        return pago

    def _post(self, cuerpo):
        return self.client.post(self.ruta, json=cuerpo, headers=CABECERAS)

    def _con_proveedor(self, respuesta, cuerpo, pendiente=_DEFECTO):
        """POST con proveedor devolviendo `respuesta`. Devuelve
        (respuesta_http, mock_del_proveedor).

        `pendiente` es lo que devuelve _obtener_pago_pendiente: por
        defecto el de la cita de arriba, None para simular que la cita
        no existe o ya esta pagada.
        """
        if pendiente is _DEFECTO:
            pendiente = self._pago_pendiente()
        cliente = MagicMock()
        cliente.consultar_pago.return_value = respuesta
        with patch("services.pagos_service.routes._obtener_pago_pendiente",
                   return_value=pendiente), \
                patch(f"services.pagos_service.routes.{self.proveedor}",
                      return_value=cliente), \
                patch("services.pagos_service.routes.confirmar_pago_servicio",
                      side_effect=lambda *a, **k: self.confirmaciones.append((a, k))):
            return self._post(cuerpo), cliente


class YapeEstadoTest(_BaseEstado):
    proveedor = "YapeClient"
    ruta = "/_internal/api/pagos/yape/estado"

    def test_no_acepta_el_cobro_id_del_pedido(self):
        """El cobro se toma de la base; el id del navegador se ignora."""
        respuesta, proveedor = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID, "cobro_id": "el-que-sea"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.get_json()["pagado"])
        proveedor.consultar_pago.assert_called_once_with("cobro-guardado")

    def test_igual_funciona_si_el_cliente_no_manda_cobro_id(self):
        respuesta, proveedor = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 200)
        proveedor.consultar_pago.assert_called_once_with("cobro-guardado")

    def test_sin_referencia_guardada_no_consulta_al_proveedor(self):
        respuesta, proveedor = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID},
            pendiente=self._pago_pendiente(referencia=None),
        )
        self.assertEqual(respuesta.status_code, 400)
        proveedor.consultar_pago.assert_not_called()
        self.assertEqual(self.confirmaciones, [])

    def test_pagado_y_valido_se_confirma(self):
        respuesta, _ = self._con_proveedor(_respuesta(), {"cita_id": CITA_ID})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.get_json()["pagado"])
        self.assertEqual(len(self.confirmaciones), 1)
        # La referencia que se guarda es la que ya estaba en la base.
        self.assertEqual(self.confirmaciones[0][1]["referencia"], "cobro-guardado")

    def test_cobro_pagado_de_otra_cita_no_se_confirma(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(referencia=999), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("No se pudo verificar", respuesta.get_json()["error"])
        self.assertEqual(self.confirmaciones, [])

    def test_cobro_por_otro_monto_no_se_confirma(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(monto=1.0), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.confirmaciones, [])

    def test_cobro_sin_monto_no_se_confirma(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(incluir_monto=False), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.confirmaciones, [])

    def test_aun_no_pagado_devuelve_false_sin_confirmar(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(pagado=False), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.get_json()["pagado"])
        self.assertEqual(self.confirmaciones, [])

    def test_cita_inexistente_o_ya_pagada_devuelve_400(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID}, pendiente=None
        )
        self.assertEqual(respuesta.status_code, 400)


class PlinEstadoTest(_BaseEstado):
    proveedor = "PlinClient"
    ruta = "/_internal/api/pagos/plin/estado"

    def test_no_acepta_el_cobro_id_del_pedido(self):
        respuesta, proveedor = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID, "cobro_id": "el-que-sea"}
        )
        self.assertEqual(respuesta.status_code, 200)
        proveedor.consultar_pago.assert_called_once_with("cobro-guardado")

    def test_cobro_pagado_de_otra_cita_no_se_confirma(self):
        respuesta, _ = self._con_proveedor(
            _respuesta(referencia=999), {"cita_id": CITA_ID}
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.confirmaciones, [])

    def test_pagado_y_valido_se_confirma(self):
        respuesta, _ = self._con_proveedor(_respuesta(), {"cita_id": CITA_ID})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(self.confirmaciones), 1)

    def test_sin_referencia_guardada_no_consulta_al_proveedor(self):
        respuesta, proveedor = self._con_proveedor(
            _respuesta(), {"cita_id": CITA_ID},
            pendiente=self._pago_pendiente(referencia=""),
        )
        self.assertEqual(respuesta.status_code, 400)
        proveedor.consultar_pago.assert_not_called()


if __name__ == "__main__":
    unittest.main()
