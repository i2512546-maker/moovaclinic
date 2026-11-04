"""API móvil JSON de MOOVA Clinic.

La API pública móvil nunca acepta cookies de sesión. El personal usa JWT
Bearer; los pacientes usan una credencial efímera X-Verificacion tras OTP.
"""
from functools import wraps
import re
import time

import jwt
from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from shared.audit import log_accion
from shared.rate_limit import LimitadorIntentos, ip_del_request
from shared.service_client import (
    auth_client, citas_client, pacientes_client, pagos_client, notas_client,
)

movil_bp = Blueprint("movil", __name__, url_prefix="/api/movil")
_ROLES = {"admin", "terapeuta"}
_DNI = re.compile(r"^\d{8}$")
_OTP_LIMIT = LimitadorIntentos(5, 15, 15)
_LOGIN_LIMIT = LimitadorIntentos(5, 10, 30)


def _respuesta(status, codigo, mensaje, data=None):
    return jsonify({"status": status, "codigo": codigo, "mensaje": mensaje, "data": data}), status


def _ok(data=None, mensaje="Operación realizada"):
    return _respuesta(200, "OK", mensaje, data)


def _error(status, codigo, mensaje):
    return _respuesta(status, codigo, mensaje, None)


def _token_secret():
    secret = current_app.config.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET no está configurada.")
    return secret


def _verificacion_serializer():
    return URLSafeTimedSerializer(_token_secret(), salt="moova-mobile-verificacion-v1")


def _crear_jwt(usuario):
    ahora = int(time.time())
    return jwt.encode({
        "sub": str(usuario["id"]),
        "rol": str(usuario["rol"]).strip().lower(),
        "nombre": usuario.get("nombre") or "",
        "iat": ahora,
        "exp": ahora + 28800,
        "iss": "moova-clinic",
        "aud": "moova-mobile",
    }, _token_secret(), algorithm="HS256")


def _identidad():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(
                auth[7:].strip(), _token_secret(), algorithms=["HS256"],
                issuer="moova-clinic", audience="moova-mobile",
                options={"require": ["sub", "rol", "iat", "exp"]},
            )
            return {"tipo": "staff", "sub": str(payload["sub"]),
                    "rol": payload["rol"], "nombre": payload.get("nombre", "")}
        except jwt.ExpiredSignatureError:
            return None, "JWT_EXPIRADO"
        except jwt.InvalidTokenError:
            return None, "JWT_INVALIDO"
    verificacion = request.headers.get("X-Verificacion", "").strip()
    if verificacion:
        try:
            payload = _verificacion_serializer().loads(verificacion, max_age=900)
            if payload.get("accion") not in {"consultar", "agendar", "modificar", "cancelar"} or not _DNI.fullmatch(str(payload.get("dni", ""))):
                return None, "VERIFICACION_INVALIDA"
            return {"tipo": "paciente", "sub": payload["dni"], "rol": "paciente", "accion": payload["accion"]}
        except SignatureExpired:
            return None, "VERIFICACION_EXPIRADA"
        except BadSignature:
            return None, "VERIFICACION_INVALIDA"
    return None, "TOKEN_REQUERIDO"


def requiere_auth(*roles):
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            identidad = _identidad()
            if isinstance(identidad, tuple):
                codigo = identidad[1]
                status = 401
                mensaje = {
                    "JWT_EXPIRADO": "El token ha expirado.",
                    "VERIFICACION_EXPIRADA": "La verificación OTP ha expirado.",
                    "TOKEN_REQUERIDO": "Se requiere autenticación.",
                }.get(codigo, "Credencial inválida.")
                return _error(status, codigo, mensaje)
            if identidad is None:
                return _error(401, "TOKEN_REQUERIDO", "Se requiere autenticación.")
            if roles and identidad["rol"] not in roles:
                return _error(403, "ROL_NO_AUTORIZADO", "No tienes permisos para esta operación.")
            request.identidad_movil = identidad
            return func(*args, **kwargs)
        return wrapper
    return decorador


def _proxy(cliente, metodo, ruta, cuerpo=None, params=None):
    try:
        fn = getattr(cliente, metodo)
        if metodo in ("get", "delete"):
            data, status = fn(ruta, params=params) if params is not None else fn(ruta)
        else:
            data, status = fn(ruta, cuerpo or {})
    except Exception as exc:
        current_app.logger.exception("Fallo API móvil al invocar %s", ruta)
        return _error(502, "SERVICIO_NO_DISPONIBLE", "No se pudo completar la operación.")
    if status >= 400:
        return _error(status, "OPERACION_RECHAZADA", (data or {}).get("error", "La operación fue rechazada."))
    return _ok(data)


