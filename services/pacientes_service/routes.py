import requests
from flask import request, jsonify, current_app
from services.pacientes_service import pacientes_bp
from shared.config import APIPERU_TOKEN, APIPERU_URL
from shared.proc import call_proc, call_proc_one, call_proc_execute
from shared.service_client import auth_client, citas_client, pagos_client


def _mapa_usuarios():
    """{usuario_id: {nombre, correo, rol, activo}} via auth_service."""
    try:
        data, _ = auth_client.get("/api/auth/usuarios")
        usuarios = data.get("usuarios") or []
        return {u["id"]: u for u in usuarios}
    except Exception:
        return {}


def _mapa_especialidades():
    especialidades = call_proc("sp_listar_especialidades") or []
    return {e["id"]: e["nombre"] for e in especialidades}


def _mapa_terapeutas(usuarios=None, especialidades=None):
    """{terapeuta_id: {te_name: Nombre, Especialidad}} para enriquecer
    citas/historial sin tocar tablas de otras bases."""
    usuarios = usuarios if usuarios is not None else _mapa_usuarios()
    especialidades = especialidades if especialidades is not None else _mapa_especialidades()
    terapeutas = call_proc("sp_listar_terapeutas") or []
    mapa = {}
    for t in terapeutas:
        u = usuarios.get(t.get("usuario_id"))
        mapa[t["ID"]] = {
            "terapeuta_nombre": (u or {}).get("nombre"),
            "especialidad": especialidades.get(t.get("especialidad_id")),
            "precio": float(t["precio"]) if t.get("precio") is not None else None,
        }
    return mapa


# ============================================================
# Pacientes
# ============================================================

@pacientes_bp.route("/api/pacientes", methods=["GET"])
def listar_pacientes():
    pacientes = call_proc("sp_listar_pacientes")

    resumen = {}
    try:
        data, _ = citas_client.get("/api/citas/resumen_pacientes")
        resumen = {r["paciente_id"]: r for r in (data.get("resumen") or [])}
    except Exception:
        pass

    for p in pacientes:
        info = resumen.get(p["id"]) or {}
        p["total_citas"] = info.get("total", 0)
        p["ultima_cita"] = info.get("ultima")

    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/dni/<dni>", methods=["GET"])
def obtener_paciente_id_por_dni(dni):
    """Resuelve el id de un paciente segun dni. Usado por
    citas_service/pagos_service (antes era un JOIN CROSS-DB)."""
    paciente = call_proc_one("sp_obtener_paciente_id_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404
    return jsonify({"success": True, "id": paciente["id"]})


def _validar_datos_paciente(nombre, apellido, dni, telefono):
    """Valida formato estricto ANTES de tocar la DB. Devuelve None si OK,
    o el mensaje de error. Solo letras/espacios en nombre/apellido."""
    import re
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,60}", nombre):
        return "Nombre inválido"
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,60}", apellido):
        return "Apellido inválido"
    if not re.fullmatch(r"\d{8}", dni):
        return "DNI inválido, debe tener 8 dígitos"
    tel = re.sub(r"[\s\-]", "", telefono or "")
    if tel.startswith("+51"):
        tel = tel[3:]
    if not re.fullmatch(r"\d{9}", tel):
        return "Teléfono inválido, debe tener 9 dígitos"
    return None


