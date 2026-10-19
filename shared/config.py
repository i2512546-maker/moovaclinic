import os

from dotenv import find_dotenv, load_dotenv

# Carga primero el .env del directorio de trabajo del proceso (el de cada
# servicio al arrancar desde su propia carpeta); si no existe, cae al .env
# de la raiz del repo como respaldo.
load_dotenv(find_dotenv(usecwd=True))

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", 3306))
NOTAS_DB_NAME = os.getenv("NOTAS_DB_NAME", "moovacloud_notas")
KPIS_DB_NAME = os.getenv("KPIS_DB_NAME", "moovacloud_kpis")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "Falta la variable de entorno SECRET_KEY. Déjala en .env y vuelve a arrancar."
    )
API_KEY = os.getenv("API_KEY")

TEXTBEE_API_KEY = os.getenv("TEXTBEE_API_KEY")
TEXTBEE_DEVICE_ID = os.getenv("TEXTBEE_DEVICE_ID")
TEXTBEE_URL = os.getenv("TEXTBEE_URL")

APIPERU_TOKEN = os.getenv("APIPERU_TOKEN")
APIPERU_URL = os.getenv("APIPERU_URL")

OTP_EXPIRA_MIN = int(os.getenv("OTP_EXPIRA_MIN", 10))
OTP_MAX_INTENTOS = int(os.getenv("OTP_MAX_INTENTOS", 3))

# Recordatorios automaticos por SMS (citas_service + APScheduler).
# Deshabilitados por defecto: el envio se activa por entorno y
# jamas se enciende solo en una instalacion nueva.
RECORDATORIOS_ENABLED = os.getenv("RECORDATORIOS_ENABLED", "0").strip()
# Hora (America/Lima) a partir de la cual el job tiene permitido
# enviar los SMS del dia siguiente. Evita mandar mensajes a las 7am.
RECORDATORIO_HORA = os.getenv("RECORDATORIO_HORA", "18:00").strip()
# Cada cuantos minutos corre el job que revisa el pendiente.
RECORDATORIO_INTERVALO_MIN = int(os.getenv("RECORDATORIO_INTERVALO_MIN", 15))

# Reporte de pacientes en riesgo de fuga (citas_service).
# Dias desde la ultima cita a partir de los cuales un paciente sin
# cita programada pasa a considerarse "en riesgo".
RIESGO_DIAS_UMBRAL = int(os.getenv("RIESGO_DIAS_UMBRAL", 30))

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

# Token que el proveedor de pagos envia en cada webhook (X-Provider-Token /
# X-Signature). Si queda vacio el webhook NO exige firma: solo queda protegido
# por la exencion del filtro de API_KEY interna.
WEBHOOK_PROVIDER_TOKEN = os.getenv("WEBHOOK_PROVIDER_TOKEN") or ""

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
    "audit": os.getenv("AUDIT_SERVICE_URL", "http://127.0.0.1:5006"),
}
