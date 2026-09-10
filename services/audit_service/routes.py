import re
from flask import request, jsonify
from services.audit_service import audit_bp
from shared.proc import call_proc, call_proc_execute

_FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?")


def _fecha_param(key):
    """Normaliza un query param de fecha (YYYY-MM-DD o con hora).
    Devuelve None si falta o no tiene formato valido."""
    valor = (request.args.get(key) or "").strip()
    return valor if valor and _FECHA_RE.match(valor) else None


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
    accion = (data.get("accion") or "").strip()
    detalles = data.get("detalles")
    ip_origen = data.get("ip_origen")

    entidad_tipo = (data.get("entidad_tipo") or "").strip() or None
    if entidad_tipo not in ("paciente", "medico"):
        entidad_tipo = None
    entidad_id = data.get("entidad_id")
    try:
        entidad_id = int(entidad_id) if entidad_id not in (None, "") else None
    except (TypeError, ValueError):
        entidad_id = None
    entidad_nombre = (data.get("entidad_nombre") or "").strip() or None

    if not accion:
        return jsonify({"error": "accion requerida"}), 400

    call_proc_execute("sp_insertar_log_auditoria", (
        usuario_id, usuario_tipo, usuario_nombre, accion, detalles, ip_origen,
        entidad_tipo, entidad_id, entidad_nombre,
    ))
    return jsonify({"success": True}), 201


@audit_bp.route("/api/auditoria", methods=["GET"])
def listar_auditoria():
    """Lista los logs de auditoria (solo lectura, sin paginacion).

    Filtros opcionales por query string: usuario_id (exacto), usuario_tipo,
    accion (texto parcial), fecha_desde, fecha_hasta y entidad_tipo.
    Ordena por fecha descendente y limita a los ultimos 200 registros
    (sp_listar_auditoria).
    """
    usuario_id_raw = (request.args.get("usuario_id") or "").strip() or None
    try:
        usuario_id = int(usuario_id_raw) if usuario_id_raw else None
    except (TypeError, ValueError):
        usuario_id = None
    usuario_tipo = (request.args.get("usuario_tipo") or "").strip() or None
    accion = (request.args.get("accion") or "").strip() or None
    fecha_desde = _fecha_param("fecha_desde")
    fecha_hasta = _fecha_param("fecha_hasta")
    entidad_tipo = (request.args.get("entidad_tipo") or "").strip() or None
    if entidad_tipo not in ("paciente", "medico"):
        entidad_tipo = None

    try:
        logs = call_proc("sp_listar_auditoria", (
            usuario_id, usuario_tipo, accion, fecha_desde, fecha_hasta, entidad_tipo,
        )) or []
    except Exception:
        logs = []

    return jsonify({"success": True, "logs": logs})