@pacientes_bp.route("/api/pacientes/min", methods=["POST"])
def crear_paciente_min():
    """Crea un paciente con datos minimos. Usado por citas_service
    cuando la reserva trae un dni que no existe aun."""
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    apellido = data.get("apellido", "").strip()
    dni = data.get("dni", "").strip()
    telefono = data.get("telefono", "").strip()

    if not all([nombre, apellido, dni, telefono]):
        return jsonify({"error": "Todos los campos son requeridos."}), 400

    error = _validar_datos_paciente(nombre, apellido, dni, telefono)
    if error:
        return jsonify({"error": error}), 400

    try:
        existente = call_proc_one("sp_existe_paciente_por_dni", (dni,))
        if existente:
            return jsonify({"error": "Ya existe un paciente con ese DNI.", "dni": existente["dni"]}), 409

        result = call_proc_one("sp_crear_paciente_min", (nombre, apellido, dni, telefono))
    except Exception as exc:
        current_app.logger.error(
            "[crear_paciente_min] Error en BD (sp_crear_paciente_min): %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    return jsonify({"success": True, "id": result["id"] if result else None}), 201


@pacientes_bp.route("/api/pacientes/<dni>", methods=["GET"])
def detalle_paciente(dni):
    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404

    paciente_id = paciente["id"]

    historial = []
    try:
        citas_data, _ = citas_client.get(f"/api/citas/paciente/{paciente_id}")
        historial = citas_data.get("citas") or []
    except Exception:
        pass

    pagos = {}
    try:
        pagos_data, _ = pagos_client.get(f"/api/pagos/pacientes/{paciente_id}")
        for pg in (pagos_data.get("pagos") or []):
            if pg.get("cita_id") not in pagos:
                pagos[pg["cita_id"]] = pg
    except Exception:
        pass

    mapa = _mapa_terapeutas()
    for c in historial:
        te = mapa.get(c.get("terapeuta_id")) or {}
        c["terapeuta"] = te.get("terapeuta_nombre")
        c["Especialidad"] = te.get("especialidad")
        pg = pagos.get(c.get("id"))
        if pg:
            c["monto"] = float(pg.get("monto") or 0)
            c["metodo_pago"] = pg.get("metodo_pago")
            c["estado_pago"] = pg.get("estado_pago")

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
    call_proc("sp_actualizar_paciente", (
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
    except Exception as exc:
        current_app.logger.error(
            "[buscar_dni] Error consultando APIPERU (dni=%s): %s: %s",
            dni, type(exc).__name__, exc,
        )

    return jsonify({"success": False, "error": "DNI no encontrado"}), 404


# ============================================================
# Servicios (catalogo)
# ============================================================

@pacientes_bp.route("/api/servicios", methods=["GET"])
def listar_servicios():
    servicios = call_proc("sp_listar_servicios")
    return jsonify({"success": True, "servicios": servicios})


# ============================================================
# Terapeutas (antes consumidos por el gateway via CROSS-DB)
# ============================================================

@pacientes_bp.route("/api/terapeutas", methods=["GET"])
def listar_terapeutas():
    terapeutas = call_proc("sp_listar_terapeutas") or []
    usuarios = _mapa_usuarios()
    especialidades = _mapa_especialidades()

    for t in terapeutas:
        u = usuarios.get(t.get("usuario_id")) or {}
        t["Nombre"] = u.get("nombre")
        t["Telefono"] = u.get("telefono")
        t["Especialidad"] = especialidades.get(t.get("especialidad_id"))
        t["precio"] = float(t["precio"]) if t.get("precio") is not None else None

    return jsonify({"success": True, "terapeutas": terapeutas})


@pacientes_bp.route("/api/terapeutas/<int:medico_id>", methods=["GET"])
def obtener_terapeuta(medico_id):
    terapeuta = call_proc_one("sp_obtener_terapeuta", (medico_id,))
    if not terapeuta:
        return jsonify({"error": "Terapeuta no encontrado"}), 404

    usuarios = _mapa_usuarios()
    especialidades = _mapa_especialidades()
    u = usuarios.get(terapeuta.get("usuario_id")) or {}
    terapeuta["Nombre"] = u.get("nombre")
    terapeuta["Especialidad"] = especialidades.get(terapeuta.get("especialidad_id"))
    terapeuta["precio"] = float(terapeuta["precio"]) if terapeuta.get("precio") is not None else None

    return jsonify({"success": True, "terapeuta": terapeuta})


@pacientes_bp.route("/api/terapeutas", methods=["POST"])
def crear_terapeuta():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    especialidad_id = data.get("especialidad_id")
    precio = data.get("precio")

    if not usuario_id:
        return jsonify({"error": "usuario_id requerido."}), 400

    result = call_proc_one("sp_crear_terapeuta", (usuario_id, especialidad_id, precio))
    return jsonify({"success": True, "id": result["id"] if result else None}), 201


@pacientes_bp.route("/api/terapeutas/<int:medico_id>/precio", methods=["PUT"])
def actualizar_precio_terapeuta(medico_id):
    data = request.get_json() or {}
    precio = data.get("precio")
    if precio is None:
        return jsonify({"error": "precio requerido."}), 400
    call_proc_execute("sp_actualizar_precio", (medico_id, precio))
    return jsonify({"success": True})


@pacientes_bp.route("/api/terapeutas/<int:medico_id>/activo", methods=["PUT"])
def set_terapeuta_activo(medico_id):
    data = request.get_json() or {}
    activo = data.get("activo")
    if activo is None:
        return jsonify({"error": "activo requerido."}), 400
    call_proc_execute("sp_set_terapeuta_activo", (medico_id, 1 if activo else 0))
    return jsonify({"success": True})


# ============================================================
# Especialidades
# ============================================================

@pacientes_bp.route("/api/especialidades", methods=["GET"])
def listar_especialidades():
    especialidades = call_proc("sp_listar_especialidades")
    return jsonify({"success": True, "especialidades": especialidades})


@pacientes_bp.route("/api/especialidades/por-nombre/<path:nombre>", methods=["GET"])
def obtener_especialidad_id(nombre):
    if not nombre:
        return jsonify({"error": "nombre requerido"}), 400
    esp = call_proc_one("sp_obtener_especialidad_id", (nombre,))
    if not esp:
        return jsonify({"error": "Especialidad no encontrada."}), 404
    return jsonify({"success": True, "id": esp["id"]})


# ============================================================
# Estadisticas
# ============================================================

@pacientes_bp.route("/api/estadisticas/especialistas", methods=["GET"])
def estadisticas_especialistas():
    data = call_proc_one("sp_estadisticas_especialistas") or {}
    return jsonify({"success": True, "total": data.get("total", 0)})


@pacientes_bp.route("/api/estadisticas/opiniones", methods=["GET"])
def estadisticas_opiniones():
    data = call_proc_one("sp_estadisticas_opiniones") or {}
    return jsonify({"success": True, "total": data.get("total", 0), "buenas": data.get("buenas", 0)})


# ============================================================
# Paquetes de sesiones (delegados a pagos_service)
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes(paciente_id):
    data, status = pagos_client.get(f"/api/pagos/pacientes/{paciente_id}/paquetes")
    return jsonify(data), status


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["POST"])
def crear_paquete(paciente_id):
    payload = request.get_json() or {}
    data, status = pagos_client.post(f"/api/pagos/pacientes/{paciente_id}/paquetes", payload)
    return jsonify(data), status


# ============================================================
# Evaluaciones iniciales
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["GET"])
def listar_evaluaciones(paciente_id):
    evaluaciones = call_proc("sp_listar_evaluaciones", (paciente_id,)) or []
    mapa = _mapa_terapeutas()
    for e in evaluaciones:
        e["terapeuta_nombre"] = (mapa.get(e.get("terapeuta_id")) or {}).get("terapeuta_nombre")
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