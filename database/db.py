"""
Database connection helper for Postgres.

Usage:
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reviews")
"""
import os
import psycopg2
import psycopg2.extras


def get_connection():
    """Return a psycopg2 connection from DATABASE_URL env var."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL not set. Export it:\n"
            "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
        )
    return psycopg2.connect(db_url)


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
