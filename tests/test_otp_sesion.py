"""S1: verificacion OTP obligatoria en el gateway.

Antes de este cambio bastaba un CSRF valido para:

  * leer las citas de cualquier DNI con un simple
    GET /citas/cancelar?paso=citas&dni=12345678
  * cancelar o modificar la cita de cualquiera con un POST que solo
    trajera un cita_id.

Ahora la sesion guarda {dni, accion, ts} por accion al verificar, y
tanto los GET de datos como los POST de mutacion exigen ese sello
vigente (y ademas que la cita pertenezca al dni verificado).

Nota sobre las aserciones: modificar y tratamiento piden la lista de
terapeutas al entrar en la vista, antes de cualquier guardia, y eso no
son datos de salud. Por eso se comprueba que no se pidieron datos de
ESE dni, no que no se haya hecho ninguna llamada.
"""
import os
import sys
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import session

from gateway.app import _otp_vigente
from gateway.app import create_app as crear_gateway
from shared.config import OTP_SESION_MIN

DNI_A = "12345678"
DNI_B = "87654321"
MARCA = "DATO_DE_SALUD_RESERVADO"

# Citas asociadas a DNI_A en la respuesta del módulo.
CITAS_A = [
    {"id": 11, "dni": DNI_A, "fecha_cita": "2026-11-25"},
    {"id": 12, "dni": DNI_A, "fecha_cita": "2026-12-02"},
]
CITA_AJENA = 99


def _respuesta_citas(dni):
    """Listado marcado (la marca va en `nombre`, que es lo que imprime
    la plantilla) para detectar si llego a renderizarse."""
    if dni != DNI_A:
        return {"success": True, "citas": []}, 200
    return {"success": True, "citas": [
        dict(c, nombre=MARCA, apellido="Paciente") for c in CITAS_A
    ]}, 200


class BaseOTP(unittest.TestCase):
    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    # --- utilidades de sesion ---

    def _sellar(self, dni, accion, ts=None):
        """Escribe el sello directamente en la sesion (S1)."""
        with self.client.session_transaction() as s:
            verificaciones = dict(s.get("otp_verificado") or {})
            verificaciones[accion] = {
                "dni": dni,
                "ts": time.time() if ts is None else ts,
            }
            s["otp_verificado"] = verificaciones

    def _sellar_expirado(self, dni, accion):
        self._sellar(dni, accion, ts=time.time() - (OTP_SESION_MIN + 1) * 60)

    def _sello(self):
        with self.client.session_transaction() as s:
            return dict(s.get("otp_verificado") or {})

    # --- sustitutos ---

    @staticmethod
    def _falso_get_citas(path, **kwargs):
        """citas_client.get controlado: terapeutas, listado por dni u
        otro, todo responde sin salir del proceso. Devuelve las citas
        del DNI que se pide, no las de todos, para que una verificacion
        ajena no pase por accidente."""
        if "terapeutas" in path:
            return {"success": True, "terapeutas": [
                {"ID": 3, "Nombre": "Dra. Becky", "usuario_id": 30},
            ]}, 200
        if "dni=" in path:
            dni = path.split("dni=", 1)[1].split("&", 1)[0]
            return _respuesta_citas(dni)
        return {"success": True, "citas": []}, 200

    @classmethod
    def _contexto_citas(cls):
        return (
            patch("gateway.app.citas_client.get",
                  side_effect=cls._falso_get_citas),
            patch("gateway.app.citas_client.delete",
                  return_value=({"success": True}, 200)),
            patch("gateway.app.citas_client.put",
                  return_value=({"success": True}, 200)),
        )

    @staticmethod
    def _pidio_datos_de(mock_get, dni):
        """True si alguna llamada filtro por ese DNI: eso es lo que no
        debe pasar sin verificacion."""
        return any(
            f"dni={dni}" in (c.args[0] if c.args else "")
            for c in mock_get.call_args_list
        )

    @staticmethod
    def _falso_post_otp(path, json_data=None, **kwargs):
        if path == "/api/citas/otp/solicitar":
            return {"success": True, "tel_mask": "999***777"}, 200
        if path == "/api/citas/otp/verificar":
            return {"resultado": "ok"}, 200
        raise AssertionError(f"ruta OTP inesperada: {path}")


