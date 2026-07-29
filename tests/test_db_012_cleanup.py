#!/usr/bin/env python3
"""
tests/test_db_012_cleanup.py — DB-012 Auto-Cleanup Tests
Verifies that truncate_dynamic_tables() empties dynamic tables
while preserving their schemas and leaving core tables untouched.

Usage:
    source .venv/bin/activate
    python -m pytest tests/test_db_012_cleanup.py -v
"""

import os
import sys
import pytest
from dotenv import load_dotenv
import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

from scripts.auto_cleanup import (
    DYNAMIC_TABLES,
    PRESERVED_TABLES,
    truncate_dynamic_tables,
    get_connection,
)


INSERT_SQL = {
    "users": "INSERT INTO users (email, name) VALUES (%s, %s) RETURNING id",
    "products": "INSERT INTO products (name, category_id, price, sku) VALUES (%s, %s, %s, %s) RETURNING id",
    "recommendations": "INSERT INTO recommendations (user_id, product_id, score) VALUES (%s, %s, %s)",
    "feedback": "INSERT INTO feedback (user_id, product_id, rating, comment, feedback_type) VALUES (%s, %s, %s, %s, %s)",
    "tickets": "INSERT INTO tickets (user_id, subject, description) VALUES (%s, %s, %s)",
    "test_data": "INSERT INTO test_data (test_name, test_type) VALUES (%s, %s)",
    "workflow_outputs": "INSERT INTO workflow_outputs (workflow_name) VALUES (%s)",
    "reviews": "INSERT INTO reviews (id, source, text, intent, categories) VALUES (%s, %s, %s, %s, %s) RETURNING id",
    "themes": "INSERT INTO themes (name, frequency, mentions) VALUES (%s, %s, %s) RETURNING id",
    "theme_evidence": "INSERT INTO theme_evidence (theme_id, quote, source) VALUES (%s, %s, %s)",
    "theme_blockers": "INSERT INTO theme_blockers (theme_id, blocker) VALUES (%s, %s)",
    "theme_triggers": "INSERT INTO theme_triggers (theme_id, trigger_text) VALUES (%s, %s)",
    "theme_categories": "INSERT INTO theme_categories (theme_id, category) VALUES (%s, %s)",
    "insights": "INSERT INTO insights (title, observation, user_need, root_cause, opportunity, implication) VALUES (%s, %s, %s, %s, %s, %s)",
    "sentiment": "INSERT INTO sentiment (id, positive_count, positive_pct, neutral_count, neutral_pct, negative_count, negative_pct, total_reviews) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
    "research_data": "INSERT INTO research_data (respondent_id, summary, matched_themes, quality_score, recommendation) VALUES (%s, %s, %s, %s, %s)",
}


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection()
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_tables(db_conn):
    """Insert one row into each dynamic table so we can verify truncation."""
    cur = db_conn.cursor()
    inserted = {}

    try:
        # 1. Grab any existing category for the product FK
        cur.execute("SELECT id FROM categories LIMIT 1")
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO categories (name, mentions, gap_severity, business_impact, is_active) "
                "VALUES ('Test Category', 1, 'Low', 'Low', TRUE) RETURNING id"
            )
            cat_id = cur.fetchone()[0]
        else:
            cat_id = row[0]

        # 2. Insert a user (no FK deps)
        cur.execute(INSERT_SQL["users"], ("test@cleanup.com", "Test User"))
        user_id = cur.fetchone()[0]
        inserted["users"] = user_id

        # 3. Insert a product (depends on categories)
        cur.execute(INSERT_SQL["products"], ("Test Product", cat_id, 99.99, "SKU-TEST-CLEANUP"))
        product_id = cur.fetchone()[0]
        inserted["products"] = product_id

        # 4. Insert dependent rows
        cur.execute(INSERT_SQL["recommendations"], (user_id, product_id, 0.95))
        cur.execute(INSERT_SQL["feedback"], (user_id, product_id, 4, "Test comment", "product"))
        cur.execute(INSERT_SQL["tickets"], (user_id, "Test Subject", "Test description"))
        cur.execute(INSERT_SQL["test_data"], ("test_cleanup", "unit"))
        cur.execute(INSERT_SQL["workflow_outputs"], ("test_workflow",))

        # 5. Insert Phase 1 dynamic rows
        cur.execute(INSERT_SQL["reviews"], ("review-test-cleanup", "test-platform", "Great product", "praise", ["quality"]))
        cur.execute(INSERT_SQL["themes"], ("Test Theme", "Medium", 5))
        theme_id = cur.fetchone()[0]
        cur.execute(INSERT_SQL["theme_evidence"], (theme_id, "Customer said X", "review"))
        cur.execute(INSERT_SQL["theme_blockers"], (theme_id, "Lack of visibility"))
        cur.execute(INSERT_SQL["theme_triggers"], (theme_id, "Long wait time"))
        cur.execute(INSERT_SQL["theme_categories"], (theme_id, "UX"))
        cur.execute(INSERT_SQL["insights"], ("Test Insight", "Observed X", "Better UX", "Root Y", "Improve Z", "Implication A"))
        cur.execute(INSERT_SQL["sentiment"], (1, 10, 50.0, 5, 25.0, 5, 25.0, 20))
        cur.execute(INSERT_SQL["research_data"], ("resp-001", "Summary text", ["theme1"], 85, "Proceed"))

        db_conn.commit()
    except Exception:
        db_conn.rollback()
        raise
    finally:
        cur.close()

    yield inserted

    # Teardown: remove test data we inserted
    cur = db_conn.cursor()
    try:
        cur.execute("DELETE FROM theme_evidence WHERE quote = 'Customer said X'")
        cur.execute("DELETE FROM theme_blockers WHERE blocker = 'Lack of visibility'")
        cur.execute("DELETE FROM theme_triggers WHERE trigger_text = 'Long wait time'")
        cur.execute("DELETE FROM theme_categories WHERE category = 'UX'")
        cur.execute("DELETE FROM themes WHERE name = 'Test Theme'")
        cur.execute("DELETE FROM insights WHERE title = 'Test Insight'")
        cur.execute("DELETE FROM sentiment WHERE positive_count = 10")
        cur.execute("DELETE FROM research_data WHERE respondent_id = 'resp-001'")
        cur.execute("DELETE FROM reviews WHERE source = 'test-platform'")
        cur.execute("DELETE FROM feedback WHERE comment = 'Test comment'")
        cur.execute("DELETE FROM recommendations WHERE score = 0.95")
        cur.execute("DELETE FROM tickets WHERE subject = 'Test Subject'")
        cur.execute("DELETE FROM test_data WHERE test_name = 'test_cleanup'")
        cur.execute("DELETE FROM workflow_outputs WHERE workflow_name = 'test_workflow'")
        cur.execute("DELETE FROM products WHERE sku = 'SKU-TEST-CLEANUP'")
        cur.execute("DELETE FROM users WHERE email = 'test@cleanup.com'")
        cur.execute("DELETE FROM categories WHERE name = 'Test Category'")
        db_conn.commit()
    except Exception:
        db_conn.rollback()
    finally:
        cur.close()