def requiere_otp(accion, validar_dni_cuerpo=False):
    """Exige un sello X-Verificacion de la acción y, al crear, del DNI del cuerpo."""
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            sello = request.headers.get("X-Verificacion", "").strip()
            if not sello:
                return _error(403, "OTP_REQUERIDO", "Debes verificar el código OTP para esta operación.")
            try:
                payload = _verificacion_serializer().loads(sello, max_age=900)
            except (BadSignature, SignatureExpired):
                return _error(403, "OTP_INVALIDO", "La verificación OTP no es válida o venció.")
            if payload.get("accion") != accion:
                return _error(403, "OTP_ACCION_INCORRECTA", "El código OTP no autoriza esta operación.")
            if validar_dni_cuerpo:
                data = request.get_json(silent=True) or {}
                if str(data.get("dni") or "").strip() != str(payload.get("dni")):
                    return _error(403, "OTP_DNI_INCORRECTO", "El OTP no corresponde al DNI enviado.")
            if "cita_id" in kwargs:
                cita_data, cita_status = citas_client.get(f"/api/citas/{kwargs['cita_id']}/basico")
                cita = (cita_data or {}).get("cita") or {}
                if cita_status != 200 or not cita.get("paciente_id"):
                    return _error(404, "CITA_NO_ENCONTRADA", "No se encontró la cita.")
                paciente_data, paciente_status = pacientes_client.get(f"/api/pacientes")
                pacientes = (paciente_data or {}).get("pacientes") or []
                paciente = next((p for p in pacientes if str(p.get("id")) == str(cita["paciente_id"])), None)
                if paciente_status != 200 or not paciente or str(paciente.get("dni")) != str(payload.get("dni")):
                    return _error(403, "OTP_DNI_INCORRECTO", "El OTP no corresponde al paciente de esta cita.")
                if request.headers.get("Authorization", "").startswith("Bearer ") and request.identidad_movil["rol"] == "terapeuta":
                    terapeuta_id = _terapeuta_id_actual()
                    if not terapeuta_id or str(cita.get("terapeuta_id")) != str(terapeuta_id):
                        return _error(403, "CITA_NO_AUTORIZADA", "Solo puedes modificar tus propias citas.")
            request.verificacion_otp = payload
            return func(*args, **kwargs)
        return wrapper
    return decorador


def _terapeuta_id_actual():
    identidad = request.identidad_movil
    if identidad["rol"] != "terapeuta":
        return None
    datos, status = pacientes_client.get("/api/terapeutas")
    if status != 200:
        return None
    for item in (datos or {}).get("terapeutas", []):
        if str(item.get("usuario_id")) == identidad["sub"]:
            return item.get("ID") or item.get("id")
    return None


def _paciente_propio(dni):
    identidad = request.identidad_movil
    return identidad["rol"] == "admin" or (
        identidad["rol"] == "paciente" and identidad["sub"] == dni
    )


@movil_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    correo = str(data.get("correo") or "").strip().lower()
    clave = str(data.get("clave") or "")
    ip = ip_del_request(request)
    claves = (f"ip:{ip}", f"correo:{correo}")
    if not correo or not clave:
        return _error(400, "DATOS_REQUERIDOS", "Correo y clave son obligatorios.")
    if _LOGIN_LIMIT.bloqueado(claves)[0]:
        return _error(429, "DEMASIADOS_INTENTOS", "Demasiados intentos. Intenta más tarde.")
    data_auth, status = auth_client.post("/api/auth/login", {"correo": correo, "clave": clave})
    usuario = (data_auth or {}).get("usuario") or {}
    rol = str(usuario.get("rol") or "").strip().lower()
    if status != 200 or not usuario or rol not in _ROLES:
        _LOGIN_LIMIT.registrar_fallo(claves)
        return _error(401, "CREDENCIALES_INVALIDAS", "Credenciales incorrectas o rol no habilitado.")
    _LOGIN_LIMIT.registrar_exito(claves)
    token = _crear_jwt(usuario)
    log_accion(usuario_id=usuario["id"], accion="login_movil", tabla_afectada="usuarios",
               registro_id=usuario["id"], detalle="Inicio de sesión móvil", ip_origen=ip)
    return _ok({"access_token": token, "token_type": "Bearer", "expires_in": 28800,
                "usuario": {"id": usuario["id"], "nombre": usuario.get("nombre"), "rol": rol}})


