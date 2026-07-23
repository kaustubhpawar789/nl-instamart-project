#!/usr/bin/env python3
"""
tests/test_db_005_setup.py — DB-005 Verification Tests
Verifies all Phase 2 tables exist and mock data is seeded.

Usage:
    source .venv/bin/activate
    python -m pytest tests/test_db_005_setup.py -v
"""

import os
import sys
import pytest
from dotenv import load_dotenv
import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "instamart"),
        user=os.getenv("DB_USER", "nitin"),
        password=os.getenv("DB_PASSWORD", "nitin"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


PHASE2_TABLES = [
    "users",
    "products",
    "categories",
    "recommendations",
    "feedback",
    "tickets",
    "test_data",
    "workflow_outputs",
]

MIN_ROWS = {
    "categories": 10,
    "products": 50,
    "users": 10,
    "recommendations": 10,
    "feedback": 10,
    "tickets": 5,
    "test_data": 5,
    "workflow_outputs": 5,
}


@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def db_tables(db_conn):
    cur = db_conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    cur.close()
    return tables


class TestTableExistence:
    @pytest.mark.parametrize("table", PHASE2_TABLES)
    def test_table_exists(self, db_tables, table):
        assert table in db_tables, f"Table '{table}' not found in database"


class TestMockDataSeeded:
    @pytest.mark.parametrize("table,min_rows", MIN_ROWS.items())
    def test_minimum_rows(self, db_conn, table, min_rows):
        cur = db_conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        cur.close()
        assert count >= min_rows, (
            f"Table '{table}' has {count} rows, expected at least {min_rows}"
        )


class TestForeignKeyIntegrity:
    def test_products_reference_valid_categories(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.category_id IS NOT NULL AND c.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        cur.close()
        assert orphans == 0, f"Found {orphans} products referencing non-existent categories"

    def test_recommendations_reference_valid_users(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM recommendations r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE u.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        cur.close()
        assert orphans == 0, f"Found {orphan} recommendations referencing non-existent users"

    def test_recommendations_reference_valid_products(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM recommendations r
            LEFT JOIN products p ON r.product_id = p.id
            WHERE p.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        cur.close()
        assert orphans == 0, f"Found {orphan} recommendations referencing non-existent products"

    def test_feedback_reference_valid_users(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            WHERE f.user_id IS NOT NULL AND u.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        cur.close()
        assert orphans == 0, f"Found {orphan} feedback entries referencing non-existent users"

    def test_tickets_reference_valid_users(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.user_id IS NOT NULL AND u.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        cur.close()
        assert orphans == 0, f"Found {orphan} tickets referencing non-existent users"


class TestSchemaConstraints:
    def test_products_price_positive(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products WHERE price <= 0")
        bad = cur.fetchone()[0]
        cur.close()
        assert bad == 0, f"Found {bad} products with non-positive price"

    def test_users_unique_emails(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1")
        dupes = cur.fetchall()
        cur.close()
        assert len(dupes) == 0, f"Found duplicate emails: {dupes}"

    def test_products_unique_skus(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT sku, COUNT(*) FROM products GROUP BY sku HAVING COUNT(*) > 1")
        dupes = cur.fetchall()
        cur.close()
        assert len(dupes) == 0, f"Found duplicate SKUs: {dupes}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
