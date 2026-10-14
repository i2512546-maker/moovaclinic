from functools import wraps
from typing import Iterable, Optional

import jwt
from flask import Flask, g, jsonify, request
from jwt import ExpiredSignatureError, InvalidTokenError
from werkzeug.exceptions import HTTPException

from shared.config import JWT_ALGORITHM, JWT_TTL_SECONDS, SECRET_KEY


def ok(mensaje, data=None):
    return {
        "status": True,
        "codigo": "0000",
        "mensaje": mensaje,
        "data": data if data is not None else {},
    }


def error(codigo, mensaje, http, detalle=None):
    payload = {
        "status": False,
        "error": {
            "codigo": codigo,
            "mensaje": mensaje,
            "detalle": detalle or [],
        },
    }
    return payload, http


def _token_error_response(codigo, mensaje, http=401, detalle=None):
    return jsonify(error(codigo, mensaje, http, detalle=detalle)[0]), http


def _invalid_field_detail(campo, codigo, mensaje):
    return [{"campo": campo, "codigo": codigo, "mensaje": mensaje}]


def token_required(roles=None):
    allowed_roles = {"admin", "terapeuta"} if roles is None else set(roles)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header or not auth_header.lower().startswith("bearer "):
                return _token_error_response("4003", "Token no encontrado", 401)

            token = auth_header.split(" ", 1)[1].strip() if " " in auth_header else ""
            if not token:
                return _token_error_response("4003", "Token no encontrado", 401)

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "user_id", "role"]})
            except ExpiredSignatureError:
                return _token_error_response("4001", "Token expirado", 401)
            except InvalidTokenError:
                return _token_error_response("4002", "Token inválido", 401)
            except Exception:
                return _token_error_response("4002", "Token inválido", 401)

            user_id = payload.get("user_id")
            user_role = payload.get("role")
            if not user_id or not user_role:
                return _token_error_response("4002", "Token inválido", 401)

            if user_role not in allowed_roles:
                return _token_error_response("4030", "Sin permisos para el rol", 403)

            g.user = payload
            g.user_id = user_id
            g.user_role = user_role
            return func(*args, **kwargs)

        return wrapper

    return decorator


def register_global_error_handlers(app: Flask):
    @app.errorhandler(400)
    def handle_bad_request(error):
        detail = _invalid_field_detail("request", "4010", "Solicitud inválida")
        return jsonify(error("4010", "Solicitud inválida", 400, detail=detail)[0]), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify(error("4040", "Registro no existe", 404, detail=[{"campo": "ruta", "codigo": "4040", "mensaje": "Registro no existe"}])[0]), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify(error("4050", "Método no permitido", 405, detail=[{"campo": "metodo", "codigo": "4050", "mensaje": "Método no permitido"}])[0]), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify(error("5000", "Error interno del servidor", 500, detail=[{"campo": "general", "codigo": "5000", "mensaje": "Error interno del servidor"}])[0]), 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        if error.code == 404:
            return handle_not_found(error)
        if error.code == 405:
            return handle_method_not_allowed(error)
        if error.code == 400:
            return handle_bad_request(error)
        return jsonify(error("5000", "Error interno del servidor", 500, detail=[{"campo": "general", "codigo": "5000", "mensaje": "Error interno del servidor"}])[0]), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        return jsonify(error("5000", "Error interno del servidor", 500, detail=[{"campo": "general", "codigo": "5000", "mensaje": "Error interno del servidor"}])[0]), 500

    return app