@movil_bp.post("/auth/otp/solicitar")
def solicitar_otp_paciente():
    data = request.get_json(silent=True) or {}
    dni = str(data.get("dni") or "").strip()
    accion = str(data.get("accion") or "consultar").strip().lower()
    if accion not in {"consultar", "agendar", "modificar", "cancelar"}:
        return _error(400, "ACCION_INVALIDA", "Acción OTP no permitida.")
    ip = ip_del_request(request)
    claves = (f"ip:{ip}", f"dni:{dni}")
    if not _DNI.fullmatch(dni):
        return _error(400, "DNI_INVALIDO", "El DNI debe contener ocho dígitos.")
    if _OTP_LIMIT.bloqueado(claves)[0]:
        return _error(429, "DEMASIADOS_INTENTOS", "Demasiadas solicitudes OTP.")
    resultado, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": accion, "telefono": data.get("telefono")})
    if status >= 400:
        _OTP_LIMIT.registrar_fallo(claves)
        return _error(status, "OTP_NO_ENVIADO", (resultado or {}).get("error", "No se pudo enviar el código."))
    _OTP_LIMIT.registrar_exito(claves)
    return _ok({"telefono_enmascarado": (resultado or {}).get("tel_mask"),
                "vigencia_minutos": 10, "accion": accion}, "Código enviado al teléfono registrado.")


@movil_bp.post("/auth/otp/verificar")
def verificar_otp_paciente():
    data = request.get_json(silent=True) or {}
    dni = str(data.get("dni") or "").strip()
    otp = str(data.get("otp") or "").strip()
    if not _DNI.fullmatch(dni) or not re.fullmatch(r"\d{6}", otp):
        return _error(400, "DATOS_INVALIDOS", "DNI y código de seis dígitos son obligatorios.")
    accion = str(data.get("accion") or "consultar").strip().lower()
    if accion not in {"consultar", "agendar", "modificar", "cancelar"}:
        return _error(400, "ACCION_INVALIDA", "Acción OTP no permitida.")
    resultado, status = citas_client.post("/api/citas/otp/verificar",
                                          {"dni": dni, "otp": otp, "accion": accion})
    if status >= 400 or (resultado or {}).get("resultado") != "ok":
        return _error(401, "OTP_INVALIDO", "El código es incorrecto, venció o no existe.")
    verificacion = _verificacion_serializer().dumps({"dni": dni, "accion": accion})
    return _ok({"tipo": "Verificacion", "verificacion": verificacion, "expires_in": 900},
               "Identidad verificada durante 15 minutos.")


@movil_bp.get("/me")
@requiere_auth()
def me():
    identidad = request.identidad_movil
    return _ok({"id": identidad["sub"], "rol": identidad["rol"],
                "nombre": identidad.get("nombre")})


# 20 operaciones de negocio expuestas con contrato JSON estable.
@movil_bp.get("/catalogo/servicios")
@requiere_auth("admin", "terapeuta", "paciente")
def servicios():
    return _proxy(pacientes_client, "get", "/api/servicios")


@movil_bp.get("/catalogo/terapeutas")
@requiere_auth("admin", "terapeuta", "paciente")
def terapeutas():
    return _proxy(pacientes_client, "get", "/api/terapeutas")


@movil_bp.get("/catalogo/terapeutas/<int:terapeuta_id>")
@requiere_auth("admin", "terapeuta", "paciente")
def terapeuta(terapeuta_id):
    return _proxy(pacientes_client, "get", f"/api/terapeutas/{terapeuta_id}")


@movil_bp.get("/citas/ocupadas")
@requiere_auth("admin", "terapeuta", "paciente")
def citas_ocupadas():
    return _proxy(citas_client, "get", "/api/citas/ocupadas", params=request.args)


@movil_bp.post("/citas/disponibilidad")
@requiere_auth("admin", "terapeuta", "paciente")
def disponibilidad():
    return _proxy(citas_client, "post", "/api/citas/disponibilidad", request.get_json(silent=True))


@movil_bp.get("/citas")
@requiere_auth("admin", "terapeuta")
def listar_citas():
    return _proxy(citas_client, "get", "/api/citas", params=request.args)


