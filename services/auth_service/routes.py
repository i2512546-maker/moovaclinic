<<<<<<< Updated upstream
from flask import jsonify, request

from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
=======
from datetime import datetime, timedelta
import jwt
from flask import g, jsonify, request

from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
from shared.api import error, ok, token_required
from shared.audit import log_accion
from shared.config import JWT_ALGORITHM, JWT_TTL_SECONDS, SECRET_KEY
>>>>>>> Stashed changes
from shared.proc import call_proc, call_proc_execute, call_proc_one


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    correo = str(data.get("email", "") or "").strip()
    clave = str(data.get("password", "") or "").strip()

    if not correo:
        return jsonify(error("4010", "El campo email es requerido", 400, detalle=[{"campo": "email", "codigo": "4010", "mensaje": "El campo email es requerido"}])[0]), 400
    if len(correo) > 100:
        return jsonify(error("4010", "El campo email excede el máximo permitido", 400, detalle=[{"campo": "email", "codigo": "4010", "mensaje": "El campo email excede el máximo permitido"}])[0]), 400
    if not clave:
        return jsonify(error("4010", "El campo password es requerido", 400, detalle=[{"campo": "password", "codigo": "4010", "mensaje": "El campo password es requerido"}])[0]), 400
    if len(clave) > 100:
        return jsonify(error("4010", "El campo password excede el máximo permitido", 400, detalle=[{"campo": "password", "codigo": "4010", "mensaje": "El campo password excede el máximo permitido"}])[0]), 400

    usuario_existente = call_proc_one("sp_obtener_usuario_por_correo", (correo,))
    usuario = call_proc_one("sp_login", (correo,))

    if usuario_existente and not usuario:
        log_accion(
            usuario_id=usuario_existente.get("id"),
            accion="login_fallido",
            tabla_afectada="usuarios",
            registro_id=usuario_existente.get("id"),
            detalle=f"Intento de login para cuenta inactiva: {correo}",
            ip_origen=request.remote_addr,
        )
        return jsonify(error("4021", "Cuenta inactiva", 401, detalle=[{"campo": "email", "codigo": "4021", "mensaje": "Cuenta inactiva"}])[0]), 401

    if not usuario or not bcrypt.check_password_hash(usuario["clave"], clave):
        log_accion(
            usuario_id=(usuario_existente or {}).get("id"),
            accion="login_fallido",
            tabla_afectada="usuarios",
            registro_id=(usuario_existente or {}).get("id"),
            detalle=f"Intento de login fallido para {correo}",
            ip_origen=request.remote_addr,
        )
        return jsonify(error("4020", "Credenciales incorrectas", 401, detalle=[{"campo": "password", "codigo": "4020", "mensaje": "Credenciales incorrectas"}])[0]), 401

    payload = {
        "user_id": usuario["id"],
        "role": usuario["rol_nombre"],
        "nombre": usuario["nombre"],
        "email": usuario["correo"],
        "exp": datetime.utcnow() + timedelta(seconds=JWT_TTL_SECONDS),
    }
    access_token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

    call_proc_execute("sp_actualizar_ultimo_acceso", (usuario["id"],))
    log_accion(
        usuario_id=usuario["id"],
        accion="login_exitoso",
        tabla_afectada="usuarios",
        registro_id=usuario["id"],
        detalle=f"Login exitoso para {usuario['correo']}",
        ip_origen=request.remote_addr,
    )

    response = ok(
        "Login exitoso",
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": JWT_TTL_SECONDS,
            "rol": usuario["rol_nombre"],
            "nombre": usuario["nombre"],
            "user_id": usuario["id"],
        },
    )
    return jsonify(response), 200


@auth_bp.route("/api/auth/protected", methods=["GET"])
@token_required(roles=["admin", "terapeuta"])
def protected_demo():
    return jsonify(ok("Acceso autorizado", {"user": {"id": g.user_id, "role": g.user_role}})), 200


