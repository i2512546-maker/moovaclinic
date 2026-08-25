import os
import requests
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", 3306))

SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32).hex())
API_KEY = os.getenv("API_KEY")

TEXTBEE_API_KEY = os.getenv("TEXTBEE_API_KEY")
TEXTBEE_DEVICE_ID = os.getenv("TEXTBEE_DEVICE_ID")
TEXTBEE_URL = os.getenv("TEXTBEE_URL")

APIPERU_TOKEN = os.getenv("APIPERU_TOKEN")
APIPERU_URL = os.getenv("APIPERU_URL")

OTP_EXPIRA_MIN = int(os.getenv("OTP_EXPIRA_MIN", 10))
OTP_MAX_INTENTOS = int(os.getenv("OTP_MAX_INTENTOS", 3))

MAX_INTENTOS_IP = int(os.getenv("MAX_INTENTOS_IP", 3))
TIEMPO_BLOQUEO = int(os.getenv("TIEMPO_BLOQUEO", 2))

NIUBIZ_SANDBOX_URL = os.getenv("NIUBIZ_SANDBOX_URL", "https://apisandbox.vnforappstest.com")
NIUBIZ_LIVE_URL = os.getenv("NIUBIZ_LIVE_URL", "https://api.viacel.com")
NIUBIZ_MODE = (os.getenv("NIUBIZ_MODE") or "sandbox").lower()
NIUBIZ_USER = os.getenv("NIUBIZ_USER") or ""
NIUBIZ_PASSWORD = os.getenv("NIUBIZ_PASSWORD") or ""
NIUBIZ_MERCHANT_ID = os.getenv("NIUBIZ_MERCHANT_ID") or ""
NIUBIZ_SDK_URL = os.getenv("NIUBIZ_SDK_URL") or ""

YAPE_API_URL = os.getenv("YAPE_API_URL") or ""
YAPE_CLIENT_ID = os.getenv("YAPE_CLIENT_ID") or ""
YAPE_CLIENT_SECRET = os.getenv("YAPE_CLIENT_SECRET") or ""
YAPE_MERCHANT_ID = os.getenv("YAPE_MERCHANT_ID") or ""

PLIN_API_URL = os.getenv("PLIN_API_URL") or ""
PLIN_CLIENT_ID = os.getenv("PLIN_CLIENT_ID") or ""
PLIN_CLIENT_SECRET = os.getenv("PLIN_CLIENT_SECRET") or ""
PLIN_MERCHANT_ID = os.getenv("PLIN_MERCHANT_ID") or ""

REDES_SOCIALES = {
    "facebook": "https://www.facebook.com/people/Moova-Clinic/61575855088670/#",
    "instagram": "https://www.instagram.com/moovaclinic/",
    "twitter": "https://twitter.com/",
    "youtube": "https://www.youtube.com/",
    "whatsapp": "https://wa.me/",
    "tiktok": "https://www.tiktok.com/@moova.clinic",
}

SERVICE_URLS = {
    "auth": os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:5001"),
    "pacientes": os.getenv("PACIENTES_SERVICE_URL", "http://127.0.0.1:5002"),
    "citas": os.getenv("CITAS_SERVICE_URL", "http://127.0.0.1:5003"),
    "pagos": os.getenv("PAGOS_SERVICE_URL", "http://127.0.0.1:5004"),
    "notas": os.getenv("NOTAS_SERVICE_URL", "http://127.0.0.1:5005"),
}
