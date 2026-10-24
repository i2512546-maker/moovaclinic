from contextlib import contextmanager
from contextvars import ContextVar

import mysql.connector
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
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=db_name,
        port=DB_PORT,
        connection_timeout=8,
    )
    # Evita esperas eternas si una operacion queda esperando un lock de
    # InnoDB (default 50s): cualquier lock wait falla en 5s.
    try:
        cursor = conn.cursor()
        cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
        cursor.close()
    except Exception:
        # Se deja en pass a proposito: si no se pudo aplicar (permisos,
        # version), la conexion sigue sirviendo y queda con el timeout
        # por defecto de InnoDB. Un aviso aqui se repetiria en cada
        # conexion de cada request.
        pass
    return conn


@contextmanager
def db_connection(db_name=None):
    conn = get_connection(db_name=db_name)
    try:
        yield conn
    finally:
        conn.close()
