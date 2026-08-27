from flask import request, jsonify
from services.notas_service import notas_bp
from shared.db import db_connection


@notas_bp.route("/api/notas/<int:cita_id>", methods=["GET"])
def listar_notas(cita_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT nc.*, t.Nombre AS autor
               FROM notas_clinicas nc
               LEFT JOIN terapeutas t ON nc.terapeuta_id = t.ID
               WHERE nc.cita_id = %s ORDER BY nc.fecha_creacion DESC""",
            (cita_id,),
        )
        notas = cursor.fetchall()
    return jsonify({"success": True, "notas": notas})


@notas_bp.route("/api/notas/<int:cita_id>", methods=["POST"])
def crear_nota(cita_id):
    data = request.get_json() or {}
    nota = data.get("nota", "").strip()
    diagnostico = data.get("diagnostico", "").strip()
    terapeuta_id = data.get("terapeuta_id")
    paciente_id = data.get("paciente_id")

    if not nota:
        return jsonify({"error": "La nota no puede estar vacia."}), 400

    if not paciente_id:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT persona_id FROM historial_citas WHERE id=%s", (cita_id,))
            cita = cursor.fetchone()
            if cita:
                paciente_id = cita["persona_id"]

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO notas_clinicas (cita_id, paciente_id, terapeuta_id, nota, diagnostico)
               VALUES (%s, %s, %s, %s, %s)""",
            (cita_id, paciente_id, terapeuta_id, nota, diagnostico or None),
        )
        conn.commit()
        nota_id = cursor.lastrowid

    return jsonify({"success": True, "nota_id": nota_id}), 201
