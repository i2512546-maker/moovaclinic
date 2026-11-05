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

import logging
import time

from shared.db import db_connection


def _run(proc_name, params, dictionary, fetch, commit, drain=False, db_name=None):
    params = list(params or ())
    started = time.perf_counter()
    with db_connection(db_name=db_name) as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            cursor.callproc(proc_name, params)
            rows = []
            if fetch:
                try:
                    for result in cursor.stored_results():
                        try:
                            rows.extend(result.fetchall())
                        finally:
                            result.close()
                except Exception:
                    # Procedimientos que no devuelven result set.
                    rows = []
            elif drain:
                try:
                    for result in cursor.stored_results():
                        try:
                            result.fetchall()
                        finally:
                            result.close()
                except Exception:
                    # Muchos procedimientos DML no dejan result set.
                    pass
            if commit:
                conn.commit()
        finally:
            cursor.close()
    elapsed = time.perf_counter() - started
    if elapsed >= 1.0:
        logging.getLogger("moova.db").warning(
            "Procedimiento %s tardó %.3f s", proc_name, elapsed
        )
    return rows


def call_proc(proc_name, params=(), dictionary=True, fetch=True, commit=False, db_name=None):
    """Ejecuta un procedimiento y devuelve la primera (y unica)
    serie de filas resultantes como lista de dict/listas."""
    return _run(proc_name, params, dictionary, fetch, commit, db_name=db_name)


def call_proc_one(proc_name, params=(), dictionary=True, db_name=None, commit=False):
    """Ejecuta una consulta y devuelve la primera fila (o None).

    Las lecturas no necesitan COMMIT; las llamadas que modifican datos
    deben indicar commit=True explícitamente.
    """
    rows = _run(proc_name, params, dictionary, fetch=True, commit=commit, db_name=db_name)
    return rows[0] if rows else None


def call_proc_execute(proc_name, params=(), db_name=None):
    """Ejecuta un procedimiento de DML (INSERT/UPDATE/DELETE) que
    no necesita devolver filas. Consume (y descarta) cualquier result
    set que el procedimiento haya dejado para evitar "Unread result
    found" en mysql-connector cuando el SP termina con un SELECT de
    control (ej: LAST_INSERT_ID(), ROW_COUNT()). Igual commit."""
    return _run(proc_name, params, dictionary=False, fetch=False, commit=True, drain=True, db_name=db_name)
