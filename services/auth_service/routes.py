from flask import request, jsonify, session
from services.auth_service import auth_bp
from services.auth_service.app import bcrypt
from shared.config import OTP_EXPIRA_MIN, MAX_INTENTOS_IP, TIEMPO_BLOQUEO
from shared.proc import call_proc, call_proc_one, call_proc_execute
import time


def _otp_rate_limit(session_key="_otp_intentos"):
    """Control de intentos y bloqueo por IP/sesión usando session Flask."""
    ahora = time.time()
    historial = session.get(session_key, [])
    # Filtrar intentos dentro de la ventana de tiempo (OTP_EXPIRA_MIN minutos)
    ventana = max(60, OTP_EXPIRA_MIN * 60)  # mínimo 1 minuto
    historial = [t for t in historial if ahora - t < ventana]
    session[session_key] = historial

    # Verificar bloqueo activo
    if historial and historial[0] < ahora - TIEMPO_BLOQUEO * 60:
        # Bloqueo expirado, resetear
        session[session_key] = []
        return None, False

    if len(historial) >= MAX_INTENTOS_IP:
        # Bloqueo activo: primer timestamp es el inicio del bloqueo
        if not session.get("_bloqueado_hasta"):
            session["_bloqueado_hasta"] = historial[0] + TIEMPO_BLOQUEO * 60
        bloqueado_hasta = session.get("_bloqueado_hasta", 0)
        if ahora < bloqueado_hasta:
            return {"error": f"Demasiados intentos. Intenta nuevamente en {int((bloqueado_hasta - ahora) / 60)} minutos."}, True
        # Bloqueo expirado, resetear
        session[session_key] = []
        session["_bloqueado_hasta"] = None
        return None, False

    return None, False


def _registrar_intento(session_key="_otp_intentos"):
    """Registra un intento fallido y devuelve si se activó bloqueo."""
    ahora = time.time()
    historial = session.get(session_key, [])
    historial = [t for t in historial if ahora - t < (OTP_EXPIRA_MIN * 60)]
    historial.append(ahora)
    session[session_key] = historial

    if len(historial) >= MAX_INTENTOS_IP:
        session["_bloqueado_hasta"] = ahora + TIEMPO_BLOQUEO * 60
        return True  # bloqueo activado
    return False


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


@auth_bp.route("/api/auth/otp", methods=["POST"])
def otp_verificar():
    """Verificación OTP con bloqueo por intentos y IP."""
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    otp = data.get("otp", "").strip()

    if not dni or not otp:
        return jsonify({"error": "DNI y OTP requeridos."}), 400

    error, bloqueado = _otp_rate_limit()
    if bloqueado:
        return jsonify(error), 429

    # Buscar usuario por DNI
    usuario = call_proc_one("sp_obtener_usuario_por_dni", (dni,))
    if not usuario:
        return jsonify({"error": "Usuario no encontrado."}), 404

    # Verificar OTP almacenado
    otp_guardado = call_proc_one("sp_obtener_otp", (dni,))
    if not otp_guardado:
        return jsonify({"error": "OTP expirado o no disponible."}), 400

    if otp_guardado["codigo"] != otp:
        # OTP incorrecto: registrar intento y aplicar bloqueo
        bloqueo_activado = _registrar_intento()
        if bloqueo_activado:
            return jsonify({"error": "Máximo de intentos fallidos. Bloqueado por 2 minutos."}), 429
        return jsonify({"error": "OTP incorrecto."}), 400

    # OTP correcto: limpiar intentos y sesión
    session["_otp_intentos"] = []
    session["_bloqueado_hasta"] = None
    # OTP usado, puede borrarse o invalidarse en la BD
    call_proc_execute("sp_limpiar_otp", (dni,))

    return jsonify({
        "success": True,
        "usuario": {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol_nombre"],
        }
    })