@auth_bp.route("/api/auth/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = call_proc("sp_listar_usuarios")
    return jsonify({"success": True, "usuarios": usuarios})


@auth_bp.route("/api/auth/usuarios", methods=["POST"])
def crear_usuario():
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    correo = data.get("correo", "").strip()
    clave = data.get("clave", "").strip()
    telefono = data.get("telefono") or None
    rol_nombre = data.get("rol", "terapeuta").strip()

    if not nombre or not correo or not clave:
        return jsonify({"error": "Nombre, correo y clave son requeridos."}), 400

    clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")

    rol = call_proc_one("sp_obtener_rol_id", (rol_nombre,))
    if not rol:
        return jsonify({"error": f"Rol '{rol_nombre}' no existe."}), 400

    if call_proc_one("sp_obtener_usuario_por_correo", (correo,)):
        return jsonify({"error": "Ya existe un usuario con ese correo."}), 409

    if telefono:
        # Usuario de panel admin (terapeuta) con telefono.
        result = call_proc_one("sp_crear_usuario_admin", (
            nombre, correo, telefono, clave_hash, rol["id"],
        ))
    else:
        result = call_proc_one("sp_crear_usuario", (nombre, correo, clave_hash, rol["id"]))
    usuario_id = result["id"] if result else None
    return jsonify({"success": True, "usuario_id": usuario_id}), 201


@auth_bp.route("/api/auth/usuarios/por-nombre/<path:nombre>", methods=["GET"])
def obtener_usuario_por_nombre(nombre):
    """Devuelve el usuario cuyo nombre coincide. Usado por
    pacientes_service/gateway para resolver el usuario_id de un
    terapeuta recien creado desde el panel admin."""
    if not nombre:
        return jsonify({"error": "nombre requerido"}), 400
    usuario = call_proc_one("sp_obtener_usuario_por_nombre", (nombre,))
    if not usuario:
        return jsonify({"error": "Usuario no encontrado."}), 404
    return jsonify({"success": True, "id": usuario["id"]})


@auth_bp.route("/api/auth/usuarios/<int:usuario_id>", methods=["GET"])
def obtener_usuario_por_id(usuario_id):
    """Devuelve id/nombre/telefono de un usuario. Lo usa
    pagos_service para el SMS de confirmacion al terapeuta."""
    usuario = call_proc_one("sp_obtener_usuario_por_id", (usuario_id,))
    if not usuario:
        return jsonify({"error": "Usuario no encontrado."}), 404
    return jsonify({"success": True, "usuario": {
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "telefono": usuario.get("telefono"),
    }})


@auth_bp.route("/api/auth/usuarios/<int:usuario_id>", methods=["PUT"])
def actualizar_usuario(usuario_id):
    data = request.get_json() or {}

    def _val(key):
        return None if key not in data else data[key]

    if not any(k in data for k in ["nombre", "correo", "activo", "clave", "rol"]):
        return jsonify({"error": "Nada que actualizar."}), 400

    clave_hash = None
    if "clave" in data and data["clave"]:
        clave_hash = bcrypt.generate_password_hash(data["clave"]).decode("utf-8")

    rol_id = None
    if "rol" in data:
        rol_info = call_proc_one("sp_obtener_rol_id", (data["rol"],))
        if rol_info:
            rol_id = rol_info["id"]

    call_proc_execute("sp_actualizar_usuario", (
        usuario_id, _val("nombre"), _val("correo"), _val("activo"),
        clave_hash, rol_id,
    ))
    return jsonify({"success": True})


@auth_bp.route("/api/auth/roles", methods=["GET"])
def listar_roles():
    roles = call_proc("sp_listar_roles")
    return jsonify({"success": True, "roles": roles})


@auth_bp.route("/api/auth/verificar", methods=["POST"])
def verificar_token():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    rol_requerido = data.get("rol")

    if not usuario_id:
        return jsonify({"error": "usuario_id requerido"}), 400

    usuario = call_proc_one("sp_verificar_usuario", (usuario_id,))
    if not usuario:
        return jsonify({"autenticado": False}), 401

    if rol_requerido and usuario["rol"] != rol_requerido and usuario["rol"] != "admin":
        return jsonify({"autenticado": False, "error": "Rol insuficiente"}), 403

    return jsonify({"autenticado": True, "usuario": {
        "id": usuario["id"], "nombre": usuario["nombre"], "rol": usuario["rol"]
    }})
