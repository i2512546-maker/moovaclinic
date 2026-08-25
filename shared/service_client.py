import requests
from shared.config import SERVICE_URLS


class ServiceClient:
    def __init__(self, service_name, timeout=10):
        self.base_url = SERVICE_URLS.get(service_name, "")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}

    def get(self, path, **kwargs):
        resp = requests.get(
            f"{self.base_url}{path}",
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        return resp.json(), resp.status_code

    def post(self, path, json_data=None, **kwargs):
        resp = requests.post(
            f"{self.base_url}{path}",
            json=json_data,
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        return resp.json(), resp.status_code

    def put(self, path, json_data=None, **kwargs):
        resp = requests.put(
            f"{self.base_url}{path}",
            json=json_data,
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        return resp.json(), resp.status_code

    def delete(self, path, **kwargs):
        resp = requests.delete(
            f"{self.base_url}{path}",
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        return resp.json(), resp.status_code


auth_client = ServiceClient("auth")
pacientes_client = ServiceClient("pacientes")
citas_client = ServiceClient("citas")
pagos_client = ServiceClient("pagos")
notas_client = ServiceClient("notas")
