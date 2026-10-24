from flask import current_app, has_app_context

from shared.config import API_KEY

_internal_app = None


def set_internal_app(app):
    """Guarda la app monolitica para llamadas fuera de una petición."""
    global _internal_app
    _internal_app = app


class ServiceClient:
    def __init__(self, service_name, timeout=15):
        self.service_name = service_name
        self.timeout = timeout
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": (API_KEY or ""),
        }

    @staticmethod
    def _get_app():
        if has_app_context():
            return current_app._get_current_object()
        if _internal_app is None:
            raise RuntimeError(
                "ServiceClient necesita una app Flask configurada para "
                "despachar llamadas internas."
            )
        return _internal_app

    def _dispatch(self, method, path, json_data=None, timeout=None, **kwargs):
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("La ruta del servicio debe comenzar con '/'.")

        app = self._get_app()
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        params = kwargs.pop("params", None)
        if params is not None:
            kwargs.setdefault("query_string", params)

        # El parámetro timeout se conserva en la interfaz. Como la llamada
        # ya no usa socket, no existe un timeout de red que aplicar.
        _ = timeout
        with app.app_context():
            with app.test_client(use_cookies=False) as client:
                response = client.open(
                    f"/_internal{path}",
                    method=method,
                    json=json_data,
                    headers=headers,
                    **kwargs,
                )
        return response.get_json(silent=True), response.status_code

    def _request(self, method, path, json_data=None, **kwargs):
        timeout = kwargs.pop("timeout", None) or self.timeout
        return self._dispatch(
            method,
            path,
            json_data=json_data,
            timeout=timeout,
            **kwargs,
        )

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path, json_data=None, **kwargs):
        return self._request("POST", path, json_data=json_data, **kwargs)

    def put(self, path, json_data=None, **kwargs):
        return self._request("PUT", path, json_data=json_data, **kwargs)

    def delete(self, path, **kwargs):
        return self._request("DELETE", path, **kwargs)


auth_client = ServiceClient("auth")
pacientes_client = ServiceClient("pacientes")
citas_client = ServiceClient("citas")
pagos_client = ServiceClient("pagos")
notas_client = ServiceClient("notas")
audit_client = ServiceClient("audit")
