import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")

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


if __name__ == "__main__":
    unittest.main()
