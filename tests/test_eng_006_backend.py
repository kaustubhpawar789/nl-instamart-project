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
        """Happy path: returns one flash recommendation per cart item."""
        cart = [{"product_id": p["product_id"], "quantity": 1} for p in snack_products]
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": 1, "cart_items": cart,
        }, timeout=90)

        if r.status_code == 502:
            data = r.json()
            if "Ollama" in data.get("error", ""):
                pytest.skip("Ollama is not running")
            pytest.fail(f"Unexpected 502: {data}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()

        # 1:1 mapping — one recommendation per cart item
        recs = data.get("recommendations", [])
        assert len(recs) == len(snack_products), (
            f"Expected {len(snack_products)} recommendations, "
            f"got {len(recs)}"
        )

        for entry in recs:
            assert "cart_product" in entry, "Missing cart_product"
            cp = entry["cart_product"]
            assert "id" in cp and "name" in cp and "category_name" in cp

            assert "flash_recommendation" in entry, "Missing flash_recommendation"
            fr = entry["flash_recommendation"]
            assert "id" in fr and "name" in fr and "price" in fr

            assert "rationale" in entry
            assert isinstance(entry["rationale"], str)
            assert len(entry["rationale"]) > 5

            # Guardrail: flash product must not be the same as cart product
            assert fr["id"] != cp["id"], (
                f"Flash product {fr['id']} is same as cart product {cp['id']}"
            )

        # Collect unique cart product IDs — must match snack_products
        cart_ids = sorted(cp["cart_product"]["id"] for cp in recs)
        expected_ids = sorted(p["product_id"] for p in snack_products)
        assert cart_ids == expected_ids, (
            f"Cart product IDs mismatch: {cart_ids} vs {expected_ids}"
        )

    def test_recommend_with_db_cart(self, api_url, snack_products):
        """Recommend returns one flash per cart item saved to DB."""
        from scripts.auto_cleanup import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users LIMIT 1")
        uid = cur.fetchone()[0]
        cur.close()
        conn.close()

        cart = [{"product_id": p["product_id"], "quantity": 2} for p in snack_products]

        for item in cart:
            r = requests.post(f"{api_url}/api/cart", json={
                "user_id": uid, "product_id": item["product_id"], "quantity": item["quantity"],
            }, timeout=10)
            assert r.status_code == 200

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": cart,
        }, timeout=90)

        if r.status_code == 502:
            data = r.json()
            if "Ollama" in data.get("error", ""):
                pytest.skip("Ollama is not running")
            pytest.fail(f"Unexpected 502: {data}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        recs = data.get("recommendations", [])
        assert len(recs) == len(snack_products)
        for entry in recs:
            assert "cart_product" in entry
            assert "flash_recommendation" in entry
            assert "rationale" in entry and len(entry["rationale"]) > 5

    def test_recommend_handles_ollama_not_running_gracefully(self, api_url):
        """OllamaClient detects unreachable server."""
        import scripts.ollama_client as oc
        client = oc.OllamaClient(base_url="http://localhost:11499", model="llama3:latest")
        assert client.is_available() is False


class TestGuardrail:
    """Tests for the product-level duplicate guardrail in ENG-006."""

    def test_standalone_filters_duplicates(self):
        """
        filter_cart_duplicates removes recommended products whose IDs match
        cart items. Pure unit test — no server needed.
        """
        from scripts.api_server import filter_cart_duplicates

        rec_products = [
            {"id": 1, "name": "Product A", "price": 100.0},
            {"id": 2, "name": "Product B", "price": 200.0},
            {"id": 3, "name": "Product C", "price": 300.0},
        ]
        cart_items = [
            {"product_id": 2, "quantity": 1},
            {"product_id": 5, "quantity": 2},
        ]

        result = filter_cart_duplicates(rec_products, cart_items)
        result_ids = {p["id"] for p in result}
        assert 2 not in result_ids, (
            "Product B (id=2) should have been filtered out "
            "because it matches cart item product_id=2"
        )
        assert 1 in result_ids
        assert 3 in result_ids
        assert len(result) == 2

    def test_standalone_all_duplicates_triggers_requery(self):
        """
        When ALL recommended products are in the cart, filter_cart_duplicates
        re-queries the DB excluding cart IDs. Verifies the fallback returns
        different products.
        """
        from scripts.api_server import filter_cart_duplicates
        from scripts.auto_cleanup import get_connection

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.price, p.sku, p.description, p.image_url,
                   c.name AS category_name
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE c.name = 'Snacks' AND p.is_active = TRUE
            LIMIT 4
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) < 2:
            pytest.fail("Need at least 2 Snacks products for this test")

        all_snacks = [
            {"id": r[0], "name": r[1], "price": float(r[2]), "sku": r[3],
             "description": r[4], "image_url": r[5]}
            for r in rows
        ]
        cart_ids = [r[0] for r in rows]  # ALL snack products in cart

        result = filter_cart_duplicates(
            all_snacks,
            [{"product_id": pid, "quantity": 1} for pid in cart_ids],
            category_name="Snacks",
        )

        assert len(result) > 0, (
            "Guardrail should have re-queried and returned "
            "different products when all originals were duplicates"
        )
        result_ids = {p["id"] for p in result}
        for pid in cart_ids:
            assert pid not in result_ids, (
                f"Guardrail re-query returned product {pid} "
                f"which was in the cart"
            )

    def test_integration_no_duplicate_in_response(self, api_url, snack_products):
        """
        Integration test: add one Snacks product to the cart via /api/cart,
        then call /api/recommend with that same product_id in cart_items.
        The guardrail must ensure the recommended products do not include
        any product_id from the cart.
        """
        from scripts.auto_cleanup import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users LIMIT 1")
        uid = cur.fetchone()[0]
        cur.close()
        conn.close()

        cart = [{"product_id": p["product_id"], "quantity": 2} for p in snack_products]
        cart_ids = {p["product_id"] for p in snack_products}

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": cart,
        }, timeout=90)

        if r.status_code == 502:
            data = r.json()
            if "Ollama" in data.get("error", ""):
                pytest.skip("Ollama is not running")
            pytest.fail(f"Unexpected 502: {data}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        recs = data.get("recommendations", [])

        for entry in recs:
            fr = entry.get("flash_recommendation", {})
            assert fr.get("id") not in cart_ids, (
                f"Guardrail failed: flash product {fr.get('id')} "
                f"is in the cart"
            )


    def test_brand_guardrail_blocks_same_brand(self, api_url):
        """
        If cart has 'Harpic Power Plus 500ml', the brand guardrail prevents
        recommending any other 'Harpic' product (e.g. 'Harpic Drain Master 500ml').
        Verifies by extracting the first-word brand token from each cart product
        and ensuring no flash product shares that token.
        """
        from scripts.auto_cleanup import get_connection
        conn = get_connection()
        cur = conn.cursor()
        # Fetch two Harpic products (same brand, different IDs)
        cur.execute("""
            SELECT id, name FROM products
            WHERE name ILIKE 'harpic%' AND is_active = TRUE
            LIMIT 2
        """)
        harpics = cur.fetchall()
        if len(harpics) < 2:
            cur.execute("""
                SELECT id, name FROM products
                WHERE name ILIKE 'amul%' AND is_active = TRUE
                LIMIT 2
            """)
            harpics = cur.fetchall()
        cur.close()
        conn.close()
        if len(harpics) < 2:
            pytest.fail("Need at least 2 products sharing a brand name")

        # Put ONE Harpic in the cart
        cart = [{"product_id": harpics[0][0], "quantity": 1}]
        cart_brand = harpics[0][1].split()[0].lower()

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": 256, "cart_items": cart,
        }, timeout=30)

        if r.status_code == 502:
            data = r.json()
            if "Ollama" in data.get("error", ""):
                pytest.skip("Ollama is not running")
            pytest.fail(f"Unexpected 502: {data}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        recs = data.get("recommendations", [])

        for entry in recs:
            fr = entry.get("flash_recommendation", {})
            flash_brand = fr.get("name", "").split()[0].lower() if fr.get("name") else ""
            assert flash_brand != cart_brand, (
                f"Brand guardrail failed: cart has '{harpics[0][1]}' (brand={cart_brand}), "
                f"but flash product '{fr.get('name')}' also has brand '{flash_brand}'"
            )


class TestPerProductRecommend:
    """Tests for POST /api/per-product-recommend endpoint."""

    def test_per_product_returns_valid_response(self, api_url):
        """Valid cart_item returns 200 with cart_product + recommendation."""
        from scripts.auto_cleanup import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE is_active = TRUE LIMIT 1")
        pid = cur.fetchone()[0]
        cur.close()
        conn.close()

        r = requests.post(f"{api_url}/api/per-product-recommend", json={
            "user_id": 256,
            "cart_item": {"product_id": pid, "quantity": 1},
        }, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()

        assert "cart_product" in data, "Missing cart_product"
        cp = data["cart_product"]
        assert cp["id"] == pid
        assert "name" in cp
        assert "category_name" in cp

        assert "recommendation" in data, "Missing recommendation"
        rec = data["recommendation"]
        assert "adjacent_category" in rec
        assert "rationale" in rec
        assert "products" in rec
        assert len(rec["products"]) > 0, "Should recommend at least 1 product"

        # The recommended product must be different from the cart product
        rec_ids = {p["id"] for p in rec["products"]}
        assert pid not in rec_ids, (
            f"Per-product rec returned the same product {pid}"
        )

    def test_per_product_rejects_missing_user_id(self, api_url):
        """Missing user_id returns 400."""
        r = requests.post(f"{api_url}/api/per-product-recommend", json={
            "cart_item": {"product_id": 1, "quantity": 1},
        }, timeout=10)
        assert r.status_code == 400

    def test_per_product_rejects_missing_product_id(self, api_url):
        """Missing product_id returns 400."""
        r = requests.post(f"{api_url}/api/per-product-recommend", json={
            "user_id": 256,
            "cart_item": {"quantity": 1},
        }, timeout=10)
        assert r.status_code == 400

    def test_per_product_different_category(self, api_url):
        """
        The recommended product should come from a different category than
        the cart product (proves the per-product adjacency logic works).
        """
        from scripts.auto_cleanup import get_connection
        conn = get_connection()
        cur = conn.cursor()
        # Pick a Baby Products item for a clear adjacent distinction
        cur.execute("""
            SELECT p.id, c.name FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE c.name = 'Baby Products' AND p.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            pytest.fail("No Baby Products found")
        pid, pcat = row

        r = requests.post(f"{api_url}/api/per-product-recommend", json={
            "user_id": 256,
            "cart_item": {"product_id": pid, "quantity": 1},
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        rec_cat = data["recommendation"]["adjacent_category"]
        assert rec_cat != pcat, (
            f"Per-product rec returned same category '{pcat}' — "
            f"should be an adjacent category"
        )