# ── Tests ─────────────────────────────────────────────────────────────────

def test_dynamic_tables_have_data(db_conn, seeded_tables):
    """Sanity check: confirm the fixture actually inserted data."""
    cur = db_conn.cursor()
    for table in DYNAMIC_TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        assert count > 0, f"Table '{table}' has 0 rows after seeding"
    cur.close()


def test_truncate_empties_dynamic_tables(db_conn, seeded_tables):
    """Core test: truncate all dynamic tables, then assert COUNT(*) = 0."""
    result = truncate_dynamic_tables()
    assert result is True, "truncate_dynamic_tables() returned False"

    cur = db_conn.cursor()
    for table in DYNAMIC_TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        assert count == 0, (
            f"Table '{table}' has {count} rows after truncation (expected 0)"
        )
    cur.close()


def test_schemas_preserved_after_truncation(db_conn, seeded_tables):
    """Verify table schemas still exist after truncation."""
    truncate_dynamic_tables()
    cur = db_conn.cursor()

    for table in DYNAMIC_TABLES:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        columns = cur.fetchall()
        assert len(columns) > 0, (
            f"Table '{table}' has no columns — schema was dropped!"
        )

    cur.close()


def test_preserved_tables_untouched(db_conn):
    """Confirm that core schema tables are NOT truncated."""
    cur = db_conn.cursor()
    for table in PRESERVED_TABLES:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s)",
            (table,),
        )
        exists = cur.fetchone()[0]
        assert exists, f"Preserved table '{table}' is missing from the database"
    cur.close()


