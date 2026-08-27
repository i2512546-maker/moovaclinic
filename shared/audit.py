# ============================================================
# Auditoria centralizada (Punto 5)
# Como todos los servicios Flask comparten la misma BD
# (moovacloud_db) y ya importan desde `shared/`, esta funcion
# reutilizable se centraliza aqui. No hace falta un servicio
# HTTP de auditoria aparte para esta escala.
#
# USO (desde cualquier servicio):
#   from shared.audit import log_accion
#   log_accion(usuario_id=session.get("usuario_id"),
#              accion="crear_cita",
#              tabla_afectada="historial_citas",
#              registro_id=cita_id,
#              detalle="Cita creada para paciente X")
#
# La tabla logs_auditoria debe existir (ver migration_v2.sql
# PARTE 6). La FK hacia usuarios.id es ON DELETE SET NULL, asi
# que el log sobrevive aunque se borre el usuario.
# ============================================================

from shared.db import db_connection


def log_accion(usuario_id=None, accion="", tabla_afectada=None,
               registro_id=None, detalle=None, ip_origen=None):
    """Registra una accion en logs_auditoria sin lanzar excepciones.

    Si la tabla no existe o la escritura falla, el error se ignora
    para no interrumpir el flujo principal del negocio.
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO logs_auditoria
                   (usuario_id, accion, tabla_afectada, registro_id, detalle, ip_origen)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (usuario_id, accion, tabla_afectada, registro_id, detalle, ip_origen),
            )
            conn.commit()
    except Exception:
        # La auditoria jamas debe romper el flujo principal.
        pass