class GuardiasDeLecturaTest(BaseOTP):
    """GET que muestra datos de salud: exige sello vigente."""

    def test_cancelar_sin_verificacion_no_muestra_datos(self):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get(f"/citas/cancelar?paso=citas&dni={DNI_A}")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/citas/cancelar", resp.headers["Location"])
        self.assertNotIn(MARCA, resp.get_data(as_text=True))
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_modificar_sin_verificacion_no_muestra_datos(self):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get(f"/citas/modificar?paso=citas&dni={DNI_A}")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/citas/modificar", resp.headers["Location"])
        self.assertNotIn(MARCA, resp.get_data(as_text=True))
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_tratamiento_menu_sin_verificacion_no_muestra_datos(self):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2], \
                patch("gateway.app._paquetes_activos_dni") as paquetes:
            resp = self.client.get(f"/tratamiento?paso=menu&dni={DNI_A}")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/tratamiento", resp.headers["Location"])
        self.assertNotIn(MARCA, resp.get_data(as_text=True))
        paquetes.assert_not_called()
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_tratamiento_sin_paquetes_tambien_esta_protegido(self):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2], \
                patch("gateway.app._paquetes_activos_dni") as paquetes:
            resp = self.client.get(f"/tratamiento?paso=sin_paquetes&dni={DNI_A}")
        self.assertEqual(resp.status_code, 302)
        paquetes.assert_not_called()
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_con_verificacion_si_muestra_los_datos(self):
        self._sellar(DNI_A, "cancelar")
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get(f"/citas/cancelar?paso=citas&dni={DNI_A}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(MARCA, resp.get_data(as_text=True))
        self.assertTrue(self._pidio_datos_de(get, DNI_A))

    def test_con_verificacion_abre_tambien_modificar_y_tratamiento(self):
        self._sellar(DNI_A, "modificar")
        self._sellar(DNI_A, "tratamiento")
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2], \
                patch("gateway.app._paquetes_activos_dni",
                      return_value=({"dni": DNI_A, "id": 7}, [])):
            r1 = self.client.get(f"/citas/modificar?paso=citas&dni={DNI_A}")
            r2 = self.client.get(f"/tratamiento?paso=menu&dni={DNI_A}")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(self._pidio_datos_de(get, DNI_A))

    def test_el_sello_de_un_dni_no_sirve_para_otro(self):
        self._sellar(DNI_A, "cancelar")
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get(f"/citas/cancelar?paso=citas&dni={DNI_B}")
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn(MARCA, resp.get_data(as_text=True))
        self.assertFalse(self._pidio_datos_de(get, DNI_B))

    def test_el_sello_de_una_accion_no_sirve_para_otra(self):
        self._sellar(DNI_A, "cancelar")
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2], \
                patch("gateway.app._paquetes_activos_dni") as paquetes:
            r_mod = self.client.get(f"/citas/modificar?paso=citas&dni={DNI_A}")
            r_tra = self.client.get(f"/tratamiento?paso=menu&dni={DNI_A}")
        self.assertEqual(r_mod.status_code, 302)
        self.assertEqual(r_tra.status_code, 302)
        paquetes.assert_not_called()
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_verificacion_expirada_no_muestra_datos(self):
        self._sellar_expirado(DNI_A, "cancelar")
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get(f"/citas/cancelar?paso=citas&dni={DNI_A}")
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn(MARCA, resp.get_data(as_text=True))
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_limite_de_expiracion_es_inclusive(self):
        """transcurrido == OTP_SESION_MIN sigue vigente; un milisegundo
        despues ya no. Se comprueba con `ahora` explicito para que la
        prueba no dependa de cuanto tarde el reloj entre dos lineas."""
        with self.app.test_request_context():
            session["otp_verificado"] = {
                "cancelar": {"dni": DNI_A, "ts": 500.0},
            }
            en_el_limite = 500.0 + OTP_SESION_MIN * 60
            self.assertTrue(_otp_vigente(DNI_A, "cancelar", ahora=en_el_limite))
            self.assertFalse(_otp_vigente(DNI_A, "cancelar",
                                          ahora=en_el_limite + 0.001))

    def test_dni_mal_formado_no_pide_datos(self):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2]:
            resp = self.client.get("/citas/cancelar?paso=citas&dni=123")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._pidio_datos_de(get, "123"))


