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
                      (SELECT COUNT(*) FROM historial_citas WHERE persona_id = p.id) AS total_citas,
                      (SELECT MAX(fecha_cita) FROM historial_citas WHERE persona_id = p.id) AS ultima_cita
               FROM personas p ORDER BY p.apellido ASC"""
        )
        pacientes = cursor.fetchall()
    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>", methods=["GET"])
def detalle_paciente(paciente_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM personas WHERE id = %s", (paciente_id,))
        paciente = cursor.fetchone()
        if not paciente:
            return jsonify({"error": "Paciente no encontrado"}), 404

        cursor.execute(
            """SELECT h.*, t.Nombre AS terapeuta, t.Especialidad,
                      pg.monto, pg.metodo_pago, pg.estado_pago
               FROM historial_citas h
               JOIN terapeutas t ON h.terapeuta_id = t.ID
               LEFT JOIN pagos pg ON pg.cita_id = h.id
               WHERE h.persona_id = %s ORDER BY h.fecha_cita DESC""",
            (paciente_id,),
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
        cursor.execute("SELECT id FROM personas WHERE dni = %s", (dni,))
        existente = cursor.fetchone()
        if existente:
            return jsonify({"error": "Ya existe un paciente con ese DNI.", "paciente_id": existente["id"]}), 409

        cursor.execute(
            "INSERT INTO personas (nombre, apellido, dni, telefono, email) VALUES (%s,%s,%s,%s,%s)",
            (nombre, apellido, dni, telefono, data.get("email")),
        )
        conn.commit()
        paciente_id = cursor.lastrowid

    return jsonify({"success": True, "paciente_id": paciente_id}), 201


@pacientes_bp.route("/api/pacientes/<int:paciente_id>", methods=["PUT"])
def actualizar_paciente(paciente_id):
    data = request.get_json() or {}
    with db_connection() as conn:
        cursor = conn.cursor()
        updates, params = [], []
        for campo in ["nombre", "apellido", "dni", "telefono", "email", "estado"]:
            if campo in data:
                updates.append(f"{campo} = %s")
                params.append(data[campo])
        if not updates:
            return jsonify({"error": "Nada que actualizar."}), 400
        params.append(paciente_id)
        cursor.execute(f"UPDATE personas SET {', '.join(updates)} WHERE id = %s", params)
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
