# ============================================================
# Auth para APIs internas (gateway -> servicios).
#
# Los microservicios NO deben quedar expuestos a Internet con la
# API abierta: se exige el header X-Api-Key en TODA request que
# llegue al servicio, comparado en tiempo constante contra la
# API_KEY del entorno (var compartida con el gateway).
#
#  - Si el servicio NO tiene API_KEY configurada -> se CIERRA por
#    defecto: se rechaza todo con 503. Permitir el paso cuando falta
#    la clave dejaba el servicio completamente abierto ante el primer
#    despliegue sin configurar, que es el peor escenario posible.
#    Para desarrollo local se puede desteurear con
#    ALLOW_INSECURE_INTERNAL_API=1, que queda logged como warning.
#  - Se exime el path "/" y "/health" para los health checks de
#    Render (que hacen GET al root).
#  - Se exime el webhook de pagos (/api/pagos/webhook): el proveedor
#    autentica con X-Provider-Token / X-Signature (movimientos reales
#    de pago), no con la API_KEY interna del gateway.
# ============================================================

import hmac
import os

from flask import request, jsonify

from shared.config import API_KEY

# Desteure explicito para desarrollo local. En produccion (y en Render)
# debe quedar ausente.
ALLOW_INSECURE = (os.getenv("ALLOW_INSECURE_INTERNAL_API") or "").strip() in (
    "1",
    "true",
    "yes",
)


def proteger_api_interna(app):
    """Registra un before_request que exige X-Api-Key en el servicio `app`."""

    @app.before_request
    def _verificar_api_key():
        if request.method == "OPTIONS":
            return None
        if request.path in ("/", "/health", "/api/pagos/webhook"):
            return None
        esperada = (API_KEY or "").strip()
        if not esperada:
            if ALLOW_INSECURE:
                app.logger.warning(
                    "[auth] API_KEY no configurada en %s y "
                    "ALLOW_INSECURE_INTERNAL_API activo: auth interna ABIERTA",
                    app.name,
                )
                return None
            # Falla cerrada: sin clave no hay quien pueda llamar.
            app.logger.error(
                "[auth] API_KEY no configurada en %s: auth interna CERRADA. "
                "Define API_KEY en el entorno del servicio.",
                app.name,
            )
            return (
                jsonify({"error": "Servicio sin configurar (falta API_KEY)"}),
                503,
            )
        recibida = (request.headers.get("X-Api-Key") or "").strip()
        if recibida and hmac.compare_digest(recibida, esperada):
            return None
        return jsonify({"error": "No autorizado"}), 401

    return app