class GuardiasDeEscrituraTest(BaseOTP):
    """POST que muta una cita: exige sello vigente y cita propia."""

    def _post_cancelar(self, cita_id, dni=None):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1] as delete, ctx[2]:
            resp = self.client.post("/citas/cancelar", data={
                "accion": "confirmar", "cita_id": str(cita_id),
            })
        return resp, get, delete

    def _post_modificar(self, cita_id):
        ctx = self._contexto_citas()
        with ctx[0] as get, ctx[1], ctx[2] as put:
            resp = self.client.post("/citas/modificar", data={
                "accion": "guardar", "cita_id": str(cita_id),
                "fecha_cita": "2026-12-31", "medico_id": "3",
            })
        return resp, get, put

    def test_cancelar_sin_verificacion_da_403(self):
        resp, get, delete = self._post_cancelar(11)
        self.assertEqual(resp.status_code, 403)
        delete.assert_not_called()
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_cancelar_cita_ajena_da_403_sin_llamar_al_servicio(self):
        self._sellar(DNI_A, "cancelar")
        resp, _get, delete = self._post_cancelar(CITA_AJENA)
        self.assertEqual(resp.status_code, 403)
        delete.assert_not_called()

    def test_cancelar_cita_propia_si_se_ejecuta(self):
        self._sellar(DNI_A, "cancelar")
        resp, get, delete = self._post_cancelar(11)
        self.assertEqual(resp.status_code, 200)
        delete.assert_called_once_with("/api/citas/11")
        # La comprobacion de pertenencia si consulto las citas de ese dni.
        self.assertTrue(self._pidio_datos_de(get, DNI_A))

    def test_cancelar_cita_ajena_con_verificacion_de_otro_dni(self):
        # Sello valido pero de otro paciente: el 11 no esta en su lista.
        self._sellar(DNI_B, "cancelar")
        resp, _get, delete = self._post_cancelar(11)
        self.assertEqual(resp.status_code, 403)
        delete.assert_not_called()

    def test_cancelar_verificacion_expirada_da_403(self):
        self._sellar_expirado(DNI_A, "cancelar")
        resp, _get, delete = self._post_cancelar(11)
        self.assertEqual(resp.status_code, 403)
        delete.assert_not_called()

    def test_modificar_sin_verificacion_da_403(self):
        resp, get, put = self._post_modificar(11)
        self.assertEqual(resp.status_code, 403)
        put.assert_not_called()
        self.assertFalse(self._pidio_datos_de(get, DNI_A))

    def test_modificar_cita_ajena_da_403_sin_llamar_al_servicio(self):
        self._sellar(DNI_A, "modificar")
        resp, _get, put = self._post_modificar(CITA_AJENA)
        self.assertEqual(resp.status_code, 403)
        put.assert_not_called()

    def test_modificar_cita_propia_si_se_ejecuta(self):
        self._sellar(DNI_A, "modificar")
        resp, get, put = self._post_modificar(11)
        self.assertEqual(resp.status_code, 200)
        put.assert_called_once()

    def test_verificacion_de_cancelar_no_habilita_modificar(self):
        self._sellar(DNI_A, "cancelar")
        resp, _get, put = self._post_modificar(11)
        self.assertEqual(resp.status_code, 403)
        put.assert_not_called()

    def test_el_bloqueo_es_antes_de_consultar_cualquier_cita(self):
        # Sin sello no se llega ni a pedir las citas del dni.
        resp, get, delete = self._post_cancelar(11)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self._pidio_datos_de(get, DNI_A))
        delete.assert_not_called()


