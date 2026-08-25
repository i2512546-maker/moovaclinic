import os
import requests

API_TIMEOUT = 20


class PaymentNotConfigured(Exception):
    pass


class PaymentProviderError(Exception):
    pass


class NiubizClient:
    SANDBOX_URL = os.getenv("NIUBIZ_SANDBOX_URL", "https://apisandbox.vnforappstest.com")
    LIVE_URL = os.getenv("NIUBIZ_LIVE_URL", "https://api.viacel.com")

    def __init__(self):
        self.mode = (os.getenv("NIUBIZ_MODE") or "sandbox").lower()
        self.user = os.getenv("NIUBIZ_USER") or ""
        self.password = os.getenv("NIUBIZ_PASSWORD") or ""
        self.merchant_id = os.getenv("NIUBIZ_MERCHANT_ID") or ""
        self.base_url = self.LIVE_URL if self.mode == "live" else self.SANDBOX_URL
        self.sdk_url = os.getenv("NIUBIZ_SDK_URL") or (
            f"{self.base_url}/js/niubiz-sdk.js" if self.mode == "live"
            else "https://apisandbox.vnforappstest.com/js/niubiz-sdk.js"
        )

    def is_configured(self):
        return bool(self.user and self.password and self.merchant_id)

    def _require_config(self):
        if not self.is_configured():
            raise PaymentNotConfigured("Tarjeta: faltan credenciales NIUBIZ.")

    def get_token(self):
        self._require_config()
        try:
            resp = requests.post(
                f"{self.base_url}/api.security/v1/security",
                auth=(self.user, self.password),
                headers={"Content-Type": "application/json"},
                data="{}", timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Niubiz: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Niubiz: auth fallida ({resp.status_code})")
        return resp.json().get("security")

    def get_session_key(self):
        token = self.get_token()
        try:
            resp = requests.post(
                f"{self.base_url}/api.core/v1/security/cards/session",
                headers={"Authorization": token, "Content-Type": "application/json"},
                data="{}", timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Niubiz: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Niubiz: sesion fallida ({resp.status_code})")
        data = resp.json()
        return {"sessionKey": data.get("sessionKey"), "merchantId": self.merchant_id}

    def cobrar(self, card_token, cvv, purchase_number, monto):
        self._require_config()
        token = self.get_token()
        body = {
            "channel": "web", "captureType": "auth", "countable": True,
            "order": {"tokenId": card_token, "purchaseNumber": str(purchase_number),
                      "amount": int(round(monto * 100)), "currency": "PEN"},
            "card": {"token": card_token, "expiration": "9999", "security": cvv, "name": ""},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api.authorization/v3/authorization",
                headers={"Authorization": token, "Content-Type": "application/json"},
                json=body, timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Niubiz: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Niubiz: cobro fallido ({resp.status_code})")
        data = resp.json() or {}
        action = (data.get("dataMap") or {}).get("ACTION_CODE", "")
        tx_id = (data.get("dataMap") or {}).get("TRANSACTION_ID", "")
        if action != "000":
            raise PaymentProviderError(f"Niubiz: rechazada (codigo {action})")
        return {"transaccion_id": tx_id, "monto": monto, "datos_respuesta": data}


class YapeClient:
    def __init__(self):
        self.base_url = (os.getenv("YAPE_API_URL") or "").rstrip("/")
        self.client_id = os.getenv("YAPE_CLIENT_ID") or ""
        self.client_secret = os.getenv("YAPE_CLIENT_SECRET") or ""
        self.merchant_id = os.getenv("YAPE_MERCHANT_ID") or ""

    def is_configured(self):
        return bool(self.base_url and self.client_id and self.client_secret and self.merchant_id)

    def _require_config(self):
        if not self.is_configured():
            raise PaymentNotConfigured("Yape: faltan credenciales.")

    def _token(self):
        self._require_config()
        try:
            resp = requests.post(
                f"{self.base_url}/oauth/token",
                data={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
                timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Yape: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Yape: auth fallida ({resp.status_code})")
        return resp.json().get("access_token")

    def crear_cobro(self, monto, concepto, referencia):
        token = self._token()
        body = {"monto": round(float(monto), 2), "moneda": "PEN", "concepto": concepto,
                "referencia": referencia, "negocio": self.merchant_id}
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/cobros",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body, timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Yape: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Yape: cobro fallido ({resp.status_code})")
        data = resp.json() or {}
        cobro_id = data.get("id") or data.get("cobro_id")
        qr_b64 = data.get("qr") or data.get("qr_base64")
        if not cobro_id or not qr_b64:
            raise PaymentProviderError("Yape: respuesta sin QR.")
        return {"cobro_id": str(cobro_id), "qr_base64": qr_b64}

    def consultar_pago(self, cobro_id):
        token = self._token()
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/cobros/{cobro_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Yape: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Yape: consulta fallida ({resp.status_code})")
        data = resp.json() or {}
        estado = (data.get("estado") or data.get("status") or "").lower()
        return {"pagado": estado in ("pagado", "paid", "confirmed"), "datos_respuesta": data}


class PlinClient:
    def __init__(self):
        self.base_url = (os.getenv("PLIN_API_URL") or "").rstrip("/")
        self.client_id = os.getenv("PLIN_CLIENT_ID") or ""
        self.client_secret = os.getenv("PLIN_CLIENT_SECRET") or ""
        self.merchant_id = os.getenv("PLIN_MERCHANT_ID") or ""

    def is_configured(self):
        return bool(self.base_url and self.client_id and self.client_secret and self.merchant_id)

    def _require_config(self):
        if not self.is_configured():
            raise PaymentNotConfigured("Plin: faltan credenciales.")

    def _token(self):
        self._require_config()
        try:
            resp = requests.post(
                f"{self.base_url}/oauth/token",
                data={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
                timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Plin: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Plin: auth fallida ({resp.status_code})")
        return resp.json().get("access_token")

    def crear_cobro(self, monto, concepto, referencia):
        token = self._token()
        body = {"monto": round(float(monto), 2), "moneda": "PEN", "concepto": concepto,
                "referencia": referencia, "negocio": self.merchant_id}
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/cobros",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body, timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Plin: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Plin: cobro fallido ({resp.status_code})")
        data = resp.json() or {}
        cobro_id = data.get("id") or data.get("cobro_id")
        qr_b64 = data.get("qr") or data.get("qr_base64")
        if not cobro_id or not qr_b64:
            raise PaymentProviderError("Plin: respuesta sin QR.")
        return {"cobro_id": str(cobro_id), "qr_base64": qr_b64}

    def consultar_pago(self, cobro_id):
        token = self._token()
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/cobros/{cobro_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=API_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PaymentProviderError(f"Plin: sin conexion ({e})")
        if resp.status_code not in (200, 201):
            raise PaymentProviderError(f"Plin: consulta fallida ({resp.status_code})")
        data = resp.json() or {}
        estado = (data.get("estado") or data.get("status") or "").lower()
        return {"pagado": estado in ("pagado", "paid", "confirmed"), "datos_respuesta": data}


def qr_url(data_b64):
    if not data_b64:
        return ""
    if data_b64.startswith("data:"):
        return data_b64
    return f"data:image/png;base64,{data_b64}"
