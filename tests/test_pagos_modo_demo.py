import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from services.pagos_service import providers  # noqa: E402


class PagosSinModoDemoTest(unittest.TestCase):
    def _sin_credenciales(self, proveedor):
        prefijo = proveedor.upper()
        return patch.multiple(
            providers,
            **{
                f"{prefijo}_API_URL": "",
                f"{prefijo}_CLIENT_ID": "",
                f"{prefijo}_CLIENT_SECRET": "",
                f"{prefijo}_MERCHANT_ID": "",
            },
        )

    def test_yape_sin_credenciales_no_simula_cobro(self):
        with self._sin_credenciales("yape"):
            cliente = providers.YapeClient()
            with self.assertRaises(providers.PaymentNotConfigured):
                cliente.crear_cobro(80.0, "Cita", "77")

    def test_plin_sin_credenciales_no_simula_cobro(self):
        with self._sin_credenciales("plin"):
            cliente = providers.PlinClient()
            with self.assertRaises(providers.PaymentNotConfigured):
                cliente.crear_cobro(80.0, "Cita", "77")


if __name__ == "__main__":
    unittest.main()
