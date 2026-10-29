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
AUTH_DB_NAME = os.getenv("AUTH_DB_NAME", "moovacloud_auth")
PACIENTES_DB_NAME = os.getenv("PACIENTES_DB_NAME", "moovacloud_pacientes")
CITAS_DB_NAME = os.getenv("CITAS_DB_NAME", "moovacloud_citas")
PAGOS_DB_NAME = os.getenv("PAGOS_DB_NAME", "moovacloud_pagos")
AUDIT_DB_NAME = os.getenv("AUDIT_DB_NAME", "moovacloud_auditoria")
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
APIPERU_URL = os.getenv("APIPERU_URL", "https://dniruc.apisperu.com/api/v1/dni/{dni}?token={token}")

OTP_EXPIRA_MIN = int(os.getenv("OTP_EXPIRA_MIN", 10))
OTP_MAX_INTENTOS = int(os.getenv("OTP_MAX_INTENTOS", 3))
# Minutos que el gateway considera vigente una verificacion OTP en la
# sesion del navegador (S1). Sirve para ver los datos de una cita y
# para cancelarla/modificarla sin volver a pedir el codigo. No es el
# tiempo de vida del codigo en si, que sigue siendo OTP_EXPIRA_MIN.
OTP_SESION_MIN = int(os.getenv("OTP_SESION_MIN", 15))

# Limite de intentos de login en el gateway (S2). No hay captcha ni
# dependencias de terceros: el gateway corta el intento ANTES de llamar
# a auth_service.
LOGIN_MAX_INTENTOS = int(os.getenv("LOGIN_MAX_INTENTOS", 5))
# Ventana (minutos) en la que se acumulan los fallos.
LOGIN_VENTANA_MIN = int(os.getenv("LOGIN_VENTANA_MIN", 10))
# Minutos que dura el bloqueo una vez superado el maximo.
LOGIN_BLOQUEO_MIN = int(os.getenv("LOGIN_BLOQUEO_MIN", 30))
# 1 = detras de un proxy (Render/ nginx): la IP real se toma del
# PRIMER valor de X-Forwarded-For. En 0 (default) el header se ignora,
# porque cualquiera podria inventarlo y quedar sin contador.
TRUST_PROXY = os.getenv("TRUST_PROXY", "0").strip().lower() in ("1", "true", "yes")

# Recordatorios automaticos por SMS (modulo de citas + APScheduler).
# Deshabilitados por defecto: el envio se activa por entorno y
# jamas se enciende solo en una instalacion nueva.
RECORDATORIOS_ENABLED = os.getenv("RECORDATORIOS_ENABLED", "0").strip()
# Hora (America/Lima) a partir de la cual el job tiene permitido
# enviar los SMS del dia siguiente. Evita mandar mensajes a las 7am.
RECORDATORIO_HORA = os.getenv("RECORDATORIO_HORA", "18:00").strip()
# Cada cuantos minutos corre el job que revisa el pendiente.
RECORDATORIO_INTERVALO_MIN = int(os.getenv("RECORDATORIO_INTERVALO_MIN", 15))

# Liberación automática de citas cuyos pagos vencieron. Se ejecuta en
# el scheduler del gateway, también cuando los recordatorios están apagados.
LIBERAR_VENCIDOS_ENABLED = (
    os.getenv("LIBERAR_VENCIDOS_ENABLED", "1").strip().lower()
    in ("1", "true", "yes", "on")
)

# Reporte de pacientes en riesgo de fuga (modulo de citas).
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

# 1 = habilita confirmacion simulada de pagos solo para sustentacion/pruebas.
# Debe estar activado tanto en gateway como en el servicio de pagos.
PAGOS_MODO_DEMO = os.getenv("PAGOS_MODO_DEMO", "0").strip().lower() in ("1", "true", "yes", "on")


REDES_SOCIALES = {
    "facebook": "https://www.facebook.com/people/Moova-Clinic/61575855088670/#",
    "instagram": "https://www.instagram.com/moovaclinic/",
    "twitter": "https://twitter.com/",
    "youtube": "https://www.youtube.com/",
    "whatsapp": "https://wa.me/",
    "tiktok": "https://www.tiktok.com/@moova.clinic",
}
