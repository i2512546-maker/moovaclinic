import hashlib
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from flask import request

from shared.config import (
    AUDIT_DB_NAME,
    AUTH_DB_NAME,
    CITAS_DB_NAME,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    NOTAS_DB_NAME,
    PACIENTES_DB_NAME,
    PAGOS_DB_NAME,
)

_DB_DOMINIOS = {
    "auth": AUTH_DB_NAME,
    "pacientes": PACIENTES_DB_NAME,
    "citas": CITAS_DB_NAME,
    "pagos": PAGOS_DB_NAME,
    "notas": NOTAS_DB_NAME,
    "audit": AUDIT_DB_NAME,
}
_DB_ACTUAL = ContextVar("moova_db_actual", default=None)

# Un pool por base de datos. Las conexiones se reutilizan entre peticiones
# y close() las devuelve al pool en lugar de abrir/cerrar TCP en cada query.
_POOLS = {}
_POOLS_LOCK = threading.Lock()


def _pool_para(db_name):
    clave = (DB_HOST, DB_PORT, DB_USER, db_name)
    pool = _POOLS.get(clave)
    if pool is not None:
        return pool

    with _POOLS_LOCK:
        pool = _POOLS.get(clave)
        if pool is None:
            try:
                pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
            except (TypeError, ValueError):
                pool_size = 5
            pool_size = max(2, min(pool_size, 10))
            nombre = "moova_" + hashlib.sha1(
                "|".join(map(str, clave)).encode("utf-8")
            ).hexdigest()[:12]
            pool = MySQLConnectionPool(
                pool_name=nombre,
                pool_size=pool_size,
                pool_reset_session=True,
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=db_name,
                port=DB_PORT,
                connection_timeout=8,
            )
            _POOLS[clave] = pool
    return pool


@contextmanager
def dominio(nombre):
    """Fija la base de datos correspondiente al dominio durante el bloque."""
    try:
        db_name = _DB_DOMINIOS[nombre]
    except KeyError as exc:
        raise ValueError(f"Dominio de base de datos desconocido: {nombre}") from exc

    token = _DB_ACTUAL.set(db_name)
    try:
        yield
    finally:
        _DB_ACTUAL.reset(token)


def configurar_dominio_blueprint(blueprint, nombre):
    """Aplica el contexto de base de datos a cada petición del blueprint."""
    clave_contexto = f"_moova_db_context_{nombre}"

    @blueprint.before_request
    def _fijar_dominio():
        contexto = dominio(nombre)
        contexto.__enter__()
        request.environ[clave_contexto] = contexto

    @blueprint.teardown_request
    def _restablecer_dominio(error=None):
        contexto = request.environ.pop(clave_contexto, None)
        if contexto is not None:
            error_info = (type(error), error, error.__traceback__) if error else (
                None, None, None
            )
            contexto.__exit__(*error_info)


def get_connection(db_name=None):
    if db_name is None:
        dominio_actual = _DB_ACTUAL.get()
        db_name = dominio_actual if dominio_actual is not None else DB_NAME

    conn = _pool_para(db_name).get_connection()
    cursor = None
    try:
        # La zona horaria y el límite de espera se aplican al sacar cada
        # conexión, porque MySQL conserva variables SESSION al reutilizarla.
        cursor = conn.cursor()
        cursor.execute("SET SESSION time_zone = '-05:00'")
        try:
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
        except Exception:
            # Compatibilidad con servidores que no permitan cambiar esta
            # variable por sesión. La conexión sigue siendo utilizable.
            pass
        return conn
    except Exception:
        conn.close()
        raise
    finally:
        if cursor is not None:
            cursor.close()


@contextmanager
def db_connection(db_name=None):
    conn = get_connection(db_name=db_name)
    try:
        yield conn
    finally:
        conn.close()
