import requests
from flask import request, jsonify
from services.pacientes_service import pacientes_bp
from shared.db import db_connection
from shared.config import APIPERU_TOKEN, APIPERU_URL


@pacientes_bp.route("/api/pacientes", methods=["GET"])
def listar_pacientes():
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM historial_citas WHERE paciente_id = p.id) AS total_citas,
                      (SELECT MAX(fecha_cita) FROM historial_citas WHERE paciente_id = p.id) AS ultima_cita
               FROM pacientes p ORDER BY p.apellido ASC"""
        )
        pacientes = cursor.fetchall()
    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/<dni>", methods=["GET"])
def detalle_paciente(dni):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pacientes WHERE dni = %s", (dni,))
        paciente = cursor.fetchone()
        if not paciente:
            return jsonify({"error": "Paciente no encontrado"}), 404

        cursor.execute(
            """SELECT h.*, u.nombre AS terapeuta, e.nombre AS Especialidad,
                      pg.monto, pg.metodo_pago, pg.estado_pago
               FROM historial_citas h
               JOIN terapeutas t ON h.terapeuta_id = t.id
               JOIN usuarios u ON t.usuario_id = u.id
               LEFT JOIN especialidades e ON t.especialidad_id = e.id
               LEFT JOIN pagos pg ON pg.cita_id = h.id
               WHERE h.paciente_id = %s ORDER BY h.fecha_cita DESC""",
            (paciente["id"],),
        )
        historial = cursor.fetchall()

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

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT dni FROM pacientes WHERE dni = %s", (dni,))
        existente = cursor.fetchone()
        if existente:
            return jsonify({"error": "Ya existe un paciente con ese DNI.", "dni": existente["dni"]}), 409

        cursor.execute(
            """INSERT INTO pacientes
               (nombre, apellido, dni, telefono, email, fecha_nacimiento, sexo, direccion, seguro)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                nombre, apellido, dni, telefono,
                data.get("email"),
                data.get("fecha_nacimiento") or None,
                data.get("sexo") or None,
                data.get("direccion"),
                data.get("seguro"),
            ),
        )
        conn.commit()

    return jsonify({"success": True, "dni": dni}), 201


@pacientes_bp.route("/api/pacientes/<dni>", methods=["PUT"])
def actualizar_paciente(dni):
    data = request.get_json() or {}
    with db_connection() as conn:
        cursor = conn.cursor()
        updates, params = [], []
        for campo in [
            "nombre", "apellido", "telefono", "email", "estado",
            "fecha_nacimiento", "sexo", "direccion", "seguro",
        ]:
            if campo in data:
                updates.append(f"{campo} = %s")
                params.append(data[campo])
        if "dni" in data and data["dni"] != dni:
            updates.append("dni = %s")
            params.append(data["dni"])
        if not updates:
            return jsonify({"error": "Nada que actualizar."}), 400
        params.append(dni)
        cursor.execute(f"UPDATE pacientes SET {', '.join(updates)} WHERE dni = %s", params)
        conn.commit()
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
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM servicios WHERE activo = 1 ORDER BY nombre")
        servicios = cursor.fetchall()
    return jsonify({"success": True, "servicios": servicios})


# ============================================================
# Paquetes de sesiones
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes(paciente_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT ps.*, s.nombre AS servicio_nombre, s.duracion_min
               FROM paquetes_sesiones ps
               JOIN servicios s ON ps.servicio_id = s.id
               WHERE ps.paciente_id = %s ORDER BY ps.fecha_compra DESC""",
            (paciente_id,),
        )
        paquetes = cursor.fetchall()
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

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO paquetes_sesiones
               (paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento)
               VALUES (%s, %s, %s, %s, %s)""",
            (paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento),
        )
        conn.commit()
        paquete_id = cursor.lastrowid

    return jsonify({"success": True, "paquete_id": paquete_id}), 201


# ============================================================
# Evaluaciones iniciales
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["GET"])
def listar_evaluaciones(paciente_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT ei.*, u.nombre AS terapeuta_nombre
               FROM evaluaciones_iniciales ei
               JOIN terapeutas t ON ei.terapeuta_id = t.id
               JOIN usuarios u ON t.usuario_id = u.id
               WHERE ei.paciente_id = %s ORDER BY ei.fecha_creacion DESC""",
            (paciente_id,),
        )
        evaluaciones = cursor.fetchall()
    return jsonify({"success": True, "evaluaciones": evaluaciones})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["POST"])
def crear_evaluacion(paciente_id):
    data = request.get_json() or {}
    terapeuta_id = data.get("terapeuta_id")
    motivo_consulta = data.get("motivo_consulta", "").strip()

    if not terapeuta_id or not motivo_consulta:
        return jsonify({"error": "terapeuta_id y motivo_consulta son requeridos."}), 400

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO evaluaciones_iniciales
               (paciente_id, terapeuta_id, motivo_consulta, escala_dolor_eva,
                rango_movimiento, objetivos_terapeuticos)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                paciente_id, terapeuta_id, motivo_consulta,
                data.get("escala_dolor_eva"),
                data.get("rango_movimiento"),
                data.get("objetivos_terapeuticos"),
            ),
        )
        conn.commit()
        eval_id = cursor.lastrowid

    return jsonify({"success": True, "evaluacion_id": eval_id}), 201


# ============================================================
# Consentimientos
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["GET"])
def listar_consentimientos(paciente_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM consentimientos WHERE paciente_id = %s ORDER BY aceptado_en DESC",
            (paciente_id,),
        )
        consentimientos = cursor.fetchall()
    return jsonify({"success": True, "consentimientos": consentimientos})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["POST"])
def crear_consentimiento(paciente_id):
    data = request.get_json() or {}
    tipo = data.get("tipo", "").strip()
    texto_version = data.get("texto_version", "").strip()

    if not tipo or not texto_version:
        return jsonify({"error": "tipo y texto_version son requeridos."}), 400

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO consentimientos
               (paciente_id, tipo, texto_version, ip_origen)
               VALUES (%s, %s, %s, %s)""",
            (paciente_id, tipo, texto_version, data.get("ip_origen")),
        )
        conn.commit()
        consent_id = cursor.lastrowid

    return jsonify({"success": True, "consentimiento_id": consent_id}), 201
