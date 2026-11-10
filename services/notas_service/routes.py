import threading
import time

from flask import jsonify, request

from services.notas_service import notas_bp
from shared.config import NOTAS_DB_NAME
from shared.proc import call_proc, call_proc_one
from shared.service_client import (
    citas_client,
    pacientes_client,
)


_TERAPEUTAS_CACHE_TTL = 30.0
_TERAPEUTAS_CACHE = {"expires": 0.0, "data": None}
_TERAPEUTAS_CACHE_LOCK = threading.Lock()


def _mapa_terapeutas():
    """Catálogo breve en caché: evita repetir auth/pacientes por cada nota."""
    ahora = time.monotonic()
    with _TERAPEUTAS_CACHE_LOCK:
        if ahora < _TERAPEUTAS_CACHE["expires"] and _TERAPEUTAS_CACHE["data"] is not None:
            return _TERAPEUTAS_CACHE["data"]

    try:
        data, status = pacientes_client.get("/api/terapeutas")
        if status != 200 or not isinstance(data, dict):
            return {}
        terapeutas = data.get("terapeutas") or []
        mapa = {t["ID"]: t for t in terapeutas}
    except Exception:
        return {}

    if mapa:
        with _TERAPEUTAS_CACHE_LOCK:
            _TERAPEUTAS_CACHE["data"] = mapa
            _TERAPEUTAS_CACHE["expires"] = time.monotonic() + _TERAPEUTAS_CACHE_TTL
    return mapa


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
        # Obtener el paciente_id mediante una llamada interna al modulo
        # de citas. Se usa el endpoint liviano /basico (solo datos locales
        # de moovacloud_citas), que evita consultas adicionales a pacientes.
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
    ), db_name=NOTAS_DB_NAME, commit=True)
    nota_id = result["id"] if result else None
    return jsonify({"success": True, "nota_id": nota_id}), 201
