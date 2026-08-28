from flask import request, jsonify
from services.notas_service import notas_bp
from shared.proc import call_proc, call_proc_one, call_proc_execute


@notas_bp.route("/api/notas/<int:cita_id>", methods=["GET"])
def listar_notas(cita_id):
    notas = call_proc("sp_listar_notas", (cita_id,))
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
        cita = call_proc_one("sp_obtener_paciente_id_cita", (cita_id,))
        if cita:
            paciente_id = cita["paciente_id"]

    result = call_proc_one("sp_crear_nota", (
        cita_id, paciente_id, terapeuta_id, nota, diagnostico or None,
    ))
    nota_id = result["id"] if result else None
    return jsonify({"success": True, "nota_id": nota_id}), 201
