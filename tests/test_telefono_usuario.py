"""Teléfono en PUT /api/auth/usuarios/<id> para avisar al terapeuta.

El teléfono se guarda en usuarios.telefono a través de un procedimiento
NUEVO (sp_actualizar_telefono_usuario) y no tocando la firma de
sp_actualizar_usuario, para que migración y código puedan desplegarse
en cualquier orden sin romper editar usuarios.
"""
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import create_app as crear_gateway
from shared.config import API_KEY
from tests.internal_client import internal_test_client

RUTA = "/_internal/api/auth/usuarios/7"

VALIDOS = ["999888777", "912345678", "900000000"]
INVALIDOS = [
    "888888888",   # no empieza por 9
    "99988877",    # 8 digitos
    "9998887777",  # 10 digitos
    "99988877A",   # letras
    "+51999888777",  # con prefijo: aqui solo se guardan digitos
    " 999 888 777",  # con espacios
    "9998887779",
]


class TelefonoUsuarioTest(unittest.TestCase):
    def setUp(self):
        app = crear_gateway()
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = internal_test_client(app)
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}

    def _put(self, cuerpo, cab=None):
        with patch(
            "services.auth_service.routes.call_proc_execute"
        ) as ejecutar, patch(
            "services.auth_service.routes.call_proc_one", return_value=None
        ), patch(
            "services.auth_service.routes.log_accion"
        ) as log:
            resp = self.client.put(
                RUTA, json=cuerpo, headers=self.cab if cab is None else cab
            )
        self.ejecutar = ejecutar
        self.log = log
        return resp

    def _llamadas_a(self, nombre):
        return [
            (c.args[0], tuple(c.args[1]))
            for c in self.ejecutar.call_args_list
            if c.args and c.args[0] == nombre
        ]

    # ---------------- validacion ----------------

    def test_exige_api_key_interna(self):
        with patch("services.auth_service.routes.call_proc_execute") as proc:
            resp = self.client.put(RUTA, json={"telefono": "999888777"})
        self.assertEqual(resp.status_code, 401)
        proc.assert_not_called()

    def test_telefono_valido_se_guarda(self):
        for tel in VALIDOS:
            with self.subTest(tel=tel):
                resp = self._put({"telefono": tel})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.get_json()["success"])
                self.assertEqual(
                    self._llamadas_a("sp_actualizar_telefono_usuario"),
                    [("sp_actualizar_telefono_usuario", (7, tel))],
                )
                # Solo el telefono: sp_actualizar_usuario no se toca.
                self.assertEqual(self._llamadas_a("sp_actualizar_usuario"), [])

    def test_telefono_invalido_devuelve_400(self):
        for tel in INVALIDOS:
            with self.subTest(tel=tel):
                resp = self._put({"telefono": tel})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("9 digitos", resp.get_json()["error"])
                self.assertEqual(
                    self._llamadas_a("sp_actualizar_telefono_usuario"), []
                )

    def test_vacio_borra_el_telefono(self):
        resp = self._put({"telefono": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"),
            [("sp_actualizar_telefono_usuario", (7, ""))],
        )

    def test_null_tambien_borra(self):
        resp = self._put({"telefono": None})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"),
            [("sp_actualizar_telefono_usuario", (7, ""))],
        )

    def test_no_enviado_no_toca_el_telefono(self):
        resp = self._put({"correo": "nuevo@moova.com"})
        self.assertEqual(resp.status_code, 200)
        # El telefono no se pide al SP...
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"), []
        )
        # ...pero el resto del usuario se guarda como siempre.
        self.assertEqual(len(self._llamadas_a("sp_actualizar_usuario")), 1)

    def test_nada_que_actualizar_devuelve_400(self):
        resp = self._put({})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "Nada que actualizar.")
        self.assertEqual(self._llamadas_a("sp_actualizar_usuario"), [])
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"), []
        )

    def test_telefono_con_otros_campos_guarda_los_dos(self):
        resp = self._put({"nombre": "Dra. Becky", "telefono": "999888777"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._llamadas_a("sp_actualizar_usuario")), 1)
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"),
            [("sp_actualizar_telefono_usuario", (7, "999888777"))],
        )

    def test_rol_desconocido_no_rompe_el_telefono(self):
        # call_proc_one devuelve None para un rol inexistente.
        resp = self._put({"rol": "no_existe", "telefono": "999888777"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._llamadas_a("sp_actualizar_telefono_usuario"),
            [("sp_actualizar_telefono_usuario", (7, "999888777"))],
        )

    # ---------------- auditoria ----------------

    def test_queda_auditado(self):
        self._put({"telefono": "999888777"})
        self.log.assert_called_once()
        kwargs = self.log.call_args.kwargs
        self.assertEqual(kwargs["accion"], "actualizar_usuario")
        self.assertEqual(kwargs["tabla_afectada"], "usuarios")
        self.assertEqual(kwargs["registro_id"], 7)
        self.assertIn("telefono=actualizado", kwargs["detalle"])

    def test_audita_el_borrado_sin_registrar_el_numero(self):
        self._put({"telefono": ""})
        kwargs = self.log.call_args.kwargs
        self.assertEqual(kwargs["accion"], "actualizar_usuario")
        self.assertIn("telefono=borrado", kwargs["detalle"])
        # El numero (dato personal) no se escribe en auditoria.
        self.assertNotIn("999888777", kwargs["detalle"])

    def test_audita_aunque_no_haya_telefono(self):
        self._put({"correo": "nuevo@moova.com"})
        kwargs = self.log.call_args.kwargs
        self.assertEqual(kwargs["accion"], "actualizar_usuario")
        self.assertNotIn("telefono=", kwargs["detalle"])


class PanelTelefonoTest(unittest.TestCase):
    """Columna Teléfono de /panel_admin.

    La misma validación se hace en el gateway: sin ella un número mal
    formado viajaría hasta auth_service solo para recibir un 400.
    """

    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        with self.client.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "admin"
            s["usuario_nombre"] = "Admin"

    def _post(self, telefono, uid="7", fallo=False):
        side_effect = RuntimeError("auth caido") if fallo else None
        with patch(
            "gateway.app.auth_client.put",
            return_value=({"success": True}, 200),
            side_effect=side_effect,
        ) as put:
            resp = self.client.post("/panel_admin", data={
                "accion": "actualizar_telefono",
                "usuario_id": uid,
                "telefono": telefono,
            })
        self.put = put
        return resp

    def test_requiere_sesion_de_admin(self):
        app = crear_gateway()
        app.config["WTF_CSRF_ENABLED"] = False
        resp = app.test_client().post("/panel_admin", data={
            "accion": "actualizar_telefono", "usuario_id": "7",
            "telefono": "999888777",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.headers["Location"])

    def test_acepta_telefono_valido(self):
        resp = self._post("999888777")
        self.assertEqual(resp.status_code, 302)
        self.put.assert_called_once_with(
            "/api/auth/usuarios/7", {"telefono": "999888777"}
        )

    def test_telefono_invalido_no_llama_a_auth(self):
        for tel in ["888888888", "99988877", "9998887777", "99988877A"]:
            with self.subTest(tel=tel):
                resp = self._post(tel)
                self.assertEqual(resp.status_code, 302)
                self.put.assert_not_called()

    def test_vacio_pasa_vacio_para_borrar(self):
        resp = self._post("")
        self.assertEqual(resp.status_code, 302)
        self.put.assert_called_once_with("/api/auth/usuarios/7", {"telefono": ""})

    def test_sin_usuario_no_llama_a_auth(self):
        resp = self._post("999888777", uid="")
        self.assertEqual(resp.status_code, 302)
        self.put.assert_not_called()

    def test_auth_caido_no_tumba_el_panel(self):
        resp = self._post("999888777", fallo=True)
        # 302 = sigue respondiendo el panel, en vez de una pagina 500.
        self.assertEqual(resp.status_code, 302)

    def test_auth_responde_error_se_muestra_como_error(self):
        with patch(
            "gateway.app.auth_client.put",
            return_value=({"error": "telefono invalido"}, 400),
        ) as put:
            resp = self.client.post("/panel_admin", data={
                "accion": "actualizar_telefono",
                "usuario_id": "7",
                "telefono": "999888777",
            })
        self.assertEqual(resp.status_code, 302)
        put.assert_called_once()

    def test_el_panel_muestra_la_columna_con_su_formulario(self):
        usuarios = {"success": True, "usuarios": [
            {"id": 7, "nombre": "Dra. Becky", "correo": "b@moova.com",
             "telefono": "999888777", "rol": "terapeuta", "activo": 1,
             "ultimo_acceso": None},
        ]}
        with patch(
            "gateway.app.auth_client.get", return_value=(usuarios, 200)
        ), patch(
            "gateway.app.pacientes_client.get",
            return_value=({"terapeutas": [], "especialidades": []}, 200),
        ), patch(
            "gateway.app.citas_client.get", return_value=({"citas": []}, 200)
        ):
            resp = self.client.get("/panel_admin")
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.get_data(as_text=True)
        self.assertIn("Teléfono", cuerpo)
        self.assertIn('name="telefono"', cuerpo)
        self.assertIn('value="999888777"', cuerpo)
        self.assertIn('value="actualizar_telefono"', cuerpo)


if __name__ == "__main__":
    unittest.main()
