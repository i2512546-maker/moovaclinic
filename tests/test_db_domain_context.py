import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")

from shared.config import (
    AUDIT_DB_NAME,
    AUTH_DB_NAME,
    CITAS_DB_NAME,
    NOTAS_DB_NAME,
    PACIENTES_DB_NAME,
    PAGOS_DB_NAME,
)
from shared.db import DB_NAME, dominio, get_connection


class DbDomainContextTest(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()

    def _database_used(self, db_name=None):
        with patch(
            "shared.db.mysql.connector.connect", return_value=self.connection
        ) as connect:
            get_connection(db_name=db_name)
        return connect.call_args.kwargs["database"]

    def test_contexto_selecciona_base_del_dominio(self):
        with dominio("citas"):
            self.assertEqual(self._database_used(), "moovacloud_citas")

    def test_argumento_explicito_prevalece_sobre_dominio(self):
        with dominio("citas"):
            self.assertEqual(
                self._database_used("base_explicita"), "base_explicita"
            )

    def test_contexto_se_restaura_al_salir(self):
        with dominio("pagos"):
            self.assertEqual(self._database_used(), "moovacloud_pagos")
        self.assertEqual(self._database_used(), DB_NAME)

    def test_rechaza_dominio_desconocido(self):
        with self.assertRaises(ValueError):
            with dominio("desconocido"):
                pass

    def test_hooks_de_los_seis_blueprints_seleccionan_su_base(self):
        from gateway.app import create_app
        from services.audit_service import audit_bp
        from services.auth_service import auth_bp
        from services.citas_service import citas_bp
        from services.notas_service import notas_bp
        from services.pacientes_service import pacientes_bp
        from services.pagos_service import pagos_bp

        app = create_app()
        blueprints = (
            (auth_bp, "auth", AUTH_DB_NAME),
            (pacientes_bp, "pacientes", PACIENTES_DB_NAME),
            (citas_bp, "citas", CITAS_DB_NAME),
            (pagos_bp, "pagos", PAGOS_DB_NAME),
            (notas_bp, "notas", NOTAS_DB_NAME),
            (audit_bp, "audit", AUDIT_DB_NAME),
        )

        for blueprint, nombre, esperado in blueprints:
            with self.subTest(dominio=nombre):
                with app.test_request_context("/_internal/prueba"):
                    before = blueprint.before_request_funcs[None]
                    teardown = blueprint.teardown_request_funcs[None]
                    self.assertTrue(before)
                    self.assertTrue(teardown)
                    for callback in before:
                        callback()
                    try:
                        self.assertEqual(self._database_used(), esperado)
                    finally:
                        for callback in teardown:
                            callback(None)

    def test_contexto_anidado_de_servicio_se_restaura_al_dominio_exterior(self):
        from gateway.app import create_app
        from services.citas_service import citas_bp
        from services.pacientes_service import pacientes_bp

        app = create_app()
        with app.test_request_context("/_internal/citas"):
            citas_bp.before_request_funcs[None][0]()
            try:
                self.assertEqual(self._database_used(), CITAS_DB_NAME)
                with app.test_request_context("/_internal/pacientes"):
                    pacientes_bp.before_request_funcs[None][0]()
                    try:
                        self.assertEqual(
                            self._database_used(), PACIENTES_DB_NAME
                        )
                    finally:
                        pacientes_bp.teardown_request_funcs[None][0](None)
                self.assertEqual(self._database_used(), CITAS_DB_NAME)
            finally:
                citas_bp.teardown_request_funcs[None][0](None)


if __name__ == "__main__":
    unittest.main()
