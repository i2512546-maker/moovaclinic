import mysql.connector
from contextlib import contextmanager
from shared.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
    )


@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
