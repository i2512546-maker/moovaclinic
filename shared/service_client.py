import requests
from shared.config import SERVICE_URLS


class ServiceClient:
    def __init__(self, service_name, timeout=10):
        self.base_url = SERVICE_URLS.get(service_name, "")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}

    def _call(self, method, path, **kwargs):
        try:
            resp = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
            try:
                return resp.json(), resp.status_code
            except ValueError:
                return {}, resp.status_code
        except requests.RequestException:
            return {}, 502

    def get(self, path, **kwargs):
        return self._call("GET", path, **kwargs)

    def post(self, path, json_data=None, **kwargs):
        return self._call("POST", path, json=json_data, **kwargs)

    def put(self, path, json_data=None, **kwargs):
        return self._call("PUT", path, json=json_data, **kwargs)

    def delete(self, path, **kwargs):
        return self._call("DELETE", path, **kwargs)


auth_client = ServiceClient("auth")
pacientes_client = ServiceClient("pacientes")
citas_client = ServiceClient("citas")
pagos_client = ServiceClient("pagos")
notas_client = ServiceClient("notas")