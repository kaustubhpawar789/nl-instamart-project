#!/usr/bin/env python3
"""
tests/test_ui_007_frontend.py — UI-007 MVP Web Interface Tests
Verifies that the shop frontend serves correctly, the product API returns data,
the feedback endpoint logs to PostgreSQL, and the recommendation + feedback
chain works end-to-end.

New in v2 (UI-007 hard reset):
  TestRecommendationEndpoint  — verifies ENG-006 POST /api/recommend integration
  TestRecommendFeedbackChain  — full recommend → feedback → DB verification

Usage:
    source .venv/bin/activate && python -m pytest tests/test_ui_007_frontend.py -v
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
    try:
        r = requests.get(f"{API_BASE}/api/kpis", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        pytest.fail(f"API server not reachable at {API_BASE}: {e}")
    return API_BASE


@pytest.fixture(scope="module")
def test_product():
    """Fetch one valid product from the DB for feedback tests."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        pytest.fail("No products found — run 'python database/seed_mock_data.py' first")
    return {"id": row[0], "name": row[1], "category": row[2]}


@pytest.fixture(scope="module")
def test_user():
    """Fetch one valid user from the DB for feedback tests."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        pytest.fail("No users found — run 'python database/seed_mock_data.py' first")
    return {"id": row[0], "name": row[1]}


@pytest.fixture(scope="module")
def ollama_available(api_url, test_product, test_user):
    """
    Skip Ollama-dependent tests gracefully if Ollama is not running or
    the required model is not loaded. Probes /api/recommend directly.
    """
    try:
        import requests as _req
        r = _req.post(f"{api_url}/api/recommend", json={
            "user_id": test_user["id"],
            "cart_items": [{"product_id": test_product["id"], "quantity": 1}],
        }, timeout=35)
        if r.status_code == 502:
            err = r.json().get("error", "")
            pytest.skip(
                f"Ollama model unavailable (ENG-006 returned 502): {err}. "
                "Run 'ollama pull llama3' and restart the API server to enable these tests."
            )
    except Exception as e:
        pytest.skip(f"Could not reach /api/recommend: {e}")
    return True


class TestProductEndpoint:

    def test_products_endpoint_success(self, api_url):
        """GET /api/products returns 200 with product list."""
        r = requests.get(f"{api_url}/api/products", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "products" in data
        assert isinstance(data["products"], list)
        assert len(data["products"]) > 0
        assert "total" in data

    def test_product_fields(self, api_url):
        """Each product has the required fields."""
        r = requests.get(f"{api_url}/api/products", timeout=10)
        data = r.json()
        for p in data["products"]:
            assert "id" in p and isinstance(p["id"], int)
            assert "name" in p and isinstance(p["name"], str)
            assert "price" in p and isinstance(p["price"], (int, float))
            assert "sku" in p
            assert "category_id" in p and isinstance(p["category_id"], int)
            assert "category_name" in p and isinstance(p["category_name"], str)

    def test_products_includes_all_seeded(self, api_url):
        """Should return all 60 seeded products (all active)."""
        r = requests.get(f"{api_url}/api/products", timeout=10)
        data = r.json()
        assert data["total"] == 60

    def test_shop_page_served(self, api_url):
        """GET /ui/shop.html returns 200 with Instamart HTML including AI panel."""
        r = requests.get(f"{api_url}/ui/shop.html", timeout=10)
        assert r.status_code == 200
        html = r.text
        # Basic HTML structure
        assert "<!DOCTYPE html>" in html
        assert "cart-sidebar" in html
        # Flash recommendation styles are in shop.css
        css_r = requests.get(f"{api_url}/ui/shop.css", timeout=10)
        assert css_r.status_code == 200
        assert ".flash-rec" in css_r.text, "Flash recommendation CSS missing"
        assert ".flash-card" in css_r.text, "Flash card CSS missing"
        assert ".flash-add-btn" in css_r.text, "Flash add button CSS missing"
        # Instamart clone structural elements
        assert "nav-brand" in html, "Instamart navbar brand missing"
        assert "hero-grid" in html, "Hero banners section missing"
        assert "categoryShelves" in html, "Category shelves container missing"
        assert "appFooter" in html, "Swiggy footer missing"

        # Verify flash recommendation classes in shop.js
        js_r = requests.get(f"{api_url}/ui/shop.js", timeout=10)
        assert js_r.status_code == 200
        js_src = js_r.text
        assert "flash-add-btn" in js_src, "Flash Add button class missing from shop.js"
        assert "flash-card" in js_src, "Flash card rendering missing from shop.js"
        assert "/api/recommend" in js_src, "ENG-006 /api/recommend call missing from shop.js"
        assert "/api/feedback" in js_src, "Feedback API call missing from shop.js"


class TestFeedbackEndpoint:

    def test_feedback_missing_user_id(self, api_url, test_product):
        """POST /api/feedback rejects missing user_id."""
        r = requests.post(f"{api_url}/api/feedback", json={
            "product_id": test_product["id"],
            "action": "add_to_cart",
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_feedback_missing_product_id(self, api_url, test_product, test_user):
        """POST /api/feedback rejects missing product_id."""
        r = requests.post(f"{api_url}/api/feedback", json={
            "user_id": test_user["id"],
            "action": "add_to_cart",
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_feedback_invalid_action(self, api_url, test_product, test_user):
        """POST /api/feedback rejects invalid action."""
        r = requests.post(f"{api_url}/api/feedback", json={
            "user_id": test_user["id"],
            "product_id": test_product["id"],
            "action": "invalid_action",
        }, timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_feedback_add_to_cart(self, api_url, test_product, test_user):
        """POST /api/feedback with add_to_cart logs row in feedback table."""
        uid = test_user["id"]
        r = requests.post(f"{api_url}/api/feedback", json={
            "user_id": uid,
            "product_id": test_product["id"],
            "action": "add_to_cart",
        }, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["action"] == "add_to_cart"

        # Verify the row was inserted
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, product_id, rating, comment, feedback_type
            FROM feedback
            WHERE user_id = %s AND product_id = %s AND comment = 'recommendation:add_to_cart'
            ORDER BY id DESC LIMIT 1
        """, (uid, test_product["id"]))
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row is not None, "Feedback row was not inserted"
        assert row[0] == uid
        assert row[1] == test_product["id"]
        assert row[2] == 5
        assert row[3] == "recommendation:add_to_cart"

    def test_feedback_not_interested(self, api_url, test_product, test_user):
        """POST /api/feedback with not_interested logs row in feedback table."""
        uid = test_user["id"]
        r = requests.post(f"{api_url}/api/feedback", json={
            "user_id": uid,
            "product_id": test_product["id"],
            "action": "not_interested",
        }, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["action"] == "not_interested"

        # Verify the row was inserted
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, product_id, rating, comment, feedback_type
            FROM feedback
            WHERE user_id = %s AND product_id = %s AND comment = 'recommendation:not_interested'
            ORDER BY id DESC LIMIT 1
        """, (uid, test_product["id"]))
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row is not None, "Feedback row was not inserted"
        assert row[0] == uid
        assert row[1] == test_product["id"]
        assert row[2] == 1
        assert row[3] == "recommendation:not_interested"


class TestRecommendationEndpoint:
    """
    Tests for ENG-006 POST /api/recommend endpoint called by the UI.
    Verifies the new 1:1 flash recommendation response format.
    """

    def test_recommend_triggered_with_cart(self, api_url, test_product, test_user, ollama_available):
        """
        POST /api/recommend with a valid cart returns 200 and a
        recommendations array with one entry per cart item.
        """
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": test_user["id"],
            "cart_items": [{"product_id": test_product["id"], "quantity": 1}],
        }, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "recommendations" in data, "Response must contain 'recommendations' array"
        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) == 1
        entry = data["recommendations"][0]
        assert "cart_product" in entry, "Missing cart_product"
        assert "flash_recommendation" in entry, "Missing flash_recommendation"
        assert "rationale" in entry, "Missing rationale"
        assert isinstance(entry["rationale"], str) and len(entry["rationale"]) > 5

    def test_recommend_rationale_is_non_empty_string(self, api_url, test_product, test_user, ollama_available):
        """
        The rationale field must be a non-empty string for each recommendation.
        """
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": test_user["id"],
            "cart_items": [{"product_id": test_product["id"], "quantity": 2}],
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        for entry in data.get("recommendations", []):
            rationale = entry.get("rationale", "")
            assert isinstance(rationale, str), "rationale must be a string"
            assert len(rationale.strip()) > 0, "rationale must not be empty"

    def test_recommend_products_have_required_fields(self, api_url, test_product, test_user, ollama_available):
        """
        Each flash_recommendation must have id, name, and price.
        """
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": test_user["id"],
            "cart_items": [{"product_id": test_product["id"], "quantity": 1}],
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        for entry in data.get("recommendations", []):
            fr = entry.get("flash_recommendation", {})
            assert "id" in fr and isinstance(fr["id"], int), "flash_recommendation must have integer id"
            assert "name" in fr and isinstance(fr["name"], str), "flash_recommendation must have string name"
            assert "price" in fr, "flash_recommendation must have price"


class TestRecommendFeedbackChain:
    """
    Full end-to-end chain: POST /api/recommend → pick first product →
    POST /api/feedback add_to_cart → verify DB row.
    Mirrors exactly what the UI does when the user clicks 'Add to Cart'
    on a recommended product.
    """

    def test_recommend_then_feedback_add_to_cart_logs_to_db(self, api_url, test_product, test_user, ollama_available):
        """
        Full UI chain: recommend endpoint returns flash recommendations, user clicks
        '+ Add' on a flash product, feedback is logged to DB.
        """
        uid = test_user["id"]

        # Step 1: Call /api/recommend
        rec_res = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid,
            "cart_items": [{"product_id": test_product["id"], "quantity": 1}],
        }, timeout=30)
        assert rec_res.status_code == 200, f"Recommend failed: {rec_res.text}"
        rec_data = rec_res.json()
        recs = rec_data.get("recommendations", [])
        assert len(recs) > 0

        # Step 2: Pick the first flash recommended product
        fr = recs[0].get("flash_recommendation", {})
        if fr.get("id"):
            rec_product_id = fr["id"]
        else:
            rec_product_id = test_product["id"]

        # Step 3: Click 'Add to Cart' — POST /api/feedback (simulates button click)
        fb_res = requests.post(f"{api_url}/api/feedback", json={
            "user_id": uid,
            "product_id": rec_product_id,
            "action": "add_to_cart",
        }, timeout=10)
        assert fb_res.status_code == 200
        fb_data = fb_res.json()
        assert fb_data["ok"] is True
        assert fb_data["action"] == "add_to_cart"

        # Step 4: Verify the feedback row exists in PostgreSQL
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, product_id, rating, comment
            FROM feedback
            WHERE user_id = %s AND product_id = %s AND comment = 'recommendation:add_to_cart'
            ORDER BY id DESC LIMIT 1
        """, (uid, rec_product_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row is not None, (
            f"Feedback row not found in DB for user {uid}, product {rec_product_id}. "
            "The UI feedback button is not writing to the database."
        )
        assert row[0] == uid
        assert row[1] == rec_product_id
        assert row[2] == 5  # add_to_cart = rating 5
        assert row[3] == "recommendation:add_to_cart"


@pytest.fixture
def cart_user(api_url):
    """Yield a fresh user with an empty cart for each cart test."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    user = {"id": row[0], "name": row[1]}
    requests.delete(f"{api_url}/api/cart?user_id={user['id']}&all=true", timeout=10)
    return user


class TestCartPersistence:
    """Tests for per-user cart persistence via GET/POST/DELETE /api/cart."""

    def test_get_cart_empty(self, api_url, cart_user):
        """GET /api/cart for a fresh user returns empty items list."""
        uid = cart_user["id"]
        r = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == uid
        assert data["items"] == []
        assert data["total"] == 0

    def test_add_to_cart_persists(self, api_url, cart_user, test_product):
        """POST /api/cart adds an item, GET verifies it in DB."""
        pid = test_product["id"]
        uid = cart_user["id"]

        r = requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": pid, "quantity": 1,
        }, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True

        r2 = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) == 1
        assert items[0]["product_id"] == pid
        assert items[0]["quantity"] == 1

    def test_add_multiple_products(self, api_url, cart_user):
        """POST two different products, GET returns both."""
        uid = cart_user["id"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE is_active = TRUE LIMIT 2")
        pids = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        if len(pids) < 2:
            pytest.fail("Need at least 2 products")

        for pid in pids:
            r = requests.post(f"{api_url}/api/cart", json={
                "user_id": uid, "product_id": pid, "quantity": 2,
            }, timeout=10)
            assert r.status_code == 200

        r2 = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) == 2
        assert items[0]["quantity"] == 2
        assert items[1]["quantity"] == 2

    def test_remove_from_cart_deletes(self, api_url, cart_user, test_product):
        """POST then DELETE a single item, GET returns empty."""
        pid = test_product["id"]
        uid = cart_user["id"]

        requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": pid, "quantity": 1,
        }, timeout=10)

        r = requests.delete(f"{api_url}/api/cart?user_id={uid}&product_id={pid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["deleted"] >= 1

        r2 = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r2.status_code == 200
        assert r2.json()["total"] == 0

    def test_clear_cart_truncates(self, api_url, cart_user):
        """POST two items then DELETE all=true, GET returns empty."""
        uid = cart_user["id"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE is_active = TRUE LIMIT 2")
        pids = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()

        for pid in pids:
            requests.post(f"{api_url}/api/cart", json={
                "user_id": uid, "product_id": pid, "quantity": 1,
            }, timeout=10)

        r = requests.delete(f"{api_url}/api/cart?user_id={uid}&all=true", timeout=10)
        assert r.status_code == 200

        r2 = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r2.status_code == 200
        assert r2.json()["total"] == 0

    def test_quantity_upsert(self, api_url, cart_user, test_product):
        """POST same product twice with different qty, DB has latest qty."""
        pid = test_product["id"]
        uid = cart_user["id"]

        requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": pid, "quantity": 1,
        }, timeout=10)
        requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": pid, "quantity": 5,
        }, timeout=10)

        r = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        cart_item = next((i for i in items if i["product_id"] == pid), None)
        assert cart_item is not None, "Product not found in cart after upsert"
        assert cart_item["quantity"] == 5

    def test_cart_requires_user_id(self, api_url):
        """GET /api/cart without user_id returns 400."""
        r = requests.get(f"{api_url}/api/cart", timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_cart_rejects_invalid_user_id(self, api_url):
        """GET /api/cart with non-int user_id returns 400."""
        r = requests.get(f"{api_url}/api/cart?user_id=abc", timeout=10)
        assert r.status_code == 400
        data = r.json()
        assert "error" in data


class TestContinuousRecommendation:
    """
    Tests that every cart mutation triggers a fresh AI recommendation
    (aggregate state analysis) and the recommendation adapts as the
    cart content changes.
    """

    def _multi_category_cart(self, api_url, cart_user):
        """Build a cart with 3 different categories by picking products."""
        uid = cart_user["id"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (c.name) p.id, c.name AS cat
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.is_active = TRUE
            LIMIT 3
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if len(rows) < 3:
            pytest.fail("Need at least 3 products across distinct categories")
        items = []
        cats = []
        for row in rows:
            pid, cat = row[0], row[1]
            requests.post(f"{api_url}/api/cart", json={
                "user_id": uid, "product_id": pid, "quantity": 1,
            }, timeout=10)
            items.append({"product_id": pid, "quantity": 1})
            cats.append(cat)
        return uid, items, cats

    def test_add_triggers_recommendation(self, api_url, cart_user, ollama_available):
        """Adding a product to cart then calling recommend returns 200."""
        uid = cart_user["id"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE is_active = TRUE LIMIT 1")
        pid = cur.fetchone()[0]
        cur.close()
        conn.close()

        requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": pid, "quantity": 1,
        }, timeout=10)

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": [{"product_id": pid, "quantity": 1}],
        }, timeout=30)
        assert r.status_code == 200, f"Recommend after add failed: {r.text}"
        data = r.json()
        recs = data.get("recommendations", [])
        assert len(recs) == 1
        assert "flash_recommendation" in recs[0]
        assert "rationale" in recs[0]

    def test_remove_updates_recommendation(self, api_url, cart_user, ollama_available):
        """Recommendation still works after removing one of multiple products."""
        uid, items, cats = self._multi_category_cart(api_url, cart_user)
        first_pid = items[0]["product_id"]
        requests.delete(f"{api_url}/api/cart?user_id={uid}&product_id={first_pid}", timeout=10)
        remaining = items[1:]

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": remaining,
        }, timeout=30)
        assert r.status_code == 200, f"Recommend after remove failed: {r.text}"
        data = r.json()
        recs = data.get("recommendations", [])
        assert len(recs) == len(remaining)
        for entry in recs:
            assert "flash_recommendation" in entry
            assert "rationale" in entry

    def test_aggregate_cart_analyzed(self, api_url, cart_user, ollama_available):
        """
        With multiple categories in cart, each gets its own flash recommendation
        from an adjacent category.
        """
        uid, items, cats = self._multi_category_cart(api_url, cart_user)

        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": items,
        }, timeout=30)
        assert r.status_code == 200, f"Recommend failed: {r.text}"
        data = r.json()
        recs = data.get("recommendations", [])
        assert len(recs) == len(items)
        for entry in recs:
            cp = entry.get("cart_product", {})
            assert "name" in cp
            fr = entry.get("flash_recommendation", {})
            assert "name" in fr
            # Flash product must differ from cart product
            assert fr["id"] != cp["id"], (
                f"Flash product {fr['name']} is same as cart product {cp['name']}"
            )


class TestFlashAddPersistence:
    """
    Tests that items added via flash recommendation '+ Add' button
    persist in PostgreSQL and survive a cart reload.
    """

    def test_flash_add_persists_in_db(self, api_url, test_product, test_user, ollama_available):
        """
        Simulate the flash '+ Add' flow:
        1. Call /api/recommend to get a flash recommendation
        2. POST /api/cart (same as _syncCartToDb) to add the flash product
        3. GET /api/cart to verify it persisted
        4. Verify the next recommendation doesn't contain the added product
        """
        uid = test_user["id"]

        # Step 1: Get recommendation
        r = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid,
            "cart_items": [{"product_id": test_product["id"], "quantity": 1}],
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        recs = data.get("recommendations", [])
        assert len(recs) > 0
        fr = recs[0].get("flash_recommendation", {})
        assert fr.get("id"), "No flash product returned"
        flash_id = fr["id"]

        # Step 2: POST /api/cart (simulates _syncCartToDb after feedback add_to_cart)
        r2 = requests.post(f"{api_url}/api/cart", json={
            "user_id": uid, "product_id": flash_id, "quantity": 1,
        }, timeout=10)
        assert r2.status_code == 200, f"Cart POST failed: {r2.text}"
        assert r2.json().get("ok") is True

        # Step 3: GET /api/cart — verify the flash product is in the cart
        r3 = requests.get(f"{api_url}/api/cart?user_id={uid}", timeout=10)
        assert r3.status_code == 200
        cart_data = r3.json()
        items = cart_data.get("items", [])
        item_ids = {i["product_id"] for i in items}
        assert flash_id in item_ids, (
            f"Flash product {flash_id} not found in cart after POST. "
            f"Cart items: {item_ids}"
        )

        # Step 4: Verify the guardrail prevents recommending the same product again
        updated_cart = [{"product_id": test_product["id"], "quantity": 1},
                        {"product_id": flash_id, "quantity": 1}]
        r4 = requests.post(f"{api_url}/api/recommend", json={
            "user_id": uid, "cart_items": updated_cart,
        }, timeout=30)
        assert r4.status_code == 200
        data4 = r4.json()
        for entry in data4.get("recommendations", []):
            fr2 = entry.get("flash_recommendation", {})
            assert fr2.get("id") != flash_id, (
                f"Guardrail failed: flash product {flash_id} was just added "
                f"to cart but appeared in recommendation again"
            )
