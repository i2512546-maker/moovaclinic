from flask import request, jsonify
from services.audit_service import audit_bp
from shared.proc import call_proc_execute


@audit_bp.route("/api/auditoria", methods=["POST"])
def registrar_auditoria():
    """Registra una accion en logs_auditoria (audit_db).

    Recibe el esquema de audit_db; la composicion de las claves
    antiguas de shared/audit.py (tabla_afectada/registro_id/detalle)
    la hace el propio log_accion antes de llamar por HTTP.
    """
    data = request.get_json() or {}

    usuario_id = data.get("usuario_id")
    usuario_tipo = data.get("usuario_tipo") or "sistema"
    usuario_nombre = data.get("usuario_nombre")
    accion = data.get("accion", "").strip()
    detalles = data.get("detalles")
    ip_origen = data.get("ip_origen")

    if not accion:
        return jsonify({"error": "accion requerida"}), 400

    call_proc_execute("sp_insertar_log_auditoria", (
        usuario_id, usuario_tipo, usuario_nombre, accion, detalles, ip_origen,
    ))
    return jsonify({"success": True}), 201