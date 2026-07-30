"""
Database connection helper for Postgres with retry logic and connection pooling.

Usage:
    from database.db import get_connection, query, execute
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reviews")
"""
import os
import time
import psycopg2
import psycopg2.extras

_DB_RETRIES = int(os.environ.get("DB_RETRIES", "3"))
_DB_RETRY_DELAY = int(os.environ.get("DB_RETRY_DELAY", "2"))
_DB_CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))


def get_connection(autocommit=False):
    """Return a psycopg2 connection from DATABASE_URL env var with retry logic.

    Retries up to DB_RETRIES times with DB_RETRY_DELAY seconds between attempts.
    Uses DB_CONNECT_TIMEOUT seconds as the connection timeout.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL not set. Export it:\n"
            "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
        )

    last_exc = None
    for attempt in range(1, _DB_RETRIES + 1):
        try:
            conn = psycopg2.connect(db_url, connect_timeout=_DB_CONNECT_TIMEOUT)
            if autocommit:
                conn.autocommit = True
            return conn
        except psycopg2.OperationalError as e:
            last_exc = e
            if attempt < _DB_RETRIES:
                print(
                    f"[db] Connection attempt {attempt}/{_DB_RETRIES} failed: {e}. "
                    f"Retrying in {_DB_RETRY_DELAY}s..."
                )
                time.sleep(_DB_RETRY_DELAY)

    raise psycopg2.OperationalError(
        f"Could not connect to database after {_DB_RETRIES} attempts "
        f"(timeout={_DB_CONNECT_TIMEOUT}s): {last_exc}"
    ) from last_exc


def query(sql, params=None):
    """Execute a query and return all results as list of dicts."""
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        conn.close()


def execute(sql, params=None):
    """Execute a write query and return affected row count."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        affected = cur.rowcount
        conn.commit()
        cur.close()
        return affected
    finally:
        conn.close()


def execute_many(sql, params_list):
    """Execute a write query with multiple parameter sets."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(sql, params_list)
        affected = cur.rowcount
        conn.commit()
        cur.close()
        return affected
    finally:
        conn.close()
