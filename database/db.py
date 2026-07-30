"""
Database connection helper for Postgres with lazy initialization,
retry logic, and automatic sslmode=require for Supabase.

Usage:
    from database.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reviews")
"""
import os
import time
import re
import psycopg2
import psycopg2.extras


def _ensure_sslmode(url):
    """Append sslmode=require for remote hosts if not already present.
    Required by Supabase and most cloud PostgreSQL providers.
    Skips localhost connections to avoid breaking local development.
    """
    if "sslmode" in url:
        return url
    host = _extract_host(url)
    if host and host in ("localhost", "127.0.0.1", "::1"):
        return url
    url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


def _extract_host(url):
    """Extract hostname from a postgresql:// connection URL."""
    m = re.match(r"postgres(?:ql)?://[^@]*@([^:/?#]+)", url)
    return m.group(1) if m else None


def get_db_connection(autocommit=False):
    """Return a psycopg2 connection from DATABASE_URL env var.
    No connection is attempted until this function is called.
    Retries up to DB_RETRIES times with DB_RETRY_DELAY seconds between attempts.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL not set. Export it:\n"
            "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
        )

    db_url = _ensure_sslmode(db_url)
    retries = int(os.environ.get("DB_RETRIES", "3"))
    retry_delay = int(os.environ.get("DB_RETRY_DELAY", "2"))
    connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(db_url, connect_timeout=connect_timeout)
            if autocommit:
                conn.autocommit = True
            return conn
        except psycopg2.OperationalError as e:
            last_exc = e
            if attempt < retries:
                print(
                    f"[db] Connection attempt {attempt}/{retries} failed: {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)

    raise psycopg2.OperationalError(
        f"Could not connect to database after {retries} attempts "
        f"(timeout={connect_timeout}s): {last_exc}"
    ) from last_exc


# Backward-compatible alias so existing callers (auto_cleanup, api_server, etc.)
# continue to work without changes.
get_connection = get_db_connection


def query(sql, params=None):
    """Execute a query and return all results as list of dicts."""
    conn = get_db_connection()
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
    conn = get_db_connection()
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
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.executemany(sql, params_list)
        affected = cur.rowcount
        conn.commit()
        cur.close()
        return affected
    finally:
        conn.close()
