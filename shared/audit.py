# ============================================================
# Auditoria centralizada (Punto 5)
#
# FASE 2: cada servicio usa su propia base de datos; logs_auditoria
# vive en la BD del audit_service (audit_db). Esta funcion ya NO toca
# la BD directamente: delega la insercion por HTTP al audit_service
# (POST /api/auditoria), que invoca sp_insertar_log_auditoria.
#
# La firma publica se conserva (usuario_id, accion, tabla_afectada,
# registro_id, detalle, ip_origen) para no tocar los callers; aqui se
# mapea al esquema de audit_db (usuario_tipo, usuario_nombre, detalles).
#
# USO (desde cualquier servicio):
#   from shared.audit import log_accion
#   log_accion(usuario_id=session.get("usuario_id"),
#              accion="crear_cita",
#              tabla_afectada="historial_citas",
#              registro_id=cita_id,
#              detalle="Cita creada para paciente X")
#
# La escritura jamas debe romper el flujo principal del negocio:
# cualquier error (servicio caido, timeout) se ignora silenciosamente.
# ============================================================

from shared.service_client import audit_client

# Acciones conocidas por el modulo de auditoria (lista cerrada).
# Si llega una accion fuera de esta lista, se registra como
# "accion_no_reconocida" (con la accion original en detalles) en vez
# de romper o rechazar el registro.
ACCIONES_VALIDAS = [
    "crear_cita",
    "reprogramar_cita",
    "cancelar_cita",
    "completar_cita",
    "marcar_pago",
    "usar_sesion_paquete",
    "crear_usuario",
    "desactivar_usuario",
]


def _sesion_valor(clave, por_defecto=None):
    """Lee una clave de session si estamos en contexto Flask de request.
    Fuera de request_context devuelve el valor por defecto."""
    try:
        from flask import session
        return session.get(clave, por_defecto)
    except Exception:
        return por_defecto


def log_accion(usuario_id=None, accion="", tabla_afectada=None,
               registro_id=None, detalle=None, ip_origen=None,
               entidad_tipo=None, entidad_id=None, entidad_nombre=None):
    """Registra una accion en logs_auditoria (via audit_service)
    sin lanzar excepciones.

    entidad_tipo/entidad_id/entidad_nombre son opcionales y referencian
    la entidad relacionada (ej. 'paciente' con su id y nombre en
    snapshot), sin FK real por el split de bases.
    """
    try:
        partes = []
        if tabla_afectada:
            partes.append(f"tabla={tabla_afectada}")
        if registro_id is not None:
            partes.append(f"registro_id={registro_id}")
        if detalle:
            partes.append(str(detalle))

        accion_normalizada = accion if accion in ACCIONES_VALIDAS else "accion_no_reconocida"
        if accion_normalizada != accion:
            partes.append(f"accion_original={accion}")
        detalles = " | ".join(partes) or None

        payload = {
            "usuario_id": usuario_id,
            "usuario_tipo": _sesion_valor("rol", "sistema"),
            "usuario_nombre": _sesion_valor("usuario_nombre"),
            "accion": accion_normalizada,
            "detalles": detalles,
            "ip_origen": ip_origen,
            "entidad_tipo": entidad_tipo,
            "entidad_id": entidad_id,
            "entidad_nombre": entidad_nombre,
        }
        audit_client.post("/api/auditoria", payload)
    except Exception:
        # La auditoria jamas debe romper el flujo principal.
        pass