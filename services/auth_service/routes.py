import json
from datetime import datetime, timedelta
from flask import request, jsonify, session
from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
from shared.db import db_connection
from shared.config import OTP_EXPIRA_MIN, OTP_MAX_INTENTOS


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    correo = data.get("correo", "").strip()
    clave = data.get("clave", "").strip()

    if not correo or not clave:
        return jsonify({"error": "Completa todos los campos."}), 400

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT u.*, r.nombre AS rol_nombre
               FROM usuarios u
               JOIN roles r ON u.rol_id = r.id
               WHERE u.correo = %s AND u.activo = 1""",
            (correo,),
        )
        usuario = cursor.fetchone()

    if not usuario or not bcrypt.check_password_hash(usuario["clave"], clave):
        return jsonify({"error": "Correo o contrasena incorrectos."}), 401

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (usuario["id"],))
        conn.commit()

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
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.ultimo_acceso
               FROM usuarios u JOIN roles r ON u.rol_id = r.id
               ORDER BY r.nombre, u.nombre"""
        )
        usuarios = cursor.fetchall()
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

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM roles WHERE nombre = %s", (rol_nombre,))
        rol = cursor.fetchone()
        if not rol:
            return jsonify({"error": f"Rol '{rol_nombre}' no existe."}), 400

        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify({"error": "Ya existe un usuario con ese correo."}), 409

        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, clave, rol_id) VALUES (%s,%s,%s,%s)",
            (nombre, correo, clave_hash, rol["id"]),
        )
        conn.commit()
        usuario_id = cursor.lastrowid

    return jsonify({"success": True, "usuario_id": usuario_id}), 201


@auth_bp.route("/api/auth/usuarios/<int:usuario_id>", methods=["PUT"])
def actualizar_usuario(usuario_id):
    data = request.get_json() or {}
    with db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        for campo in ["nombre", "correo", "activo"]:
            if campo in data:
                updates.append(f"{campo} = %s")
                params.append(data[campo])
        if "clave" in data and data["clave"]:
            clave_hash = bcrypt.generate_password_hash(data["clave"]).decode("utf-8")
            updates.append("clave = %s")
            params.append(clave_hash)
        if "rol" in data:
            cursor.execute("SELECT id FROM roles WHERE nombre = %s", (data["rol"],))
            rol = cursor.fetchone()
            if rol:
                updates.append("rol_id = %s")
                params.append(rol[0])
        if not updates:
            return jsonify({"error": "Nada que actualizar."}), 400
        params.append(usuario_id)
        cursor.execute(f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    return jsonify({"success": True})


@auth_bp.route("/api/auth/roles", methods=["GET"])
def listar_roles():
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM roles WHERE activo = 1 ORDER BY nombre")
        roles = cursor.fetchall()
    return jsonify({"success": True, "roles": roles})


@auth_bp.route("/api/auth/verificar", methods=["POST"])
def verificar_token():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    rol_requerido = data.get("rol")

    if not usuario_id:
        return jsonify({"error": "usuario_id requerido"}), 400

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT u.id, u.nombre, u.rol_id, r.nombre AS rol
               FROM usuarios u JOIN roles r ON u.rol_id = r.id
               WHERE u.id = %s AND u.activo = 1""",
            (usuario_id,),
        )
        usuario = cursor.fetchone()

    if not usuario:
        return jsonify({"autenticado": False}), 401

    if rol_requerido and usuario["rol"] != rol_requerido and usuario["rol"] != "admin":
        return jsonify({"autenticado": False, "error": "Rol insuficiente"}), 403

    return jsonify({"autenticado": True, "usuario": {
        "id": usuario["id"], "nombre": usuario["nombre"], "rol": usuario["rol"]
    }})
