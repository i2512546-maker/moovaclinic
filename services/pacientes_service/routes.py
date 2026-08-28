import requests
from flask import request, jsonify
from services.pacientes_service import pacientes_bp
from shared.config import APIPERU_TOKEN, APIPERU_URL
from shared.proc import call_proc, call_proc_one, call_proc_execute


@pacientes_bp.route("/api/pacientes", methods=["GET"])
def listar_pacientes():
    pacientes = call_proc("sp_listar_pacientes")
    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/<dni>", methods=["GET"])
def detalle_paciente(dni):
    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404

    historial = call_proc("sp_obtener_historial_paciente", (paciente["id"],))
    return jsonify({"success": True, "paciente": paciente, "historial": historial})


@pacientes_bp.route("/api/pacientes", methods=["POST"])
def crear_paciente():
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    apellido = data.get("apellido", "").strip()
    dni = data.get("dni", "").strip()
    telefono = data.get("telefono", "").strip()

    if not all([nombre, apellido, dni, telefono]):
        return jsonify({"error": "Todos los campos son requeridos."}), 400

    existente = call_proc_one("sp_existe_paciente_por_dni", (dni,))
    if existente:
        return jsonify({"error": "Ya existe un paciente con ese DNI.", "dni": existente["dni"]}), 409

    call_proc_execute("sp_crear_paciente", (
        nombre, apellido, dni, telefono,
        data.get("email"),
        data.get("fecha_nacimiento") or None,
        data.get("sexo") or None,
        data.get("direccion"),
        data.get("seguro"),
    ))
    return jsonify({"success": True, "dni": dni}), 201


@pacientes_bp.route("/api/pacientes/<dni>", methods=["PUT"])
def actualizar_paciente(dni):
    data = request.get_json() or {}

    def _val(key):
        return None if key not in data else data[key]

    if not any(k in data for k in [
        "nombre", "apellido", "telefono", "email", "estado",
        "fecha_nacimiento", "sexo", "direccion", "seguro", "dni",
    ]):
        return jsonify({"error": "Nada que actualizar."}), 400

    dni_nuevo = data["dni"] if ("dni" in data and data["dni"] != dni) else None
    result = call_proc("sp_actualizar_paciente", (
        dni,
        _val("nombre"), _val("apellido"), _val("telefono"), _val("email"),
        _val("estado"), _val("fecha_nacimiento"), _val("sexo"),
        _val("direccion"), _val("seguro"), dni_nuevo,
    ))
    return jsonify({"success": True})


@pacientes_bp.route("/api/pacientes/buscar_dni", methods=["POST"])
def buscar_dni():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    if len(dni) != 8 or not dni.isdigit():
        return jsonify({"success": False, "error": "DNI invalido"}), 400

    try:
        url = APIPERU_URL.format(dni=dni, token=APIPERU_TOKEN)
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=5)
        if resp.status_code == 200:
            api_data = resp.json()
            if api_data.get("success"):
                return jsonify({"success": True, "data": api_data})
    except Exception:
        pass

    return jsonify({"success": False, "error": "DNI no encontrado"}), 404


# ============================================================
# Servicios (catalogo)
# ============================================================

@pacientes_bp.route("/api/servicios", methods=["GET"])
def listar_servicios():
    servicios = call_proc("sp_listar_servicios")
    return jsonify({"success": True, "servicios": servicios})


# ============================================================
# Paquetes de sesiones
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes(paciente_id):
    paquetes = call_proc("sp_listar_paquetes", (paciente_id,))
    return jsonify({"success": True, "paquetes": paquetes})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["POST"])
def crear_paquete(paciente_id):
    data = request.get_json() or {}
    servicio_id = data.get("servicio_id")
    total_sesiones = data.get("total_sesiones")
    fecha_compra = data.get("fecha_compra")
    fecha_vencimiento = data.get("fecha_vencimiento")

    if not servicio_id or not total_sesiones or not fecha_compra:
        return jsonify({"error": "servicio_id, total_sesiones y fecha_compra son requeridos."}), 400

    result = call_proc_one("sp_crear_paquete", (
        paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento,
    ))
    paquete_id = result["id"] if result else None
    return jsonify({"success": True, "paquete_id": paquete_id}), 201


# ============================================================
# Evaluaciones iniciales
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["GET"])
def listar_evaluaciones(paciente_id):
    evaluaciones = call_proc("sp_listar_evaluaciones", (paciente_id,))
    return jsonify({"success": True, "evaluaciones": evaluaciones})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["POST"])
def crear_evaluacion(paciente_id):
    data = request.get_json() or {}
    terapeuta_id = data.get("terapeuta_id")
    motivo_consulta = data.get("motivo_consulta", "").strip()

    if not terapeuta_id or not motivo_consulta:
        return jsonify({"error": "terapeuta_id y motivo_consulta son requeridos."}), 400

    result = call_proc_one("sp_crear_evaluacion", (
        paciente_id, terapeuta_id, motivo_consulta,
        data.get("escala_dolor_eva"),
        data.get("rango_movimiento"),
        data.get("objetivos_terapeuticos"),
    ))
    eval_id = result["id"] if result else None
    return jsonify({"success": True, "evaluacion_id": eval_id}), 201


# ============================================================
# Consentimientos
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["GET"])
def listar_consentimientos(paciente_id):
    consentimientos = call_proc("sp_listar_consentimientos", (paciente_id,))
    return jsonify({"success": True, "consentimientos": consentimientos})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["POST"])
def crear_consentimiento(paciente_id):
    data = request.get_json() or {}
    tipo = data.get("tipo", "").strip()
    texto_version = data.get("texto_version", "").strip()

    if not tipo or not texto_version:
        return jsonify({"error": "tipo y texto_version son requeridos."}), 400

    result = call_proc_one("sp_crear_consentimiento", (
        paciente_id, tipo, texto_version, data.get("ip_origen"),
    ))
    consent_id = result["id"] if result else None
    return jsonify({"success": True, "consentimiento_id": consent_id}), 201
