# ============================================================
# Helper central para invocar procedimientos almacenados.
# Reemplaza el uso directo de cursor.execute("SELECT ...") en las
# rutas: el backend Python ya NO conoce nombres de tablas ni de
# columnas; toda la logica SQL vive en los PROCEDURE de
# procedures.sql.
#
# Convenciones:
#  - Los procedimientos SELECCIONAN su resultado (filas a leer) o
#    terminan con un SELECT de control (ej: LAST_INSERT_ID(),
#    ROW_COUNT()) para que aqui se lea con stored_results().
#  - Se evitan los parametros OUT de MySQL para simplificar y ser
#    compatible con mysql-connector-python 8.0.33.
# ============================================================

from shared.db import db_connection


def _run(proc_name, params, dictionary, fetch, commit, drain=False):
    params = list(params or ())
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        cursor.callproc(proc_name, params)
        rows = []
        if fetch:
            try:
                for result in cursor.stored_results():
                    rows.extend(result.fetchall())
            except Exception:
                # Procedimientos que no devuelven result set
                rows = []
        elif drain:
            try:
                for result in cursor.stored_results():
                    result.fetchall()
            except Exception:
                pass
        if commit:
            conn.commit()
    return rows


def call_proc(proc_name, params=(), dictionary=True, fetch=True, commit=True):
    """Ejecuta un procedimiento y devuelve la primera (y unica)
    serie de filas resultantes como lista de dict/listas."""
    return _run(proc_name, params, dictionary, fetch, commit)


def call_proc_one(proc_name, params=(), dictionary=True):
    """Ejecuta y devuelve la primera fila del resultado (o None)."""
    rows = _run(proc_name, params, dictionary, fetch=True, commit=True)
    return rows[0] if rows else None


def call_proc_execute(proc_name, params=()):
    """Ejecuta un procedimiento de DML (INSERT/UPDATE/DELETE) que
    no necesita devolver filas. Consume (y descarta) cualquier result
    set que el procedimiento haya dejado para evitar "Unread result
    found" en mysql-connector cuando el SP termina con un SELECT de
    control (ej: LAST_INSERT_ID(), ROW_COUNT()). Igual commit."""
    return _run(proc_name, params, dictionary=False, fetch=False, commit=True, drain=True)


def call_proc_results(proc_name, params=()):
    """Ejecuta un procedimiento que devuelve VARIOS result sets
    (ej: sp_obtener_ficha_clinica_completa) y retorna una lista de
    listas de dicts, una por cada SELECT, en orden. Igual commit."""
    params = list(params or ())
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc(proc_name, params)
        results = []
        try:
            for result in cursor.stored_results():
                results.append(result.fetchall())
        except Exception:
            results = []
        conn.commit()
    return results
