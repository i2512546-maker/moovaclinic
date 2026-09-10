import mysql.connector
from contextlib import contextmanager
from shared.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT


def get_connection(db_name=None):
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=db_name or DB_NAME,
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
        pass
    return conn


@contextmanager
def db_connection(db_name=None):
    conn = get_connection(db_name=db_name)
    try:
        yield conn
    finally:
        conn.close()
