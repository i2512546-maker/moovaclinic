import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from services.pacientes_service.app import create_app
from shared.config import API_KEY

# Respuesta completa que devuelve APIPERU: el flujo de reserva solo usa
# nombres y apellidos, el resto no debe salir del servicio.
API_PERU_COMPLETO = {
    "success": True,
    "data": {
        "nombres": "ANA",
        "apellido_paterno": "PEREZ",
        "apellido_materno": "RUIZ",
        "dni": "12345678",
        "direccion": "Calle Secreta 123",
        "ubigeo": "150101",
        "fecha_nacimiento": "1990-01-01",
        "telefono": "999888777",
        "email": "ana@correo.com",
        "foto": "http://ejemplo/foto.png",
    },
}


class _RespuestaFalsa:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class BuscarDniTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.cab = {"X-Api-Key": API_KEY} if API_KEY else {}

    def test_solo_devuelve_nombres_y_apellidos(self):
        with patch(
            "services.pacientes_service.routes.requests.get",
            return_value=_RespuestaFalsa(API_PERU_COMPLETO),
        ):
            resp = self.client.post(
                "/api/pacientes/buscar_dni",
                json={"dni": "12345678"},
                headers=self.cab,
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]

        # Los campos que el formulario de cita usa siguen presentes.
        self.assertEqual(data["nombres"], "ANA")
        self.assertEqual(data["apellido_paterno"], "PEREZ")
        self.assertEqual(data["apellido_materno"], "RUIZ")

        # Y nada del resto del expediente.
        for sensible in (
            "dni",
            "direccion",
            "ubigeo",
            "fecha_nacimiento",
            "telefono",
            "email",
            "foto",
        ):
            self.assertNotIn(sensible, data)

    def test_soporta_nombres_con_guion_bajo(self):
        payload = {
            "success": True,
            "data": {
                "nombre": "CARLOS",
                "apellidoPaterno": "LOPEZ",
                "apellidoMaterno": "DIAZ",
                "dni": "87654321",
            },
        }
        with patch(
            "services.pacientes_service.routes.requests.get",
            return_value=_RespuestaFalsa(payload),
        ):
            resp = self.client.post(
                "/api/pacientes/buscar_dni",
                json={"dni": "87654321"},
                headers=self.cab,
            )

        data = resp.get_json()["data"]
        self.assertEqual(data["nombres"], "CARLOS")
        self.assertEqual(data["apellido_paterno"], "LOPEZ")
        self.assertEqual(data["apellidoMaterno"], "DIAZ")
        # El frontend puede leer cualquiera de las dos variantes.
        self.assertEqual(data["nombre"], "CARLOS")
        self.assertEqual(data["apellidoPaterno"], "LOPEZ")

    def test_dni_invalido_no_consulta_la_api(self):
        with patch("services.pacientes_service.routes.requests.get") as mock_get:
            resp = self.client.post(
                "/api/pacientes/buscar_dni",
                json={"dni": "123"},
                headers=self.cab,
            )

        self.assertEqual(resp.status_code, 400)
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()