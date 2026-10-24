import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-api-de-pruebas")

from flask import Flask, jsonify, request

from shared.service_client import ServiceClient, set_internal_app


class ServiceClientInProcessTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        @self.app.route(
            "/_internal/api/endpoint",
            methods=["GET", "POST", "PUT", "DELETE"],
        )
        def endpoint():
            return jsonify({
                "method": request.method,
                "body": request.get_json(silent=True),
                "query": request.args.get("q"),
                "api_key": request.headers.get("X-Api-Key"),
            }), 201 if request.method == "POST" else 200

        set_internal_app(self.app)
        self.client = ServiceClient("test", timeout=15)

    def test_timeout_explicito_prevalece_sobre_el_default(self):
        with patch.object(
            self.client, "_dispatch", wraps=self.client._dispatch
        ) as dispatch:
            data, status = self.client.get("/api/endpoint", timeout=5)

        self.assertEqual(status, 200)
        self.assertEqual(dispatch.call_args.kwargs["timeout"], 5)
        self.assertEqual(data["method"], "GET")

    def test_sin_timeout_conserva_el_default_y_devuelve_tupla_json_status(self):
        with patch.object(
            self.client, "_dispatch", wraps=self.client._dispatch
        ) as dispatch:
            data, status = self.client.get(
                "/api/endpoint", params={"q": "valor"}
            )

        self.assertEqual(dispatch.call_args.kwargs["timeout"], 15)
        self.assertEqual((data["query"], status), ("valor", 200))
        self.assertEqual(data["api_key"], self.client.headers["X-Api-Key"])

    def test_post_put_delete_envian_verbo_y_cuerpo(self):
        for metodo in ("post", "put", "delete"):
            with self.subTest(metodo=metodo):
                llamada = getattr(self.client, metodo)
                data, status = llamada(
                    "/api/endpoint", {"dato": metodo}
                ) if metodo != "delete" else llamada("/api/endpoint")
                esperado = 201 if metodo == "post" else 200
                self.assertEqual(status, esperado)
                self.assertEqual(data["method"], metodo.upper())
                if metodo != "delete":
                    self.assertEqual(data["body"], {"dato": metodo})

    def test_rechaza_ruta_sin_slash_inicial(self):
        with self.assertRaises(ValueError):
            self.client.get("api/endpoint")


if __name__ == "__main__":
    unittest.main()