@movil_bp.get("/citas/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def detalle_cita(cita_id):
    return _proxy(citas_client, "get", f"/api/citas/{cita_id}")


@movil_bp.post("/citas")
@requiere_auth("admin", "terapeuta")
def crear_cita():
    data = request.get_json(silent=True) or {}
    if not data:
        return _error(400, "JSON_REQUERIDO", "Se requiere un objeto JSON.")
    if request.identidad_movil["rol"] == "paciente" and request.identidad_movil["sub"] != str(data.get("dni") or "").strip():
        return _error(403, "PACIENTE_NO_AUTORIZADO", "Solo puedes agendar para tu propio DNI.")
    respuesta = _proxy(citas_client, "post", "/api/citas", data)
    if isinstance(respuesta, tuple) and respuesta[1] == 200:
        log_accion(usuario_id=request.identidad_movil["sub"], accion="crear_cita",
                   tabla_afectada="historial_citas", detalle="Creación desde API móvil",
                   ip_origen=request.remote_addr)
    return respuesta


@movil_bp.put("/citas/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def modificar_cita(cita_id):
    return _proxy(citas_client, "put", f"/api/citas/{cita_id}", request.get_json(silent=True))


@movil_bp.delete("/citas/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def cancelar_cita(cita_id):
    return _proxy(citas_client, "delete", f"/api/citas/{cita_id}")


@movil_bp.get("/pacientes/<dni>")
@requiere_auth("admin", "terapeuta", "paciente")
def paciente(dni):
    if not _DNI.fullmatch(dni):
        return _error(400, "DNI_INVALIDO", "DNI inválido.")
    if not _paciente_propio(dni):
        return _error(403, "PACIENTE_NO_AUTORIZADO", "No puedes consultar otro paciente.")
    return _proxy(pacientes_client, "get", f"/api/pacientes/{dni}")


@movil_bp.get("/pacientes/<dni>/citas")
@requiere_auth("admin", "terapeuta", "paciente")
def historial_citas(dni):
    if not _paciente_propio(dni):
        return _error(403, "PACIENTE_NO_AUTORIZADO", "No puedes consultar otro paciente.")
    paciente_data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    paciente = (paciente_data or {}).get("paciente") or {}
    if status != 200 or not paciente.get("id"):
        return _error(404, "PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.")
    return _proxy(citas_client, "get", f"/api/citas/paciente/{paciente['id']}")


@movil_bp.get("/pacientes/<dni>/pagos")
@requiere_auth("admin", "terapeuta", "paciente")
def historial_pagos(dni):
    if not _paciente_propio(dni):
        return _error(403, "PACIENTE_NO_AUTORIZADO", "No puedes consultar otro paciente.")
    paciente_data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    paciente = (paciente_data or {}).get("paciente") or {}
    if status != 200 or not paciente.get("id"):
        return _error(404, "PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.")
    return _proxy(pagos_client, "get", f"/api/pagos/pacientes/{paciente['id']}")


@movil_bp.get("/pacientes/<dni>/paquetes")
@requiere_auth("admin", "terapeuta", "paciente")
def historial_paquetes(dni):
    if not _paciente_propio(dni):
        return _error(403, "PACIENTE_NO_AUTORIZADO", "No puedes consultar otro paciente.")
    paciente_data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    paciente = (paciente_data or {}).get("paciente") or {}
    if status != 200 or not paciente.get("id"):
        return _error(404, "PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.")
    return _proxy(pagos_client, "get", f"/api/pagos/pacientes/{paciente['id']}/paquetes")


@movil_bp.get("/pacientes/<dni>/evaluaciones")
@requiere_auth("admin", "terapeuta", "paciente")
def historial_evaluaciones(dni):
    if not _paciente_propio(dni):
        return _error(403, "PACIENTE_NO_AUTORIZADO", "No puedes consultar otro paciente.")
    paciente_data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    paciente = (paciente_data or {}).get("paciente") or {}
    if status != 200 or not paciente.get("id"):
        return _error(404, "PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.")
    return _proxy(pacientes_client, "get", f"/api/pacientes/{paciente['id']}/evaluaciones")


@movil_bp.post("/pacientes/<dni>/evaluaciones")
@requiere_auth("admin", "terapeuta")
def crear_evaluacion(dni):
    paciente_data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    paciente = (paciente_data or {}).get("paciente") or {}
    if status != 200 or not paciente.get("id"):
        return _error(404, "PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.")
    return _proxy(pacientes_client, "post", f"/api/pacientes/{paciente['id']}/evaluaciones",
                  request.get_json(silent=True))


@movil_bp.get("/pagos/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def estado_pago(cita_id):
    return _proxy(pagos_client, "get", f"/api/pagos/{cita_id}")


@movil_bp.post("/pagos/anticipo")
@requiere_auth("admin", "terapeuta")
def crear_anticipo():
    return _proxy(pagos_client, "post", "/api/pagos/anticipo", request.get_json(silent=True))


@movil_bp.get("/agenda")
@requiere_auth("admin", "terapeuta")
def agenda():
    return _proxy(citas_client, "get", "/api/citas/agenda", params=request.args)


@movil_bp.get("/estadisticas")
@requiere_auth("admin")
def estadisticas():
    return _proxy(citas_client, "get", "/api/citas/estadisticas")


@movil_bp.get("/notas/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def notas_cita(cita_id):
    return _proxy(notas_client, "get", f"/api/notas/{cita_id}")


@movil_bp.post("/notas/<int:cita_id>")
@requiere_auth("admin", "terapeuta")
def crear_nota(cita_id):
    return _proxy(notas_client, "post", f"/api/notas/{cita_id}", request.get_json(silent=True))
