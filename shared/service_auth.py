# ============================================================
# Auth para APIs internas (gateway -> servicios).
#
# Los microservicios NO deben quedar expuestos a Internet con la
# API abierta: se exige el header X-Api-Key en TODA request que
# llegue al servicio, comparado en tiempo constante contra la
# API_KEY del entorno (var compartida con el gateway).
#
#  - Si el servicio no tiene API_KEY configurada -> se loguea un
#    warning y se deja pasar (modo degradado para desarrollo), de
#    modo que la ausencia de configuracion nunca derribe al servicio
#    pero quede visible en los logs.
#  - Se exime el path "/" y "/health" para los health checks de
#    Render (que hacen GET al root).
# ============================================================

import hmac

from flask import request, jsonify

from shared.config import API_KEY


def proteger_api_interna(app):
    """Registra un before_request que exige X-Api-Key en el servicio `app`."""

    @app.before_request
    def _verificar_api_key():
        if request.method == "OPTIONS":
            return None
        if request.path in ("/", "/health"):
            return None
        esperada = (API_KEY or "").strip()
        if not esperada:
            app.logger.warning(
                "[auth] API_KEY no configurada en %s: auth interna DESHABILITADA",
                app.name,
            )
            return None
        recibida = (request.headers.get("X-Api-Key") or "").strip()
        if recibida and hmac.compare_digest(recibida, esperada):
            return None
        return jsonify({"error": "No autorizado"}), 401

    return app