class FlujoCompletoTest(BaseOTP):
    """De la solicitud del codigo hasta cancelar, sin atajos de sesion."""

    def test_solicitar_verificar_ver_datos_y_cancelar(self):
        ctx = self._contexto_citas()
        with patch("gateway.app.citas_client.post", side_effect=self._falso_post_otp) as post, \
                ctx[0] as get, ctx[1] as delete, ctx[2]:
            # 1) Pide el codigo.
            r = self.client.post("/citas/cancelar", data={
                "accion": "solicitar", "dni": DNI_A,
            })
            self.assertEqual(r.status_code, 200)

            # 2) El exito del OTP deja el sello con la forma pedida.
            r = self.client.post("/citas/cancelar", data={
                "accion": "verificar", "dni": DNI_A, "otp": "123456",
            })
            self.assertEqual(r.status_code, 200)
            sello = self._sello().get("cancelar")
            self.assertIsNotNone(sello, "el OTP verificado no dejo sello")
            self.assertEqual(sello["dni"], DNI_A)
            self.assertIsInstance(sello["ts"], (int, float))

            # 3) Con sello, el paso de citas abre.
            r = self.client.get(f"/citas/cancelar?paso=citas&dni={DNI_A}")
            self.assertEqual(r.status_code, 200)
            self.assertIn(MARCA, r.get_data(as_text=True))

            # 4) Y la cancelacion de su propia cita pasa.
            r = self.client.post("/citas/cancelar", data={
                "accion": "confirmar", "cita_id": "11",
            })
            self.assertEqual(r.status_code, 200)
            delete.assert_called_once_with("/api/citas/11")

        self.assertEqual(post.call_count, 2)
        # Con sello vigente, si se pidieron las citas de ese DNI.
        self.assertTrue(self._pidio_datos_de(get, DNI_A))

    def test_otp_fallido_no_deja_sello(self):
        def falso_post(path, json_data=None, **kwargs):
            if path == "/api/citas/otp/solicitar":
                return {"success": True, "tel_mask": "999***777"}, 200
            if path == "/api/citas/otp/verificar":
                return {"resultado": "incorrecto", "restantes": 2}, 200
            raise AssertionError(path)

        with patch("gateway.app.citas_client.post", side_effect=falso_post):
            self.client.post("/citas/cancelar", data={
                "accion": "verificar", "dni": DNI_A, "otp": "000000",
            })
        self.assertEqual(self._sello(), {})

    def test_modificar_tambien_deja_su_propio_sello(self):
        ctx = self._contexto_citas()
        with patch("gateway.app.citas_client.post",
                   side_effect=self._falso_post_otp), \
                ctx[0], ctx[1], ctx[2]:
            self.client.post("/citas/modificar", data={
                "accion": "verificar", "dni": DNI_A, "otp": "123456",
            })
        sello = self._sello()
        self.assertIn("modificar", sello)
        self.assertNotIn("cancelar", sello)
        self.assertEqual(sello["modificar"]["dni"], DNI_A)

    def test_tratamiento_deja_su_propio_sello(self):
        ctx = self._contexto_citas()
        with patch("gateway.app.citas_client.post",
                   side_effect=self._falso_post_otp), \
                patch("gateway.app._paquetes_activos_dni",
                      return_value=({"dni": DNI_A, "id": 7}, [])), \
                ctx[0], ctx[1], ctx[2]:
            self.client.post("/tratamiento", data={
                "accion": "verificar", "dni": DNI_A, "otp": "123456",
            })
        self.assertIn("tratamiento", self._sello())

    def test_cerrar_sesion_borra_la_verificacion(self):
        self._sellar(DNI_A, "cancelar")
        self.assertIn("cancelar", self._sello())
        self.client.get("/logout")
        self.assertEqual(self._sello(), {})


if __name__ == "__main__":
    unittest.main()