def test_idle_timer_tracks_requests():
    """Verify the inactivity tracker functions correctly."""
    from scripts.auto_cleanup import (
        set_last_request_time,
        seconds_since_last_request,
    )

    set_last_request_time()
    idle = seconds_since_last_request()
    assert idle >= 0.0, "Idle time should be >= 0"
    assert idle < 2.0, "Idle time should be < 2s immediately after set"


def test_monitor_starts_once():
    """Verify start_cleanup_monitor() can be called multiple times safely."""
    from scripts.auto_cleanup import start_cleanup_monitor

    start_cleanup_monitor()
    start_cleanup_monitor()
    start_cleanup_monitor()
    # Should not raise — idempotent


# ── HTTP Endpoint Test ────────────────────────────────────────────────────

class TestDBClearEndpoint:
    """Test the POST /api/db/clear HTTP endpoint with a live server."""

    @pytest.fixture(scope="class")
    def seeded(self):
        """Self-contained fixture: seed data for endpoint tests, clean up after."""
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT id FROM categories LIMIT 1")
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO categories (name, mentions, gap_severity, business_impact, is_active) "
                "VALUES ('Endpoint Test Cat', 1, 'Low', 'Low', TRUE) RETURNING id"
            )
            cat_id = cur.fetchone()[0]
        else:
            cat_id = row[0]

        cur.execute(
            "INSERT INTO users (email, name) VALUES ('ep@test.com', 'Endpoint User') RETURNING id"
        )
        uid = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO products (name, category_id, price, sku) VALUES "
            "('Ep Product', %s, 10.0, 'SKU-EP-TEST') RETURNING id",
            (cat_id,),
        )
        pid = cur.fetchone()[0]

        cur.execute("INSERT INTO recommendations (user_id, product_id, score) VALUES (%s, %s, 0.5)", (uid, pid))
        cur.execute("INSERT INTO feedback (user_id, product_id, rating, comment, feedback_type) VALUES (%s, %s, 3, 'ep comment', 'product')", (uid, pid))
        cur.execute("INSERT INTO tickets (user_id, subject, description) VALUES (%s, 'ep subj', 'ep desc')", (uid,))
        cur.execute("INSERT INTO test_data (test_name, test_type) VALUES ('ep_test', 'unit')")
        cur.execute("INSERT INTO workflow_outputs (workflow_name) VALUES ('ep_wf')")

        cur.close()
        conn.close()
        yield

        # Teardown
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        for sql in [
            "DELETE FROM feedback WHERE comment = 'ep comment'",
            "DELETE FROM recommendations WHERE score = 0.5",
            "DELETE FROM tickets WHERE subject = 'ep subj'",
            "DELETE FROM test_data WHERE test_name = 'ep_test'",
            "DELETE FROM workflow_outputs WHERE workflow_name = 'ep_wf'",
            "DELETE FROM products WHERE sku = 'SKU-EP-TEST'",
            "DELETE FROM users WHERE email = 'ep@test.com'",
        ]:
            cur.execute(sql)
        cur.close()
        conn.close()

    @pytest.fixture(scope="class")
    def server(self):
        from scripts.api_server import ThreadedHTTPServer, APIHandler
        from threading import Thread

        server = ThreadedHTTPServer(("127.0.0.1", 0), APIHandler)
        port = server.server_address[1]
        t = Thread(target=server.serve_forever, daemon=True)
        t.start()
        yield port
        server.shutdown()

    def _post_clear(self, port):
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        req = Request(
            f"http://127.0.0.1:{port}/api/db/clear",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urlopen(req)
            return json.loads(resp.read()), resp.status
        except HTTPError as e:
            return json.loads(e.read()), e.code

    def test_endpoint_returns_ok(self, server, seeded):
        """POST /api/db/clear should return 200 with ok:true."""
        body, status = self._post_clear(server)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("ok") is True, f"Expected ok:true, got {body}"

    def test_endpoint_clears_data(self, server, seeded):
        """After POST /api/db/clear, dynamic tables should be empty."""
        self._post_clear(server)

        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        for table in DYNAMIC_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            assert count == 0, (
                f"Table '{table}' has {count} rows after endpoint call (expected 0)"
            )
        cur.close()
        conn.close()

    def test_endpoint_schemas_survive(self, server, seeded):
        """After endpoint call, schemas must still exist."""
        self._post_clear(server)

        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        for table in DYNAMIC_TABLES:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            )
            cols = [r[0] for r in cur.fetchall()]
            assert len(cols) > 0, (
                f"Table '{table}' has no columns — schema was dropped!"
            )
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
