"""Aviso por SMS al terapeuta al cancelar o reprogramar (FASE 3).

Reglas que se cubren:
  - El aviso NUNCA rompe el DELETE/PUT de la cita.
  - Sin telefono: solo auditoria.
  - DELETE: 1 SMS.
  - PUT con cambio de terapeuta: 2 SMS (pierde + recibe).
  - PUT solo de fecha u hora: 1 SMS.
  - PUT que no toca fecha/hora/terapeuta: 0 SMS.
"""
import os
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.citas_service.app import create_app
from shared.config import API_KEY

Hoy = date(2026, 10, 19)
CITA = {
    "id": 11,
    "paciente_id": 7,
    "terapeuta_id": 3,
    "fecha_cita": date(2026, 10, 25),
    "hora_cita": timedelta(hours=10),
    "estado": "programada",
    "descripcion": "Dolor lumbar",
}

TELEFONOS = [
    {"ID": 3, "usuario_id": 30, "Nombre": "Dra. Becky", "Especialidad": "Fisio"},
    {"ID": 5, "usuario_id": 31, "Nombre": "Jordy", "Especialidad": "Fisio"},
]
USUARIOS = [
    {"id": 30, "nombre": "Dra. Becky", "correo": "becky@moova.com", "telefono": "999888777"},
    {"id": 31, "nombre": "Jordy", "correo": "jordy@moova.com", "telefono": "999111222"},
]


class AvisoTerapeutaBase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}
        self.cita = dict(CITA)
        self.telefonos = {30: "999888777", 31: "999111222"}
        self.sms_ok = True
        self.sms_textos = []

    # ---- sustitutos ----

    def _proc_one(self, nombre, params=(), db_name=None):
        if nombre == "sp_medico_disponible":
            return {"n": 0}
        if nombre == "sp_modificar_cita":
            return {"actualizadas": 1}
        if nombre == "sp_cancelar_cita":
            return {"actualizadas": 1}
        if nombre == "sp_detalle_cita":
            return dict(self.cita)
        return None

    def _get_pacientes(self, url, **kwargs):
        if "terapeutas" in url:
            return {"terapeutas": TELEFONOS}, 200
        return {"pacientes": [
            {"id": 7, "nombre": "Ana", "apellido": "Torres",
             "dni": "47896066", "telefono": "999111222"},
        ]}, 200

    def _get_auth(self, url, **kwargs):
        # self.telefonos es por usuario: sin telefono es None para ese
        # usuario, no para todos.
        return {"success": True, "usuarios": [
            dict(u, telefono=self.telefonos.get(u["id"])) for u in USUARIOS
        ]}, 200

    def _falso_sms(self, telefono, texto):
        self.sms_textos.append((telefono, texto))
        return self.sms_ok

    def _contexto(self):
        """Todos los sustitutos, ya activados. Devuelve (sms, log)."""
        self._stack = ExitStack()
        self._stack.enter_context(
            patch("services.citas_service.routes.call_proc_one",
                  side_effect=self._proc_one))
        self._stack.enter_context(
            patch("services.citas_service.routes.call_proc_execute"))
        self._stack.enter_context(
            patch("services.citas_service.routes.pacientes_client.get",
                  side_effect=self._get_pacientes))
        self._stack.enter_context(
            patch("services.citas_service.routes.auth_client.get",
                  side_effect=self._get_auth))
        self._stack.enter_context(
            patch("services.citas_service.routes.pagos_client.post",
                  return_value=({}, 200)))
        sms = self._stack.enter_context(
            patch("services.citas_service.routes._enviar_sms",
                  side_effect=self._falso_sms))
        log = self._stack.enter_context(
            patch("services.citas_service.routes.log_accion"))
        self._stack.enter_context(
            patch("services.citas_service.routes._hoy_lima", return_value=Hoy))
        return sms, log

    def _avisos(self, log):
        """Registros de auditoria de aviso como lista de detalles."""
        return [
            c.kwargs.get("detalle", "")
            for c in log.call_args_list
            if c.kwargs.get("accion") == "avisar_terapeuta"
        ]


