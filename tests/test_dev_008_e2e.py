#!/usr/bin/env python3
"""
tests/test_dev_008_e2e.py — DEV-008 End-to-End Health Check
Verifies deployment configuration files, the PORT env patch, docs completeness,
database connection resilience, and runs an E2E health check against all core
API endpoints.

Usage:
    python -m pytest tests/test_dev_008_e2e.py -v
    # (API endpoint tests require the server to be running on localhost:8080)
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

import psycopg2
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
API_BASE = os.environ.get("API_BASE", "http://localhost:8080")

REQUIRED_DEPLOYMENT_FILES = [
    "Procfile",
    "railway.json",
    "requirements.txt",
    "Dockerfile",
]


class TestDeploymentFiles(unittest.TestCase):
    """Structural checks — no server needed."""

    def test_procfile_exists_and_correct(self):
        path = os.path.join(ROOT, "Procfile")
        self.assertTrue(os.path.isfile(path), "Procfile missing")
        with open(path) as f:
            content = f.read().strip()
        self.assertEqual(content, "web: python scripts/api_server.py")

    def test_railway_json_exists_and_valid(self):
        path = os.path.join(ROOT, "railway.json")
        self.assertTrue(os.path.isfile(path), "railway.json missing")
        with open(path) as f:
            cfg = json.load(f)
        self.assertEqual(cfg["build"]["builder"], "DOCKERFILE")
        self.assertEqual(cfg["build"]["dockerfilePath"], "Dockerfile")
        self.assertIn("healthcheckPath", cfg["deploy"])
        self.assertEqual(cfg["deploy"]["healthcheckPath"], "/api/kpis")

    def test_requirements_txt_exists(self):
        path = os.path.join(ROOT, "requirements.txt")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            deps = f.read()
        self.assertIn("requests", deps)
        self.assertIn("psycopg2-binary", deps)
        self.assertIn("python-dotenv", deps)

    def test_dockerfile_exists(self):
        path = os.path.join(ROOT, "Dockerfile")
        self.assertTrue(os.path.isfile(path), "Dockerfile missing")

    def test_api_server_port_patch(self):
        """Verify the PORT env var fallback is in api_server.py."""
        path = os.path.join(ROOT, "scripts", "api_server.py")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            content = f.read()
        self.assertIn('os.environ.get("PORT", 8080)', content,
                      "PORT env var patch missing — expected os.environ.get(\"PORT\", 8080)")

    def test_deployment_docs_exist(self):
        path = os.path.join(ROOT, "docs", "deployment.md")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            md = f.read()
        required_sections = [
            "Railway Deployment (Production)",
            "Step 1: Push Code to GitHub",
            "Step 2: Create a Railway Project",
            "Step 3: Provision PostgreSQL",
            "Step 4: Initialize the Database Schema",
            "GitHub Auto-Deploy",
        ]
        for section in required_sections:
            self.assertIn(section, md, f"deployment.md missing section: {section}")

    def test_context_md_has_dev008(self):
        path = os.path.join(ROOT, "docs", "context.md")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            content = f.read()
        self.assertIn("DEV-008 completed", content,
                      "context.md missing DEV-008 completed entry")
        self.assertIn("fully deployed and ready for final PPT presentation", content,
                      "context.md missing 'fully deployed and ready for final PPT presentation'")

    def test_all_deployment_files_present(self):
        for name in REQUIRED_DEPLOYMENT_FILES:
            path = os.path.join(ROOT, name)
            self.assertTrue(os.path.isfile(path), f"Missing deployment file: {name}")

    def test_gitignore_covers_dot_env_and_logs(self):
        path = os.path.join(ROOT, ".gitignore")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            lines = f.read().splitlines()
        ignored = set(lines)
        for pattern in [".env", ".env.*", "secrets/.env", "*.log", "__pycache__/"]:
            self.assertIn(pattern, ignored, f".gitignore missing pattern: {pattern}")


class TestAPIEndpoints(unittest.TestCase):
    """E2E endpoint health checks — requires server on API_BASE."""

    @classmethod
    def setUpClass(cls):
        try:
            r = requests.get(f"{API_BASE}/api/kpis", timeout=5)
            cls.server_available = r.status_code == 200
        except Exception:
            cls.server_available = False
            raise unittest.SkipTest(
                f"API server not reachable at {API_BASE}. "
                "Start the server first:\n"
                "  python scripts/api_server.py\n"
                "Then re-run these tests."
            )

    def test_endpoint_kpis(self):
        r = requests.get(f"{API_BASE}/api/kpis", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        expected_keys = {"ai_analyzed", "themes", "key_insights", "categories",
                         "data_sources", "survey_responses", "last_updated"}
        self.assertTrue(expected_keys.issubset(data.keys()),
                        f"Missing KPIs keys: {expected_keys - data.keys()}")

    def test_endpoint_insights(self):
        r = requests.get(f"{API_BASE}/api/insights", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        for key in ("themes", "insights", "sentiment", "categories"):
            self.assertIn(key, data, f"insights missing key: {key}")

    def test_endpoint_records(self):
        r = requests.get(f"{API_BASE}/api/records", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("records", data)
        self.assertIn("total", data)

    def test_endpoint_charts_data(self):
        r = requests.get(f"{API_BASE}/api/charts/data", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("labels", data)
        self.assertIn("values", data)

    def test_endpoint_charts_configs(self):
        r = requests.get(f"{API_BASE}/api/charts/configs", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_endpoint_scrape_status(self):
        r = requests.get(f"{API_BASE}/api/scrape/status", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("running", data)

    def test_endpoint_survey_responses(self):
        r = requests.get(f"{API_BASE}/api/survey/responses", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("responses", data)
        self.assertIn("total", data)

    def test_endpoint_matrix(self):
        r = requests.get(f"{API_BASE}/api/matrix", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("categories", data)
        self.assertIn("total_reviews", data)
        if data["categories"]:
            cat = data["categories"][0]
            for key in ("id", "name", "mentions", "sources"):
                self.assertIn(key, cat, f"matrix category missing key: {key}")

    def test_endpoint_users(self):
        r = requests.get(f"{API_BASE}/api/users", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("users", data)
        self.assertIn("total", data)

    def test_endpoint_products(self):
        r = requests.get(f"{API_BASE}/api/products", timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("products", data)
        if data["products"]:
            p = data["products"][0]
            for key in ("id", "name", "price", "sku", "category_name"):
                self.assertIn(key, p, f"product missing key: {key}")

    def test_endpoint_cart_no_user_returns_400(self):
        r = requests.get(f"{API_BASE}/api/cart", timeout=10)
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertIn("error", data)

    def test_static_ui_index_serves(self):
        r = requests.get(f"{API_BASE}/ui/index.html", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("Content-Type", ""))

    def test_static_ui_shop_serves(self):
        r = requests.get(f"{API_BASE}/ui/shop.html", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("Content-Type", ""))

    def test_static_css_served_at_root(self):
        """CSS files (referenced relatively by HTML) are served from ui/ dir."""
        r = requests.get(f"{API_BASE}/styles.css", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/css", r.headers.get("Content-Type", ""))

    def test_static_js_served_at_root(self):
        """JS files (referenced relatively by HTML) are served from ui/ dir."""
        r = requests.get(f"{API_BASE}/app.js", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r.headers.get("Content-Type", ""))

    def test_static_shop_css_served_at_root(self):
        r = requests.get(f"{API_BASE}/shop.css", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/css", r.headers.get("Content-Type", ""))

    def test_root_serves_index_html(self):
        r = requests.get(f"{API_BASE}/", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("Content-Type", ""))

    def test_cors_headers_present(self):
        r = requests.get(f"{API_BASE}/api/kpis", timeout=10)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")

    def test_post_search_returns_json(self):
        r = requests.post(f"{API_BASE}/api/search",
                          json={"query": "delivery"},
                          timeout=15)
        self.assertIn(r.status_code, (200, 502, 503))
        data = r.json()
        if r.status_code == 200:
            self.assertIn("answer", data)

    def test_unknown_endpoint_returns_404(self):
        r = requests.get(f"{API_BASE}/api/nonexistent", timeout=10)
        self.assertEqual(r.status_code, 404)


class TestDatabaseResilience(unittest.TestCase):
    """Database connection resilience tests — no server needed."""

    def setUp(self):
        self._env_backup = {}
        for key in ("DATABASE_URL", "DB_RETRIES", "DB_RETRY_DELAY", "DB_CONNECT_TIMEOUT"):
            self._env_backup[key] = os.environ.get(key)
        os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/testdb"
        os.environ["DB_RETRIES"] = "1"
        os.environ["DB_RETRY_DELAY"] = "0"
        os.environ["DB_CONNECT_TIMEOUT"] = "1"

    def tearDown(self):
        for key, val in self._env_backup.items():
            if val is not None:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

    def test_database_db_has_retry_logic(self):
        """Verify database/db.py has retry with configurable env vars."""
        path = os.path.join(ROOT, "database", "db.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("get_db_connection", content,
                      "Missing get_db_connection factory function")
        self.assertIn("DB_RETRIES", content,
                      "Missing DB_RETRIES env var for retry count")
        self.assertIn("DB_CONNECT_TIMEOUT", content,
                      "Missing DB_CONNECT_TIMEOUT env var")
        self.assertIn("DB_RETRY_DELAY", content,
                      "Missing DB_RETRY_DELAY env var")
        self.assertIn("connect_timeout", content,
                      "Missing connect_timeout parameter in psycopg2.connect()")
        self.assertIn("for attempt in range(1, retries + 1):", content,
                      "Missing retry loop in get_db_connection()")
        self.assertIn("time.sleep(retry_delay)", content,
                      "Missing delay between retries")

    def test_get_connection_reads_database_url(self):
        """get_db_connection reads DATABASE_URL from environment."""
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("mocked")
            with self.assertRaises(psycopg2.OperationalError):
                get_db_connection()
            mock_connect.assert_called_once()
            args, _ = mock_connect.call_args
            self.assertIn("testdb", args[0])
            self.assertIn("test:test", args[0])

    def test_get_connection_appends_sslmode_for_remote_host(self):
        """sslmode=require is appended for non-localhost hosts."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@db.supabase.com:6543/mydb"
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("mocked")
            with self.assertRaises(psycopg2.OperationalError):
                get_db_connection()
            mock_connect.assert_called_once()
            args, _ = mock_connect.call_args
            self.assertEqual(
                args[0],
                "postgresql://user:pass@db.supabase.com:6543/mydb?sslmode=require"
            )

    def test_get_connection_skips_sslmode_for_localhost(self):
        """sslmode=require is NOT appended for localhost connections."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/mydb"
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("mocked")
            with self.assertRaises(psycopg2.OperationalError):
                get_db_connection()
            mock_connect.assert_called_once()
            args, _ = mock_connect.call_args
            self.assertEqual(args[0], "postgresql://user:pass@localhost:5432/mydb")

    def test_get_connection_passes_connect_timeout(self):
        """connect_timeout is passed to psycopg2.connect."""
        os.environ["DB_CONNECT_TIMEOUT"] = "7"
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("mocked")
            with self.assertRaises(psycopg2.OperationalError):
                get_db_connection()
            mock_connect.assert_called_once()
            _, kwargs = mock_connect.call_args
            self.assertEqual(kwargs.get("connect_timeout"), 7)

    def test_get_connection_retries_on_operational_error(self):
        """get_db_connection retries DB_RETRIES times on OperationalError."""
        os.environ["DB_RETRIES"] = "3"
        os.environ["DB_RETRY_DELAY"] = "0"
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("transient failure")
            with self.assertRaises(psycopg2.OperationalError):
                get_db_connection()
            self.assertEqual(mock_connect.call_count, 3)

    def test_get_connection_succeeds_on_second_attempt(self):
        """get_db_connection succeeds if retry succeeds."""
        os.environ["DB_RETRIES"] = "3"
        os.environ["DB_RETRY_DELAY"] = "0"
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = [
                psycopg2.OperationalError("first fail"),
                psycopg2.OperationalError("second fail"),
                True,
            ]
            conn = get_db_connection()
            self.assertEqual(mock_connect.call_count, 3)
            self.assertIsNotNone(conn)

    def test_get_connection_respects_autocommit(self):
        """autocommit=True enables autocommit on the connection."""
        from database.db import get_db_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_conn = mock_connect.return_value
            conn = get_db_connection(autocommit=True)
            self.assertTrue(conn.autocommit)

    def test_auto_cleanup_delegates_to_database_db(self):
        """auto_cleanup.get_connection delegates to database.db.get_db_connection."""
        from scripts.auto_cleanup import get_connection as ac_get_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_connect.side_effect = psycopg2.OperationalError("mocked")
            with self.assertRaises(psycopg2.OperationalError):
                ac_get_connection()
            mock_connect.assert_called_once()

    def test_auto_cleanup_passes_autocommit(self):
        """auto_cleanup.get_connection passes autocommit to database.db."""
        from scripts.auto_cleanup import get_connection as ac_get_connection
        with patch("database.db.psycopg2.connect") as mock_connect:
            mock_conn = mock_connect.return_value
            conn = ac_get_connection(autocommit=True)
            self.assertTrue(conn.autocommit)

    def test_raises_value_error_if_no_database_url(self):
        """get_db_connection raises ValueError if DATABASE_URL is unset."""
        os.environ.pop("DATABASE_URL", None)
        from database.db import get_db_connection
        with self.assertRaises(ValueError) as ctx:
            get_db_connection()
        self.assertIn("DATABASE_URL not set", str(ctx.exception))

    def test_db_env_vars_have_sane_defaults(self):
        """DB_RETRIES, DB_RETRY_DELAY, DB_CONNECT_TIMEOUT defaults exist in database/db.py."""
        path = os.path.join(ROOT, "database", "db.py")
        with open(path) as f:
            content = f.read()
        self.assertIn('os.environ.get("DB_RETRIES', content)
        self.assertIn('os.environ.get("DB_RETRY_DELAY', content)
        self.assertIn('os.environ.get("DB_CONNECT_TIMEOUT', content)

    def test_ensure_sslmode_appends_require_for_remote(self):
        """_ensure_sslmode appends ?sslmode=require for non-localhost hosts."""
        from database.db import _ensure_sslmode
        result = _ensure_sslmode("postgresql://user:pass@db.supabase.com:6543/mydb")
        self.assertEqual(result, "postgresql://user:pass@db.supabase.com:6543/mydb?sslmode=require")

    def test_ensure_sslmode_skips_localhost(self):
        """_ensure_sslmode does NOT append sslmode=require for localhost."""
        from database.db import _ensure_sslmode
        result = _ensure_sslmode("postgresql://user:pass@localhost:5432/mydb")
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb")

    def test_ensure_sslmode_skips_localhost_ip(self):
        """_ensure_sslmode skips 127.0.0.1 as well."""
        from database.db import _ensure_sslmode
        result = _ensure_sslmode("postgresql://user:pass@127.0.0.1:5432/mydb")
        self.assertEqual(result, "postgresql://user:pass@127.0.0.1:5432/mydb")

    def test_ensure_sslmode_preserves_existing_sslmode(self):
        """_ensure_sslmode does not duplicate sslmode=require if already present."""
        from database.db import _ensure_sslmode
        url = "postgresql://user:pass@db.supabase.com:6543/mydb?sslmode=require"
        result = _ensure_sslmode(url)
        self.assertEqual(result.count("sslmode=require"), 1)

    def test_ensure_sslmode_appends_for_pooler_host(self):
        """_ensure_sslmode appends sslmode for pooler.supabase.com hosts."""
        from database.db import _ensure_sslmode
        result = _ensure_sslmode(
            "postgresql://postgres:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
        )
        self.assertIn("sslmode=require", result)

    def test_database_backed_endpoint_returns_json(self):
        """DB-backed endpoints return valid JSON (graceful error or success)."""
        try:
            r = requests.get(f"{API_BASE}/api/users", timeout=15)
            self.assertIn(r.status_code, (200, 500))
            data = r.json()
            self.assertTrue("users" in data or "error" in data)
        except requests.ConnectionError:
            self.skipTest("Server not available")


if __name__ == "__main__":
    unittest.main()
