"""Tests de importacion: evitan regresiones como las de FASE 2.

- Que TODOS los modulos del proyecto importen sin NameError (por ejemplo
  `audit_client` sin importar en el gateway, o rutas proxy fuera de
  `create_app()` referenciando `app` inexistente).
- Que `create_app()` de cada microservicio y del gateway construya la app.
"""

import os
import unittest

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-api-de-pruebas")


class ImportModulosTest(unittest.TestCase):
    def test_importa_todos_los_modulos_del_proyecto(self):
        import importlib

        modulos = ["gateway.app", "shared.config", "shared.proc", "shared.audit",
                   "shared.service_auth", "shared.service_client", "shared.validators"]
        for svc in ("auth_service", "pacientes_service", "citas_service",
                    "pagos_service", "notas_service", "audit_service"):
            modulos.append(f"services.{svc}")
            modulos.append(f"services.{svc}.app")
            modulos.append(f"services.{svc}.routes")

        for nombre in modulos:
            with self.subTest(modulo=nombre):
                importlib.import_module(nombre)


class CreateAppTest(unittest.TestCase):
    def test_gateway_crea_app(self):
        from gateway.app import create_app

        app = create_app()
        self.assertTrue(app)
        # La sesion del gateway debe usar la SECRET_KEY del entorno.
        self.assertEqual(app.secret_key, os.environ["SECRET_KEY"])

    def test_microservicios_crean_app(self):
        import importlib

        for svc in ("auth_service", "pacientes_service", "citas_service",
                    "pagos_service", "notas_service", "audit_service"):
            with self.subTest(servicio=svc):
                modulo = importlib.import_module(f"services.{svc}.app")
                app = modulo.create_app()
                self.assertTrue(app)
                self.assertEqual(app.secret_key, os.environ["SECRET_KEY"])

    def test_secret_key_ausente_falla_rapido(self):
        """shared.config debe fallar si no hay SECRET_KEY (nada de claves
        aleatorias silenciosas). Se prueba en un subprocess con un cwd sin
        .env, porque `load_dotenv` vuelve a leer el archivo del disco."""
        import subprocess
        import sys
        import tempfile

        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        codigo = "import shared.config"
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
            env["PYTHONPATH"] = raiz
            proc = subprocess.run(
                [sys.executable, "-c", codigo],
                cwd=tmp, env=env, capture_output=True, text=True,
            )
        self.assertNotEqual(
            proc.returncode, 0,
            "shared.config deberia fallar sin SECRET_KEY, pero arranco bien.\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}",
        )
        self.assertIn("SECRET_KEY", proc.stderr)


if __name__ == "__main__":
    unittest.main()