class AvisoEnDeleteTest(AvisoTerapeutaBase):
    def _delete(self):
        sms, log = self._contexto()
        try:
            resp = self.client.delete("/api/citas/11", headers=self.cab)
        finally:
            self._stack.close()
        self.sms = sms
        self.log = log
        return resp

    def test_envia_un_solo_sms(self):
        resp = self._delete()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        self.assertEqual(len(self.sms_textos), 1)
        telefono, texto = self.sms_textos[0]
        self.assertEqual(telefono, "999888777")
        self.assertEqual(
            texto,
            "MOOVA Clinic: Se libero tu cita del 25/10 a las 10:00 (paciente Ana).",
        )

    def test_sms_sin_tildes_sin_dni_ni_telefono_del_paciente(self):
        self._delete()
        texto = self.sms_textos[0][1]
        texto.encode("ascii")  # lanza si hay tildes
        self.assertNotIn("47896066", texto)      # DNI
        self.assertNotIn("999111222", texto)     # telefono del paciente
        self.assertNotIn("Torres", texto)        # solo el nombre de pila

    def test_sin_telefono_solo_auditoria(self):
        self.telefonos = {30: None, 31: None}
        resp = self._delete()
        self.assertEqual(resp.status_code, 200)   # no se rompe
        self.assertEqual(self.sms_textos, [])     # no hay a quien enviarle
        avisos = self._avisos(self.log)
        self.assertEqual(len(avisos), 1)
        self.assertIn("sin_telefono", avisos[0])
        self.assertIn("cita_cancelada", avisos[0])

    def test_sms_fallido_no_rompe_el_delete(self):
        self.sms_ok = False
        resp = self._delete()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        avisos = self._avisos(self.log)
        self.assertEqual(len(avisos), 1)
        self.assertIn("sms_fallido", avisos[0])

    def test_servicio_de_auth_caido_no_rompe_el_delete(self):
        def _roto(url, **kwargs):
            raise RuntimeError("auth caido")
        with patch("services.citas_service.routes.call_proc_one",
                   side_effect=self._proc_one), patch(
            "services.citas_service.routes.pacientes_client.get",
            side_effect=self._get_pacientes), patch(
            "services.citas_service.routes.auth_client.get",
            side_effect=_roto), patch(
            "services.citas_service.routes.pagos_client.post",
            return_value=({}, 200)), patch(
            "services.citas_service.routes.log_accion") as log:
            resp = self.client.delete("/api/citas/11", headers=self.cab)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.sms_textos, [])
        self.assertIn("sin_telefono", self._avisos(log)[0])

    def test_cita_inexistente_no_avisa(self):
        def _no_existe(nombre, params=(), db_name=None):
            if nombre == "sp_cancelar_cita":
                return {"actualizadas": 0}
            return self._proc_one(nombre, params, db_name)

        with patch("services.citas_service.routes.call_proc_one",
                   side_effect=_no_existe), patch(
            "services.citas_service.routes.log_accion") as log:
            resp = self.client.delete("/api/citas/11", headers=self.cab)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._avisos(log), [])


class AvisoEnPutTest(AvisoTerapeutaBase):
    def _put(self, cuerpo):
        sms, log = self._contexto()
        try:
            resp = self.client.put("/api/citas/11", json=cuerpo,
                                   headers=self.cab)
        finally:
            self._stack.close()
        self.sms = sms
        self.log = log
        return resp

    def test_cambio_de_terapeuta_envia_dos_sms(self):
        resp = self._put({"fecha_cita": "2026-10-25", "medico_id": 5,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.sms_textos), 2)
        # Al que pierde: con la cita que se libero.
        self.assertEqual(self.sms_textos[0],
                         ("999888777",
                          "MOOVA Clinic: Se libero tu cita del 25/10 a las 10:00 (paciente Ana)."))
        # Al que la recibe: con la nueva.
        self.assertEqual(self.sms_textos[1],
                         ("999111222",
                          "MOOVA Clinic: Te asignaron una cita del 25/10 a las 10:00 (paciente Ana)."))
        avisos = self._avisos(self.log)
        self.assertIn("cita_liberada", avisos[0])
        self.assertIn("cita_asignada", avisos[1])

    def test_cambio_solo_de_fecha_envia_un_sms(self):
        resp = self._put({"fecha_cita": "2026-10-26", "medico_id": 3,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.sms_textos), 1)
        telefono, texto = self.sms_textos[0]
        self.assertEqual(telefono, "999888777")   # mismo terapeuta
        self.assertIn("del 26/10", texto)
        self.assertIn("Tu cita quedo en", texto)

    def test_cambio_solo_de_hora_envia_un_sms(self):
        resp = self._put({"fecha_cita": "2026-10-25", "medico_id": 3,
                          "hora_cita": "11:30"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.sms_textos), 1)
        self.assertIn("a las 11:30", self.sms_textos[0][1])

    def test_sin_cambio_relevante_no_envia_nada(self):
        # Mismo terapeuta, misma fecha y misma hora: el cambio no toca
        # los tres campos que le importan al doctor (por ejemplo otro
        # campo de la cita), asi que no se envia ningun SMS.
        resp = self._put({"fecha_cita": "2026-10-25", "medico_id": 3,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.sms_textos, [])
        self.assertEqual(self._avisos(self.log), [])

    def test_cambio_de_terapeuta_sin_telefono_no_rompe(self):
        self.telefonos = {30: None, 31: None}
        resp = self._put({"fecha_cita": "2026-10-25", "medico_id": 5,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.sms_textos, [])
        avisos = self._avisos(self.log)
        self.assertEqual(len(avisos), 2)
        self.assertTrue(all("sin_telefono" in a for a in avisos))

    def test_sms_fallido_no_rompe_el_put(self):
        self.sms_ok = False
        resp = self._put({"fecha_cita": "2026-10-26", "medico_id": 3,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        self.assertIn("sms_fallido", self._avisos(self.log)[0])

    def test_terapeuta_desconocido_no_rompe_el_put(self):
        resp = self._put({"fecha_cita": "2026-10-25", "medico_id": 99,
                          "hora_cita": "10:00"})
        self.assertEqual(resp.status_code, 200)
        # Al que se le libero la cita si tiene telefono: se le avisa.
        self.assertEqual(len(self.sms_textos), 1)
        self.assertEqual(self.sms_textos[0][0], "999888777")
        # Al nuevo no se le encuentra el contacto: solo auditoria, sin
        # romper el PUT.
        avisos = self._avisos(self.log)
        self.assertEqual(len(avisos), 2)
        self.assertIn("sin_telefono", avisos[1])
        self.assertIn("cita_asignada", avisos[1])


if __name__ == "__main__":
    unittest.main()
