import mysql.connector
from contextlib import contextmanager
from shared.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT


def get_connection(db_name=None):
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=db_name or DB_NAME,
        port=DB_PORT,
    )


@contextmanager
def db_connection(db_name=None):
    conn = get_connection(db_name=db_name)
    try:
        yield conn
    finally:
        conn.close()
