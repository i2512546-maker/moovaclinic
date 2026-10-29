import re

from flask import jsonify, request

from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
from shared.audit import log_accion
from shared.proc import call_proc, call_proc_execute, call_proc_one

# Movil peruano: 9 digitos que empiezan por 9. El SMS agrega el prefijo
# +51, por eso en base solo se guardan digitos.
_RE_TELEFONO_PE = re.compile(r"^9\d{8}$")


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
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    correo = data.get("correo", "").strip()
    clave = data.get("clave", "").strip()
    telefono_crudo = data.get("telefono") or None
    rol_nombre = data.get("rol", "terapeuta").strip()

    if not nombre or not correo or not clave:
        return jsonify({"error": "Nombre, correo y clave son requeridos."}), 400

    telefono = None
    if telefono_crudo:
        telefono = re.sub(r"[\s\-()]", "", str(telefono_crudo).strip())
        if telefono.startswith("+51"):
            telefono = telefono[3:]
        if not _RE_TELEFONO_PE.fullmatch(telefono):
            return jsonify({"error": "Teléfono inválido: usa 9 dígitos que empiecen por 9."}), 400

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
    """Devuelve id/nombre/telefono de un usuario. Lo usa el modulo
    de pagos para el SMS de confirmacion al terapeuta."""
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

    # Campos que sp_actualizar_usuario sabe tocar. El telefono va por su
    # propio procedimiento (sp_actualizar_telefono_usuario) para que el
    # orden de despliegue entre codigo y migracion no lo afecte.
    campos = [k for k in ("nombre", "correo", "activo", "clave", "rol") if k in data]
    telefono_presente = "telefono" in data

    if not campos and not telefono_presente:
        return jsonify({"error": "Nada que actualizar."}), 400

    # Telefono: "" o null lo borra; si no viene en el cuerpo no se toca.
    # Fuera de eso debe ser un movil peruano (9 digitos empezando por 9).
    telefono = None
    if telefono_presente:
        crudo = data.get("telefono")
        telefono = "" if crudo is None else str(crudo).strip()
        if telefono and not _RE_TELEFONO_PE.fullmatch(telefono):
            return jsonify({
                "error": "telefono invalido: se esperan 9 digitos que empiezan por 9.",
            }), 400

    clave_hash = None
    if "clave" in data and data["clave"]:
        clave_hash = bcrypt.generate_password_hash(data["clave"]).decode("utf-8")

    rol_id = None
    if "rol" in data:
        rol_info = call_proc_one("sp_obtener_rol_id", (data["rol"],))
        if rol_info:
            rol_id = rol_info["id"]

    if campos:
        call_proc_execute("sp_actualizar_usuario", (
            usuario_id, _val("nombre"), _val("correo"), _val("activo"),
            clave_hash, rol_id,
        ))

    if telefono_presente:
        call_proc_execute("sp_actualizar_telefono_usuario", (usuario_id, telefono))

    # Auditoria: hasta esta fase este PUT no dejaba rastro alguno.
    # No se registra el valor del telefono (es dato personal del
    # terapeuta); solo si se cambio o se borro.
    detalles = f"usuario_id={usuario_id} campos={','.join(campos) or 'ninguno'}"
    if telefono_presente:
        detalles += f" telefono={'borrado' if not telefono else 'actualizado'}"
    log_accion(
        usuario_id=None,
        accion="actualizar_usuario",
        tabla_afectada="usuarios",
        registro_id=usuario_id,
        detalle=detalles,
        ip_origen=request.remote_addr,
        entidad_tipo="usuario",
        entidad_id=usuario_id,
    )
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
