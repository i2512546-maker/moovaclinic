from datetime import datetime, timedelta
from flask import request, jsonify, session
from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
from shared.config import OTP_EXPIRA_MIN, OTP_MAX_INTENTOS
from shared.proc import call_proc, call_proc_one, call_proc_execute


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    correo = data.get("correo", "").strip()
    clave = data.get("clave", "").strip()

    if not correo or not clave:
        return jsonify({"error": "Completa todos los campos."}), 400

    usuario = call_proc_one("sp_login", (correo,))

    if not usuario or not bcrypt.check_password_hash(usuario["clave"], clave):
        return jsonify({"error": "Correo o contrasena incorrectos."}), 401

    call_proc_execute("sp_actualizar_ultimo_acceso", (usuario["id"],))

    return jsonify({
        "success": True,
        "usuario": {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "correo": usuario["correo"],
            "rol": usuario["rol_nombre"],
        },
    })


@auth_bp.route("/api/auth/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = call_proc("sp_listar_usuarios")
    return jsonify({"success": True, "usuarios": usuarios})


@auth_bp.route("/api/auth/usuarios", methods=["POST"])
def crear_usuario():
    from flask import session as flask_session
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    correo = data.get("correo", "").strip()
    clave = data.get("clave", "").strip()
    rol_nombre = data.get("rol", "terapeuta").strip()

    if not nombre or not correo or not clave:
        return jsonify({"error": "Nombre, correo y clave son requeridos."}), 400

    clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")

    rol = call_proc_one("sp_obtener_rol_id", (rol_nombre,))
    if not rol:
        return jsonify({"error": f"Rol '{rol_nombre}' no existe."}), 400

    if call_proc_one("sp_obtener_usuario_por_correo", (correo,)):
        return jsonify({"error": "Ya existe un usuario con ese correo."}), 409

    result = call_proc_one("sp_crear_usuario", (nombre, correo, clave_hash, rol["id"]))
    usuario_id = result["id"] if result else None
    return jsonify({"success": True, "usuario_id": usuario_id}), 201


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
