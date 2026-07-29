#!/usr/bin/env python3
"""
tests/test_eng_006_backend.py — ENG-006 "Try Next Basket" Backend Logic Tests
Verifies that POST /api/recommend accepts a cart payload, queries PostgreSQL,
calls Ollama, and returns a valid bundle recommendation with rationale.

Usage:
    source .venv/bin/activate
    python -m pytest tests/test_eng_006_backend.py -v
"""

import json
import os
import sys
import pytest
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

from scripts.auto_cleanup import get_connection

API_BASE = "http://localhost:8080"


@pytest.fixture(scope="module")
def api_url():
    """Health check — confirm server is reachable."""
    try:
        r = requests.get(f"{API_BASE}/api/kpis", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        pytest.fail(f"API server not reachable at {API_BASE}: {e}")
    return API_BASE


@pytest.fixture(scope="module")
def snack_products():
    """Fetch a few product IDs from the 'Snacks' category for use in cart."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE c.name = 'Snacks' AND p.is_active = TRUE
        LIMIT 3
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        pytest.fail("No Snacks products found — run 'python database/seed_mock_data.py' first")
    return [{"product_id": r[0], "name": r[1], "category": r[2]} for r in rows]


class TestRecommendEndpoint:

    def test_endpoint_reachable(self, api_url):
        """POST /api/recommend should be reachable and return 400 for missing body."""
        r = requests.post(f"{api_url}/api/recommend", json={}, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_empty_cart_rejected(self, api_url):
        """Empty or missing cart_items should be rejected."""
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": 1, "cart_items": []
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_missing_user_id_rejected(self, api_url):
        """Missing user_id should be rejected."""
        r = requests.post(f"{api_url}/api/recommend", json={
            "cart_items": [{"product_id": 1, "quantity": 2}]
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_invalid_product_rejected(self, api_url):
        """Non-existent product_id should return 400."""
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": 1, "cart_items": [{"product_id": 999999, "quantity": 1}]
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_successful_recommendation(self, api_url, snack_products):
        """Happy path: cart with Snacks products returns a valid recommendation."""
        cart = [{"product_id": p["product_id"], "quantity": 1} for p in snack_products]
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": 1, "cart_items": cart,
        }, timeout=90)

        # Allow 502 if Ollama is not running
        if r.status_code == 502:
            data = r.json()
            if "Ollama" in data.get("error", ""):
                pytest.skip("Ollama is not running — cannot test live recommendation")
            pytest.fail(f"Unexpected 502: {data}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()

        # Top-level fields
        assert data["user_id"] == 1
        assert len(data["cart_items"]) == len(snack_products)

        # Recommendation block
        rec = data["recommendation"]
        assert "adjacent_category" in rec
        assert isinstance(rec["adjacent_category"], str)
        assert len(rec["adjacent_category"]) > 0

        assert "rationale" in rec
        assert isinstance(rec["rationale"], str)
        assert len(rec["rationale"]) > 10

        assert "products" in rec
        assert isinstance(rec["products"], list)
        assert len(rec["products"]) > 0

        # Each recommended product should have the required fields
        for p in rec["products"]:
            assert "id" in p
            assert "name" in p
            assert "price" in p
            assert "sku" in p
