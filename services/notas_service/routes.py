from flask import request, jsonify
from services.notas_service import notas_bp
from shared.proc import call_proc, call_proc_one, call_proc_execute
from shared.service_client import citas_client, pacientes_client
from shared.config import NOTAS_DB_NAME


def _mapa_terapeutas():
    """{terapeuta_id: {Nombre, ...}} via pacientes_service para
    enriquecer el autor de las notas (antes JOIN a usuarios via
    terapeutas en sp_listar_notas, CROSS-DB)."""
    try:
        data, _ = pacientes_client.get("/api/terapeutas")
        terapeutas = data.get("terapeutas") or []
        return {t["ID"]: t for t in terapeutas}
    except Exception:
        return {}


@notas_bp.route("/api/notas/<int:cita_id>", methods=["GET"])
def listar_notas(cita_id):
    notas = call_proc("sp_listar_notas", (cita_id,), db_name=NOTAS_DB_NAME) or []
    mapa = _mapa_terapeutas()
    for n in notas:
        te = mapa.get(n.get("terapeuta_id")) or {}
        if te.get("Nombre") is not None:
            n["autor"] = te["Nombre"]
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
        # FASE 2: paciente_id de la cita via citas_service. Se usa el
        # endpoint liviano /basico (solo datos locales de citas_db) en
        # vez del detalle enriquecido, que dispara llamadas HTTP a
        # pacientes_service y supera el timeout de ServiceClient.
        try:
            cita_data, status = citas_client.get(f"/api/citas/{cita_id}/basico")
            cita = (cita_data or {}).get("cita") or {} if status == 200 else {}
            paciente_id = cita.get("paciente_id")
        except Exception:
            paciente_id = None

    if not paciente_id:
        return jsonify({"error": "No se pudo determinar el paciente de la cita."}), 400

    result = call_proc_one("sp_crear_nota", (
        cita_id, paciente_id, terapeuta_id, nota, diagnostico or None,
    ), db_name=NOTAS_DB_NAME)
    nota_id = result["id"] if result else None
    return jsonify({"success": True, "nota_id": nota_id}), 201