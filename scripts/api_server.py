#!/usr/bin/env python3
"""
Discovery Engine BI Dashboard — API Server v2.0
Single-file Python server (stdlib only, no external dependencies).
Serves all endpoints required by the UI dashboard app.js.
Persistence via JSON files in database/.
"""

import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATABASE = os.path.join(ROOT, "database")

from scripts.ollama_client import get_client, OLLAMA_BASE_URL, OLLAMA_MODEL
from scripts import auto_cleanup

_ollama_client = None

SCRAPE_SIM_DELAY = 4


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _read_json(filepath, default=None):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, filepath)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _extract_brand(name):
    """Return the first word of a product name as a brand hint (lowercased)."""
    words = name.split()
    return words[0].lower() if words else ""


def filter_cart_duplicates(rec_products, cart_items, category_name=None):
    """
    Remove any recommended product whose ID appears in the user's cart.
    If all products are filtered out, re-query the same category excluding
    cart product IDs. Returns the filtered (or re-queried) product list.
    """
    cart_ids = set()
    for item in cart_items:
        if isinstance(item, dict):
            pid = item.get("product_id")
            if pid is not None:
                cart_ids.add(pid)

    filtered = [p for p in rec_products if p["id"] not in cart_ids]
    if filtered or not cart_ids:
        return filtered

    # All were duplicates — re-query excluding cart items
    if not category_name:
        return []

    from scripts.auto_cleanup import get_connection
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join("%s" for _ in cart_ids)
    cur.execute(f"""
        SELECT p.id, p.name, p.price, p.sku, p.description, p.image_url
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE c.name = %s AND p.is_active = TRUE
          AND p.id NOT IN ({placeholders})
        ORDER BY stock_quantity DESC
        LIMIT 4
    """, [category_name] + list(cart_ids))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "price": float(r[2]), "sku": r[3],
         "description": r[4], "image_url": r[5]}
        for r in rows
    ]


class APIHandler(SimpleHTTPRequestHandler):
    # ── Routing ────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        auto_cleanup.set_last_request_time()

        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

        routes = {
            "/api/insights":         self._get_insights,
            "/api/kpis":             self._get_kpis,
            "/api/records":          self._get_records,
            "/api/charts/data":      self._get_charts_data,
            "/api/charts/configs":   self._get_charts_configs,
            "/api/scrape/status":    self._get_scrape_status,
            "/api/survey/responses": self._get_survey_responses,
            "/api/matrix":           self._get_matrix,
            "/api/products":         self._get_products,
            "/api/cart":             self._get_cart,
            "/api/users":            self._get_users,
        }

        handler = routes.get(path)
        if handler:
            handler(params)
        elif path.startswith("/api/"):
            self.send_error(404)
        elif path.startswith("/ui/"):
            super().do_GET()
        elif path == "/" or path == "":
            self.path = "/ui/index.html"
            super().do_GET()
        else:
            self.path = "/ui" + path
            super().do_GET()

    def send_response(self, code, message=None):
        super().send_response(code, message)
        # Disable caching for all static UI assets so CSS/JS changes are immediate
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")

    def do_POST(self):
        auto_cleanup.set_last_request_time()

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/charts/configs":
            self._post_charts_config()
        elif path == "/api/scrape":
            self._post_scrape()
        elif path == "/api/survey/submit":
            self._post_survey_submit()
        elif path == "/api/search":
            self._post_search()
        elif path == "/api/db/clear":
            self._post_db_clear()
        elif path == "/api/recommend":
            self._post_recommend()
        elif path == "/api/per-product-recommend":
            self._post_per_product_recommend()
        elif path == "/api/feedback":
            self._post_feedback()
        elif path == "/api/cart":
            self._post_cart()
        elif path == "/api/seed":
            self._post_seed()
        else:
            self.send_error(404)

    def do_DELETE(self):
        auto_cleanup.set_last_request_time()

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/cart":
            self._delete_cart(parsed)
        elif path.startswith("/api/charts/configs/"):
            try:
                chart_id = int(path.split("/")[-1])
            except (ValueError, IndexError):
                self.send_error(400, "Invalid chart id")
                return
            self._delete_charts_config(chart_id)
        else:
            self.send_error(404)

    # ── Helpers ────────────────────────────────────────────────────────────

    def log_message(self, fmt, *args):
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _parse_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # ── GET /api/insights ─────────────────────────────────────────────────

    def _get_insights(self, params):
        data = _read_json(os.path.join(DATABASE, "ai_insights.json"))
        if data is None or not isinstance(data, dict):
            data = {
                "themes": [],
                "insights": [],
                "sentiment": {"positive": {"count": 0, "percentage": 0},
                              "neutral":  {"count": 0, "percentage": 0},
                              "negative": {"count": 0, "percentage": 0}},
                "categories": [],
            }
        self._json(data)

    # ── GET /api/kpis ─────────────────────────────────────────────────────

    def _get_kpis(self, params):
        live = _read_json(os.path.join(DATABASE, "live_scraped_data.json"), [])
        if not isinstance(live, list):
            live = []
        insights = _read_json(os.path.join(DATABASE, "ai_insights.json"), {})
        if not isinstance(insights, dict):
            insights = {"themes": [], "insights": [], "categories": []}
        survey = _read_json(os.path.join(DATABASE, "survey_responses.json"), [])
        if not isinstance(survey, list):
            survey = []
        status = _read_json(os.path.join(DATABASE, "scrape_status.json"),
                            {"running": False, "added": 0, "error": None})
        if not isinstance(status, dict):
            status = {"running": False, "added": 0, "error": None}

        total_reviews = len(live)
        unique_sources = list({r.get("source", "unknown") for r in live})

        avg_rating = 0.0
        if live:
            ratings = [r.get("rating", 0) for r in live if r.get("rating")]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        themes = insights.get("themes", [])
        cats = insights.get("categories", [])

        last_updated = status.get("finished_at") or status.get("started_at")
        if not last_updated:
            last_updated = _now_iso()

        self._json({
            "ai_analyzed":       total_reviews,
            "themes":            len(themes),
            "key_insights":      len(insights.get("insights", [])),
            "categories":        len(cats),
            "data_sources":      len(unique_sources),
            "survey_responses":  len(survey),
            "scrape_frequency":  "Manual",
            "avg_rating":        avg_rating,
            "last_updated":      last_updated,
        })

    # ── GET /api/products ────────────────────────────────────────────────

    def _get_products(self, params):
        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()
            # Debug
            cur.execute("SELECT COUNT(*) FROM products")
            total_debug = cur.fetchone()
            import sys; print(f"[DEBUG] Total products in DB: {total_debug}", file=sys.stderr)
            cur.execute("SELECT COUNT(*) FROM categories")
            cat_debug = cur.fetchone()
            print(f"[DEBUG] Total categories in DB: {cat_debug}", file=sys.stderr)
            cur.execute("""
                SELECT p.id, p.name, p.price, p.sku, p.description, p.image_url,
                       c.id AS category_id, c.name AS category_name
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE p.is_active = TRUE
                ORDER BY c.name, p.name
            """)
            rows = cur.fetchall()
            print(f"[DEBUG] Products query returned {len(rows)} rows", file=sys.stderr)
            cur.close()
            conn.close()
            products = [
                {"id": r[0], "name": r[1], "price": float(r[2]), "sku": r[3],
                 "description": r[4], "image_url": r[5],
                 "category_id": r[6], "category_name": r[7]}
                for r in rows
            ]
            self._json({"products": products, "total": len(products)})
        except Exception as e:
            import sys; print(f"[DEBUG] _get_products error: {e}", file=sys.stderr)
            self._json({"error": str(e)}, 500)

    # ── GET /api/records ──────────────────────────────────────────────────

    def _get_records(self, params):
        data = _read_json(os.path.join(DATABASE, "live_scraped_data.json"), [])

        # Filters
        source = params.get("source")
        intent = params.get("intent")
        category = params.get("category")
        search = params.get("search", "").lower().strip()

        if source:
            data = [r for r in data if r.get("source") == source]
        if intent:
            data = [r for r in data if r.get("intent") == intent]
        if category:
            data = [r for r in data if category in (r.get("categories") or [])]
        if search:
            data = [r for r in data if search in
                    f"{r.get('id','')} {r.get('source','')} {r.get('user','')} "
                    f"{r.get('location','')} {r.get('text','')} "
                    f"{r.get('intent','')} {' '.join(r.get('categories', []))}".lower()]

        total = len(data)

        # Sort
        sort_col = params.get("sort", "date")
        sort_dir = params.get("dir", "desc")
        reverse = sort_dir == "desc"

        def sort_key(r):
            if sort_col == "rating":
                return r.get("rating", 0)
            if sort_col == "date":
                return r.get("date", "")
            return str(r.get(sort_col, "")).lower()

        data.sort(key=sort_key, reverse=reverse)

        # Paginate
        try:
            offset = int(params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(params.get("limit", 50))
        except (ValueError, TypeError):
            limit = 50

        page = data[offset: offset + limit]

        self._json({"records": page, "total": total, "offset": offset})

    # ── GET /api/charts/data ──────────────────────────────────────────────

    def _get_charts_data(self, params):
        data = _read_json(os.path.join(DATABASE, "live_scraped_data.json"), [])

        # WHERE filters
        source = params.get("source")
        intent = params.get("intent")
        category = params.get("category")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if source:
            data = [r for r in data if r.get("source") == source]
        if intent:
            data = [r for r in data if r.get("intent") == intent]
        if category:
            data = [r for r in data if category in (r.get("categories") or [])]
        if date_from:
            data = [r for r in data if r.get("date", "") >= date_from]
        if date_to:
            data = [r for r in data if r.get("date", "") <= date_to]

        x = params.get("x", "source")
        y = params.get("y", "count")

        # GROUP BY
        groups = {}
        for r in data:
            if x == "date":
                key = r.get("date", "unknown")[:7]
            elif x == "rating":
                key = str(r.get("rating", 0))
            elif x == "platform":
                key = r.get("platform", "unknown")
            elif x == "category":
                cats = r.get("categories") or ["uncategorized"]
                for c in cats:
                    if c not in groups:
                        groups[c] = []
                    groups[c].append(r)
                continue
            else:
                key = r.get(x, "unknown")

            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        # Aggregate Y
        labels = sorted(groups.keys())
        values = []

        for label in labels:
            recs = groups[label]
            if y == "avg_rating":
                ratings = [rr.get("rating", 0) for rr in recs]
                values.append(round(sum(ratings) / len(ratings), 2) if ratings else 0)
            elif y == "sum_rating":
                values.append(sum(rr.get("rating", 0) for rr in recs))
            else:
                values.append(len(recs))

        self._json({"labels": labels, "values": values})

    # ── GET /api/charts/configs ───────────────────────────────────────────

    def _get_charts_configs(self, params):
        configs = _read_json(os.path.join(DATABASE, "chart_configs.json"), [])
        self._json(configs)

    # ── GET /api/scrape/status ────────────────────────────────────────────

    def _get_scrape_status(self, params):
        status = _read_json(os.path.join(DATABASE, "scrape_status.json"), {
            "running": False, "added": 0, "error": None,
        })
        if not isinstance(status, dict):
            status = {"running": False, "added": 0, "error": None}
        self._json(status)

    # ── GET /api/survey/responses ─────────────────────────────────────────

    def _get_survey_responses(self, params):
        responses = _read_json(os.path.join(DATABASE, "survey_responses.json"), [])
        limit = params.get("limit")
        if limit:
            try:
                responses = responses[:int(limit)]
            except (ValueError, TypeError):
                pass
        self._json({"responses": responses, "total": len(
            _read_json(os.path.join(DATABASE, "survey_responses.json"), [])
        )})

    # ── POST /api/charts/configs ──────────────────────────────────────────

    def _post_charts_config(self):
        body = self._parse_body()
        name = (body.get("name") or "").strip()
        if not name:
            self._json({"error": "Chart name is required"}, 400)
            return

        filepath = os.path.join(DATABASE, "chart_configs.json")
        configs = _read_json(filepath, [])

        if any(c.get("name") == name for c in configs):
            self._json({"error": f'A chart named "{name}" already exists'}, 409)
            return

        next_id = max((c.get("id", 0) for c in configs), default=0) + 1
        config = {
            "id":         next_id,
            "name":       name,
            "chart_type": body.get("chart_type", "bar"),
            "x_axis":     body.get("x_axis", "source"),
            "y_axis":     body.get("y_axis", "count"),
            "filters":    body.get("filters", {}),
            "created_at": _now_iso(),
        }
        configs.append(config)
        _write_json(filepath, configs)
        self._json(config)

    # ── POST /api/scrape ─────────────────────────────────────────────────

    def _post_scrape(self):
        filepath = os.path.join(DATABASE, "scrape_status.json")
        status = _read_json(filepath, {
            "running": False, "added": 0, "error": None,
        })
        if not isinstance(status, dict):
            status = {"running": False, "added": 0, "error": None}

        if status.get("running"):
            self._json({"error": "Scrape already in progress"}, 409)
            return

        status = {
            "running":     True,
            "added":       0,
            "started_at":  _now_iso(),
            "finished_at": None,
            "error":       None,
        }
        _write_json(filepath, status)

        def run():
            added = 0
            try:
                import sys as _sys
                _sys.path.insert(0, ROOT)

                from scripts.scrapers import ALL_SCRAPERS
                live_path = os.path.join(DATABASE, "live_scraped_data.json")
                existing = _read_json(live_path, [])
                if not isinstance(existing, list):
                    existing = []
                existing_ids = {r.get("id") for r in existing} if existing else set()

                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

                all_new = []
                for name, scraper_cls in ALL_SCRAPERS.items():
                    try:
                        print(f"[API Scrape] Scraping {name}...", flush=True)
                        scraper = scraper_cls()
                        with ThreadPoolExecutor(max_workers=1) as pool:
                            fut = pool.submit(scraper.scrape)
                            reviews = fut.result(timeout=30)
                        print(f"[API Scrape]   {name}: {len(reviews)} reviews", flush=True)
                        all_new.extend(reviews)
                    except FutureTimeout:
                        print(f"[API Scrape]   {name}: timed out after 30s", flush=True)
                    except Exception as e:
                        print(f"[API Scrape]   {name}: skipped ({e})", flush=True)

                # Deduplicate by ID and text
                seen_ids = set(existing_ids)
                seen_texts = set()
                fresh = []
                for r in all_new:
                    tid = r.get("id", "")
                    tkey = (r.get("text") or "")[:100]
                    if tid not in seen_ids and tkey not in seen_texts:
                        r.setdefault("sentiment", "neutral")
                        r.setdefault("themes", [])
                        fresh.append(r)
                        seen_ids.add(tid)
                        seen_texts.add(tkey)

                print(f"[API Scrape] After dedup: {len(fresh)} new reviews")

                if not fresh:
                    print("[API Scrape] No new reviews found — skipping pipeline")
                    added = 0
                else:
                    # Merge into live_scraped_data.json
                    merged = existing + fresh
                    _write_json(live_path, merged)
                    added = len(fresh)
                    print(f"[API Scrape] Saved {len(merged)} total reviews to live_scraped_data.json")

                    # Sync cleaned_feedback.json
                    try:
                        cleaned_path = os.path.join(DATABASE, "cleaned_feedback.json")
                        cfb = _read_json(cleaned_path, [])
                        if not isinstance(cfb, list) or not cfb:
                            _write_json(cleaned_path, merged)
                        else:
                            cfb_ids = {r.get("id") for r in cfb}
                            to_add = [r for r in fresh if r["id"] not in cfb_ids]
                            if to_add:
                                cfb.extend(to_add)
                                _write_json(cleaned_path, cfb)
                        print(f"[API Scrape] Synced to cleaned_feedback.json")
                    except Exception as e:
                        print(f"[API Scrape] cleaned_feedback.json sync skipped: {e}")

                    # Bulk insert into PostgreSQL reviews table
                    try:
                        from psycopg2.extras import execute_values
                        from scripts.auto_cleanup import get_connection
                        conn = get_connection(autocommit=True)
                        cur = conn.cursor()
                        cur.execute("SELECT id FROM reviews")
                        db_ids = {r[0] for r in cur.fetchall()}
                        new_rows = [r for r in fresh if r["id"] not in db_ids]
                        if new_rows:
                            rows = [(
                                r["id"], r.get("source", ""), r.get("date"), r.get("platform"),
                                r.get("user", "anonymous"), r.get("location", "India"),
                                r.get("text", ""), r.get("intent", "observation"),
                                r.get("categories", ["general"]), r.get("rating"),
                                r.get("url", ""),
                            ) for r in new_rows]
                            execute_values(
                                cur,
                                "INSERT INTO reviews (id, source, date, platform, user_name, location, "
                                "text, intent, categories, rating, url) VALUES %s "
                                "ON CONFLICT (id) DO NOTHING",
                                rows,
                            )
                            print(f"[API Scrape] Inserted {len(new_rows)} reviews into PostgreSQL")
                        cur.close()
                        conn.close()
                    except Exception as e:
                        print(f"[API Scrape] PostgreSQL insert skipped: {e}")

                try:
                    from scripts.generate_insights import generate_insights
                    generate_insights()
                    print("[API Scrape] Insights regenerated")
                except Exception as e:
                    print(f"[API Scrape] Insights generation skipped: {e}")

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[API Scrape] Error: {e}")
                status["error"] = str(e)

            _write_json(filepath, {
                "running":     False,
                "added":       added,
                "started_at":  status["started_at"],
                "finished_at": _now_iso(),
                "error":       status.get("error"),
            })

        threading.Thread(target=run, daemon=True).start()
        self._json({"ok": True})

    # ── POST /api/db/clear ────────────────────────────────────────────────

    def _post_db_clear(self):
        ok = auto_cleanup.truncate_dynamic_tables()
        if not ok:
            self._json({"error": "Truncation already in progress or failed"}, 409)
            return

        # Reset JSON data files so the dashboard reflects the cleared state
        db = DATABASE
        _write_json(os.path.join(db, "live_scraped_data.json"), [])
        _write_json(os.path.join(db, "cleaned_feedback.json"), [])
        _write_json(os.path.join(db, "survey_responses.json"), [])
        _write_json(os.path.join(db, "scrape_status.json"), {
            "running": False, "added": 0, "started_at": None,
            "finished_at": _now_iso(), "error": None,
        })
        _write_json(os.path.join(db, "ai_insights.json"), {
            "themes": [],
            "insights": [],
            "sentiment": {
                "positive": {"count": 0, "percentage": 0},
                "neutral":  {"count": 0, "percentage": 0},
                "negative": {"count": 0, "percentage": 0},
            },
            "categories": [],
        })
        self._json({"ok": True, "message": "All data cleared — PostgreSQL tables and dashboard data reset"})

    # ── POST /api/seed ────────────────────────────────────────────────────

    def _post_seed(self):
        try:
            import database.init_db
            database.init_db.init_schema()
            import database.seed_mock_data
            database.seed_mock_data.main()
            self._json({"ok": True, "message": "Database seeded successfully"})
        except Exception as e:
            self._json({"error": f"Seed failed: {e}"}, 500)

    # ── POST /api/recommend ───────────────────────────────────────────────

    def _post_recommend(self):
        body = self._parse_body()
        user_id = body.get("user_id")
        cart_items = body.get("cart_items", [])

        if not isinstance(user_id, int):
            self._json({"error": "user_id is required and must be an integer"}, 400)
            return
        if not isinstance(cart_items, list) or not cart_items:
            self._json({"error": "cart_items must be a non-empty array of {product_id, quantity}"}, 400)
            return

        product_ids = [item.get("product_id") for item in cart_items if isinstance(item, dict)]
        if not product_ids:
            self._json({"error": "Each cart item must have a product_id"}, 400)
            return

        try:
            from scripts.auto_cleanup import get_connection
            from scripts.ollama_client import get_client

            conn = get_connection()
            cur = conn.cursor()

            # Fetch all cart products with categories
            cur.execute("""
                SELECT p.id, p.name, p.price, p.sku, c.name AS category_name
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE p.id = ANY(%s)
            """, (product_ids,))
            cart_rows = cur.fetchall()
            if not cart_rows:
                self._json({"error": "No valid products found for the given product_ids"}, 400)
                return

            COMPLEMENTARY_MAP = {
                "Household":            ["Cleaning", "Personal Care", "Groceries"],
                "Cleaning":             ["Household", "Personal Care", "Groceries"],
                "Personal Care":        ["Household", "Cleaning", "Groceries"],
                "Baby Products":        ["Personal Care", "Dairy", "Groceries"],
                "Pet Supplies":         ["Packaged Food", "Groceries"],
                "Snacks":               ["Beverages", "Bakery", "Groceries"],
                "Beverages":            ["Snacks", "Bakery", "Dairy", "Groceries"],
                "Groceries":            ["Packaged Food", "Dairy", "Snacks", "Beverages", "Fruits & Vegetables"],
                "Fruits & Vegetables":  ["Dairy", "Beverages", "Snacks", "Bakery", "Groceries"],
                "Dairy":                ["Bakery", "Beverages", "Fruits & Vegetables", "Groceries"],
                "Bakery":               ["Dairy", "Beverages", "Snacks", "Groceries"],
                "Packaged Food":        ["Beverages", "Snacks", "Groceries"],
            }

            all_cart_ids = set(product_ids)
            recommendations = []
            ollama_pairs = []

            # 1-1: For each cart product, pick one adjacent product
            for row in cart_rows:
                pid, pname, pprice, psku, pcat = row
                adj_opts = COMPLEMENTARY_MAP.get(pcat, [])
                flash = None
                adjacent = None

                # Try each adjacent category until one passes all guardrails
                for adj_cat in adj_opts:
                    cur.execute("""
                        SELECT p.id, p.name, p.price, p.sku, p.description, p.image_url
                        FROM products p
                        JOIN categories c ON c.id = p.category_id
                        WHERE c.name = %s AND p.is_active = TRUE
                          AND p.id != %s
                        ORDER BY RANDOM()
                        LIMIT 3
                    """, (adj_cat, pid))
                    candidates = cur.fetchall()
                    for cand in candidates:
                        cflash = {"id": cand[0], "name": cand[1],
                                  "price": float(cand[2]), "sku": cand[3],
                                  "description": cand[4], "image_url": cand[5]}
                        # Guardrail 1: skip if flash product ID is in the cart
                        if cflash["id"] in all_cart_ids:
                            continue
                        # Guardrail 2: skip if flash product shares brand (first word)
                        cart_brand = _extract_brand(pname)
                        flash_brand = _extract_brand(cflash["name"])
                        if cart_brand and flash_brand and cart_brand == flash_brand:
                            continue
                        flash = cflash
                        adjacent = adj_cat
                        break
                    if flash:
                        break

                if not flash:
                    continue

                recommendations.append({
                    "cart_product": {"id": pid, "name": pname,
                                     "price": float(pprice), "category_name": pcat},
                    "flash_recommendation": flash,
                    "adjacent_category": adjacent,
                    "rationale": "",
                })
                ollama_pairs.append({
                    "cart_name": pname,
                    "flash_name": flash["name"],
                    "adjacent": adjacent,
                })

            cur.close()
            conn.close()

            if not recommendations:
                self._json({"error": "Could not generate any flash recommendations"}, 502)
                return

            # Call Ollama once for all rationales
            try:
                client = get_client()
                if client.is_available():
                    pairs_text = "\n".join(
                        f'{i+1}. Cart item: "{p["cart_name"]}" → '
                        f'Companion: "{p["flash_name"]}" ({p["adjacent"]})'
                        for i, p in enumerate(ollama_pairs)
                    )
                    prompt = (
                        "You are a cross-sell pairings engine. You will receive a list of cart items, "
                        "each already matched with a recommended companion product.\n\n"
                        "For EACH pair, write ONE short rationale sentence (max 15 words) explaining "
                        "why the companion fits the cart item. Be specific — name both products.\n\n"
                        "ABSOLUTE RULE: The companion product is always correct. Do not suggest "
                        "a different product. Only write the rationale.\n\n"
                        f"Pairs:\n{pairs_text}\n\n"
                        "Return ONLY a JSON array — no other text:\n"
                        '[\n'
                        '  {"cart_item": "...", "flash_recommendation": "...", '
                        '"rationale": "..."},\n'
                        '  ...\n'
                        ']'
                    )
                    response = client.chat(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1, max_tokens=500,
                    )

                    import re as _re
                    text = response.strip()
                    m = _re.search(r"\[.*\]", text, _re.DOTALL)
                    if m:
                        text = m.group(0)
                    text = text.replace("'", '"')
                    text = _re.sub(r",\s*}", "}", text)
                    text = _re.sub(r",\s*]", "]", text)
                    ai_data = json.loads(text)
                    if isinstance(ai_data, list):
                        # Map rationales back by matching cart_product name
                        for entry in ai_data:
                            cname = entry.get("cart_item", "")
                            rtext = entry.get("rationale", "")
                            for rec in recommendations:
                                if rec["cart_product"]["name"] == cname and rtext:
                                    rec["rationale"] = rtext
                                    break
            except Exception:
                pass

            # Fallback rationales for any missing
            for rec in recommendations:
                if not rec["rationale"]:
                    rec["rationale"] = (
                        f"Pair {rec['cart_product']['name']} with "
                        f"{rec['flash_recommendation']['name']}."
                    )

            self._json({
                "user_id": user_id,
                "recommendations": recommendations,
            })

        except Exception as e:
            self._json({"error": str(e)}, 502)

    # ── POST /api/per-product-recommend ──────────────────────────────────

    def _post_per_product_recommend(self):
        body = self._parse_body()
        user_id = body.get("user_id")
        cart_item = body.get("cart_item", {})
        product_id = cart_item.get("product_id")
        quantity = cart_item.get("quantity", 1)

        if not isinstance(user_id, int):
            self._json({"error": "user_id is required and must be an integer"}, 400)
            return
        if not isinstance(product_id, int):
            self._json({"error": "cart_item.product_id is required"}, 400)
            return

        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT p.id, p.name, p.price, p.sku, c.name AS category_name
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE p.id = %s AND p.is_active = TRUE
            """, (product_id,))
            row = cur.fetchone()
            if not row:
                self._json({"error": "Product not found"}, 404)
                return

            prod_id, prod_name, prod_price, prod_sku, prod_cat = row

            PPC_MAP = {
                "Household":            ["Cleaning", "Personal Care", "Groceries"],
                "Cleaning":             ["Household", "Personal Care", "Groceries"],
                "Personal Care":        ["Household", "Cleaning", "Groceries"],
                "Baby Products":        ["Personal Care", "Dairy", "Groceries"],
                "Pet Supplies":         ["Packaged Food", "Groceries"],
                "Snacks":               ["Beverages", "Bakery", "Groceries"],
                "Beverages":            ["Snacks", "Bakery", "Dairy", "Groceries"],
                "Groceries":            ["Dairy", "Snacks", "Beverages", "Fruits & Vegetables"],
                "Fruits & Vegetables":  ["Dairy", "Beverages", "Snacks", "Bakery", "Groceries"],
                "Dairy":                ["Bakery", "Beverages", "Fruits & Vegetables", "Groceries"],
                "Bakery":               ["Dairy", "Beverages", "Snacks", "Groceries"],
                "Packaged Food":        ["Beverages", "Snacks", "Groceries"],
            }

            adj_opts = PPC_MAP.get(prod_cat, [])
            if not adj_opts:
                self._json({"error": f"No adjacent category for {prod_cat}"}, 502)
                return
            adjacent = adj_opts[0]

            # Fetch 1 product from adjacent category, excluding any in cart
            cur.execute("""
                SELECT p.id, p.name, p.price, p.sku, p.description, p.image_url
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE c.name = %s AND p.is_active = TRUE
                  AND p.id != %s
                ORDER BY RANDOM()
                LIMIT 1
            """, (adjacent, product_id))
            rec_row = cur.fetchone()

            rec_products = []
            rec_name = ""
            if rec_row:
                rec_products = [{
                    "id": rec_row[0], "name": rec_row[1],
                    "price": float(rec_row[2]), "sku": rec_row[3],
                    "description": rec_row[4], "image_url": rec_row[5],
                }]
                rec_name = rec_row[1]

            # Ollama-powered per-product rationale
            rationale = f"Since you added {prod_name}, try {rec_name}."
            if rec_name:
                try:
                    from scripts.ollama_client import get_client
                    client = get_client()
                    if client.is_available():
                        prompt = (
                            f"The user just added '{prod_name}' ({prod_cat}) to their "
                            f"cart. Recommend '{rec_name}' ({adjacent}) as a perfect "
                            f"companion. Write ONE short sentence (max 15 words) "
                            f"explaining why '{rec_name}' pairs well with "
                            f"'{prod_name}'. Be specific and natural. Example: "
                            f"'Parle-G biscuits are best enjoyed with a hot cup "
                            f"of Brooke Bond Red Label Tea.'"
                        )
                        response = client.chat(
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.3, max_tokens=80,
                        )
                        text = response.strip().strip('"').strip("'")
                        if text and len(text) > 8:
                            rationale = text
                except Exception:
                    pass

            cur.close()
            conn.close()

            self._json({
                "cart_product": {
                    "id": prod_id, "name": prod_name,
                    "price": float(prod_price), "category_name": prod_cat,
                },
                "recommendation": {
                    "adjacent_category": adjacent,
                    "rationale": rationale,
                    "products": rec_products,
                },
            })

        except Exception as e:
            self._json({"error": str(e)}, 502)

    # ── POST /api/feedback ───────────────────────────────────────────────

    def _post_feedback(self):
        body = self._parse_body()
        user_id = body.get("user_id")
        product_id = body.get("product_id")
        action = body.get("action")

        if not isinstance(user_id, int):
            self._json({"error": "user_id is required and must be an integer"}, 400)
            return
        if not isinstance(product_id, int):
            self._json({"error": "product_id is required and must be an integer"}, 400)
            return
        if action not in ("add_to_cart", "not_interested"):
            self._json({"error": "action must be 'add_to_cart' or 'not_interested'"}, 400)
            return

        try:
            from scripts.auto_cleanup import get_connection
            rating = 5 if action == "add_to_cart" else 1
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO feedback (user_id, product_id, rating, comment, feedback_type)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, product_id, rating, f"recommendation:{action}", "product"))
            conn.commit()
            cur.close()
            conn.close()
            self._json({"ok": True, "action": action})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── GET /api/users ────────────────────────────────────────────────────

    def _get_users(self, params):
        """Return all users (id + name) for the user-selector dropdown."""
        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM users ORDER BY id")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            users = [{"id": r[0], "name": r[1]} for r in rows]
            self._json({"users": users, "total": len(users)})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── GET /api/cart ─────────────────────────────────────────────────────

    def _get_cart(self, params):
        """Return all cart items for a given user, JOINed with product details."""
        user_id = params.get("user_id")
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            self._json({"error": "user_id query parameter is required and must be an integer"}, 400)
            return

        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT c.product_id, p.name, p.price, p.sku,
                       c.quantity, cat.name AS category_name, p.image_url
                FROM user_carts c
                JOIN products p ON p.id = c.product_id
                JOIN categories cat ON cat.id = p.category_id
                WHERE c.user_id = %s
                ORDER BY c.created_at
            """, (user_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            items = [
                {"product_id": r[0], "name": r[1], "price": float(r[2]),
                 "sku": r[3], "quantity": r[4], "category_name": r[5], "image_url": r[6]}
                for r in rows
            ]
            self._json({"user_id": user_id, "items": items, "total": len(items)})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── POST /api/cart ────────────────────────────────────────────────────

    def _post_cart(self):
        """Upsert a product into the user's cart. Body: {user_id, product_id, quantity}."""
        body = self._parse_body()
        user_id = body.get("user_id")
        product_id = body.get("product_id")
        quantity = body.get("quantity", 1)

        if not isinstance(user_id, int):
            self._json({"error": "user_id is required and must be an integer"}, 400)
            return
        if not isinstance(product_id, int):
            self._json({"error": "product_id is required and must be an integer"}, 400)
            return
        if not isinstance(quantity, int) or quantity < 0:
            self._json({"error": "quantity must be a non-negative integer"}, 400)
            return

        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()

            if quantity == 0:
                cur.execute("DELETE FROM user_carts WHERE user_id = %s AND product_id = %s",
                            (user_id, product_id))
            else:
                cur.execute("""
                    INSERT INTO user_carts (user_id, product_id, quantity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, product_id)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW()
                """, (user_id, product_id, quantity))

            conn.commit()
            cur.close()
            conn.close()
            self._json({"ok": True, "user_id": user_id, "product_id": product_id, "quantity": quantity if quantity else 0})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── DELETE /api/cart ──────────────────────────────────────────────────

    def _delete_cart(self, parsed):
        """Delete cart item(s). Params: user_id=X (&product_id=Y or &all=true)."""
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        try:
            user_id = int(params.get("user_id", [None])[0])
        except (TypeError, ValueError):
            self._json({"error": "user_id query parameter is required and must be an integer"}, 400)
            return

        product_id = params.get("product_id")
        all_flag = params.get("all")

        try:
            from scripts.auto_cleanup import get_connection
            conn = get_connection()
            cur = conn.cursor()

            if all_flag and all_flag[0].lower() in ("true", "1"):
                cur.execute("DELETE FROM user_carts WHERE user_id = %s", (user_id,))
                deleted = cur.rowcount
            elif product_id:
                try:
                    pid = int(product_id[0])
                except (ValueError, TypeError):
                    self._json({"error": "product_id must be an integer"}, 400)
                    return
                cur.execute("DELETE FROM user_carts WHERE user_id = %s AND product_id = %s",
                            (user_id, pid))
                deleted = cur.rowcount
            else:
                self._json({"error": "Provide product_id=X or all=true query parameter"}, 400)
                return

            conn.commit()
            cur.close()
            conn.close()
            self._json({"ok": True, "deleted": deleted})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── POST /api/survey/submit ───────────────────────────────────────────

    def _post_survey_submit(self):
        body = self._parse_body()
        required = [
            (body.get("respondent_name", "").strip(), "Full Name is required"),
            (body.get("email", "").strip(),           "Email is required"),
            (body.get("city", "").strip(),            "City is required"),
            (body.get("age_group"),                   "Age Group is required"),
            (body.get("order_frequency"),             "Order Frequency is required"),
        ]
        for val, msg in required:
            if not val:
                self._json({"error": msg}, 400)
                return

        filled = sum(1 for k in [
            "respondent_name", "email", "city", "age_group",
            "order_frequency", "suggestion",
        ] if body.get(k))
        if body.get("categories"):
            filled += 1
        if body.get("blockers"):
            filled += 1
        quality_score = min(100, int(filled / 8.0 * 100))

        response = {
            "id":               str(uuid.uuid4())[:8],
            "respondent_name":  body.get("respondent_name", "").strip(),
            "email":            body.get("email", "").strip(),
            "city":             body.get("city", "").strip(),
            "age_group":        body.get("age_group", ""),
            "order_frequency":  body.get("order_frequency", ""),
            "categories":       body.get("categories", []),
            "blockers":         body.get("blockers", []),
            "suggestion":       body.get("suggestion", "").strip(),
            "quality_score":    quality_score,
            "created_at":       _now_iso(),
        }

        filepath = os.path.join(DATABASE, "survey_responses.json")
        responses = _read_json(filepath, [])
        if not isinstance(responses, list):
            responses = []
        responses.append(response)
        _write_json(filepath, responses)
        self._json(response)

    # ── GET /api/matrix ─────────────────────────────────────────────────

    def _get_matrix(self, params):
        cleaned = _read_json(os.path.join(DATABASE, "cleaned_feedback.json"), [])
        if not isinstance(cleaned, list) or not cleaned:
            cleaned = _read_json(os.path.join(DATABASE, "live_scraped_data.json"), [])
        if not isinstance(cleaned, list):
            cleaned = []

        category_data = {}
        for r in cleaned:
            cats = r.get("categories", []) or ["general"]
            sentiment = r.get("sentiment", "neutral") or "neutral"
            if sentiment not in ("positive", "neutral", "negative"):
                sentiment = "neutral"
            for cat in cats:
                if cat not in category_data:
                    category_data[cat] = {
                        "mentions": 0, "positive": 0, "neutral": 0, "negative": 0,
                        "ratings": [], "sources": set(), "candidates": [],
                    }
                category_data[cat]["mentions"] += 1
                if sentiment in ("positive", "neutral", "negative"):
                    category_data[cat][sentiment] += 1
                if r.get("rating"):
                    category_data[cat]["ratings"].append(r["rating"])
                if r.get("source"):
                    category_data[cat]["sources"].add(r["source"])
                text = (r.get("text") or "").strip()
                if text and len(text) >= 20:
                    category_data[cat]["candidates"].append({
                        "text": text[:250],
                        "source": r.get("source", ""),
                        "sentiment": sentiment,
                        "rating": r.get("rating"),
                    })

        for cat_data in category_data.values():
            cat_data["quotes"] = self._pick_best_quotes(cat_data["candidates"], 3)
            del cat_data["candidates"]

        categories = []
        for name, data in sorted(category_data.items(), key=lambda x: -x[1]["mentions"]):
            avg_rating = round(sum(data["ratings"]) / len(data["ratings"]), 1) if data["ratings"] else 0
            total = data["mentions"]
            neg_pct = round(data["negative"] / total * 100) if total else 0
            gap_severity = "High" if neg_pct > 50 else ("Medium" if neg_pct > 30 else "Low")
            business_impact = "High" if total > 20 else ("Medium" if total > 10 else "Low")

            categories.append({
                "id": name,
                "name": name.replace("_", " ").title(),
                "mentions": total,
                "gap_severity": gap_severity,
                "business_impact": business_impact,
                "neg_pct": neg_pct,
                "avg_rating": avg_rating,
                "sentiment": {"positive": data["positive"], "neutral": data["neutral"], "negative": data["negative"]},
                "sources": list(data["sources"]),
                "quotes": data["quotes"],
            })

        self._json({"categories": categories, "total_reviews": len(cleaned)})

    def _pick_best_quotes(self, candidates, limit=3):
        if not candidates:
            return []
        scored = []
        for c in candidates:
            score = 0
            if c["sentiment"] == "negative":
                score += 100
            elif c["sentiment"] == "neutral":
                score += 30
            text = c["text"]
            if len(text) > 100:
                score += 20
            if len(text) > 180:
                score += 10
            if any(kw in text.lower() for kw in ["refund", "expired", "wrong", "late", "cancelled",
                    "worst", "terrible", "never received", "no response", "fake", "damaged",
                    "complaint", "fraud", "poor", "disappointed", "unacceptable"]):
                score += 30
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        seen_texts = set()
        picked = []
        for _, c in scored:
            short = c["text"][:60].lower().strip()
            if short in seen_texts:
                continue
            seen_texts.add(short)
            picked.append(c)
            if len(picked) >= limit:
                break
        return picked

    # ── POST /api/search ──────────────────────────────────────────────────

    def _post_search(self):
        body = self._parse_body()
        query = (body.get("query") or "").strip()
        if not query:
            self._json({"error": "Query is required"}, 400)
            return

        client = self._get_ollama_client()

        query = self._sanitize_query(query)

        try:
            context = self._build_search_context(query)
            if context["total"] == 0:
                self._json({"answer": "The database is currently empty — there are no reviews to analyze yet. Try scraping some data first.", "query": query, "sources": []})
                return
            answer = self._call_ollama_search(client, query, context)
            self._json({"answer": answer, "query": query, "sources": context["source_list"]})
        except Exception as e:
            self._json({"error": f"AI service error: {str(e)}"}, 502)

    def _sanitize_query(self, query):
        query = re.sub(r'<[^>]+>', '', query)
        query = re.sub(r'[`$]', '', query)
        return query[:500]

    def _build_search_context(self, query):
        cleaned = _read_json(os.path.join(DATABASE, "cleaned_feedback.json"), [])
        if not isinstance(cleaned, list) or not cleaned:
            cleaned = _read_json(os.path.join(DATABASE, "live_scraped_data.json"), [])
        if not isinstance(cleaned, list):
            cleaned = []
        # Limit to 50 reviews to keep prompts fast enough for Ollama on CPU
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        insights = _read_json(os.path.join(DATABASE, "ai_insights.json"), {})
        if not isinstance(insights, dict):
            insights = {}

        source_set = set()
        all_cats = set()
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        rating_sum = 0
        rating_count = 0
        cat_data = {}

        for r in cleaned:
            sentiment = r.get("sentiment", "neutral") or "neutral"
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1
            cats = r.get("categories") or ["general"]
            for c in cats:
                all_cats.add(c)
                if c not in cat_data:
                    cat_data[c] = {"mentions": 0, "positive": 0, "neutral": 0, "negative": 0, "ratings": []}
                cat_data[c]["mentions"] += 1
                if sentiment in ("positive", "neutral", "negative"):
                    cat_data[c][sentiment] += 1
                if r.get("rating"):
                    cat_data[c]["ratings"].append(r["rating"])
            if r.get("source"):
                source_set.add(r["source"])
            if r.get("rating"):
                rating_sum += r["rating"]
                rating_count += 1

        total = len(cleaned)
        avg_rating = round(rating_sum / rating_count, 1) if rating_count else 0

        sections = []

        sections.append(f"=== SWIGGY INSTAMART DISCOVERY ENGINE — COMPLETE DATA EXPORT ===")
        sections.append(f"Total reviews analyzed: {total}")
        sections.append(f"Data sources: {', '.join(sorted(source_set)) if source_set else 'N/A'}")
        sections.append(f"Overall average rating: {avg_rating}/5")
        sections.append(f"Sentiment distribution: Positive {sentiment_counts['positive']} ({round(sentiment_counts['positive']/total*100,1) if total else 0}%), Neutral {sentiment_counts['neutral']} ({round(sentiment_counts['neutral']/total*100,1) if total else 0}%), Negative {sentiment_counts['negative']} ({round(sentiment_counts['negative']/total*100,1) if total else 0}%)")

        sections.append(f"\n=== CATEGORY BREAKDOWN ===")
        sorted_cats = sorted(cat_data.items(), key=lambda x: -x[1]["mentions"])
        for name, d in sorted_cats:
            neg_pct = round(d["negative"] / d["mentions"] * 100) if d["mentions"] else 0
            avg_r = round(sum(d["ratings"]) / len(d["ratings"]), 1) if d["ratings"] else 0
            severity = "High" if neg_pct > 50 else ("Medium" if neg_pct > 30 else "Low")
            impact = "High" if d["mentions"] > 20 else ("Medium" if d["mentions"] > 10 else "Low")
            sections.append(
                f"- {name}: {d['mentions']} reviews, sentiment (+{d['positive']}/{d['neutral']}/{d['negative']}), "
                f"avg rating {avg_r}, negative% {neg_pct}%, gap_severity={severity}, business_impact={impact}"
            )

        themes = insights.get("themes", [])
        if themes:
            sections.append(f"\n=== DISCOVERED THEMES ({len(themes)} total) ===")
            for t in themes:
                blocks = t.get("blockers", [])
                triggers = t.get("triggers", [])
                evidence = t.get("evidence", [])
                block_str = "; ".join(blocks[:3]) if blocks else "none identified"
                trigger_str = "; ".join(triggers[:3]) if triggers else "none identified"
                sections.append(
                    f"- {t.get('name', 'Unknown')}: {t.get('mentions', 0)} mentions, "
                    f"frequency={t.get('frequency', 'N/A')}, sentiment (+{t.get('sentiment',{}).get('positive',0)}/"
                    f"{t.get('sentiment',{}).get('neutral',0)}/{t.get('sentiment',{}).get('negative',0)})"
                )
                sections.append(f"  Blockers: {block_str}")
                sections.append(f"  Triggers: {trigger_str}")
                if evidence:
                    for ev in evidence[:3]:
                        sections.append(f'  Evidence: "{ev.get("text","")[:200]}" (source: {ev.get("source","")}, category: {ev.get("category","")})')

        structured = insights.get("insights", [])
        if structured:
            sections.append(f"\n=== STRUCTURED INSIGHTS ({len(structured)} total) ===")
            for ins in structured:
                sections.append(f"- {ins.get('title', 'Untitled')}")
                sections.append(f"  Observation: {ins.get('observation', '')}")
                sections.append(f"  User Need: {ins.get('user_need', '')}")
                sections.append(f"  Root Cause: {ins.get('root_cause', '')}")
                sections.append(f"  Opportunity: {ins.get('opportunity', '')}")
                sections.append(f"  Implication: {ins.get('implication', '')}")

        sections.append(f"\n=== REVIEWS (showing {min(15, total)} of {total}) ===")
        sections.append("Format: [SENTIMENT] (Source, Categories, Rating) — Review text")

        neg_reviews = [r for r in cleaned if r.get("sentiment") == "negative"]
        neu_reviews = [r for r in cleaned if r.get("sentiment") == "neutral"]
        pos_reviews = [r for r in cleaned if r.get("sentiment") == "positive"]
        curated = neg_reviews[:8] + neu_reviews[:5] + pos_reviews[:2]

        for r in curated:
            text = (r.get("text") or "").strip()[:150]
            sentiment = r.get("sentiment", "unknown")
            cats = ", ".join(r.get("categories") or ["general"])
            source = r.get("source", "unknown")
            rating = r.get("rating", "N/A")
            themes_str = ", ".join(r.get("themes") or [])
            sections.append(f"- [{sentiment}] ({source}, {cats}, rating={rating}, themes=[{themes_str}]): {text}")

        context_text = "\n".join(sections)
        return {"context": context_text, "source_list": sorted(source_set), "total": total}

    def _get_ollama_client(self):
        global _ollama_client
        if _ollama_client is None:
            _ollama_client = get_client()
        return _ollama_client

    def _call_ollama_search(self, client, query, context):
        system_prompt = (
            "You're chatting with a colleague about Swiggy Instamart user reviews. "
            "Answer like a human.\n\n"
            "Pick one or two concrete things from the data that answer the question — "
            "a specific number, a real quote, a clear pattern. Mention them naturally.\n\n"
            "If the data contains nothing relevant to the question, say so directly "
            "(e.g. 'None of the reviews mention that'). Do NOT make up connections "
            "or force unrelated reviews into an answer.\n\n"
            "Never start with 'Based on the data', 'According to the data', "
            "'The data suggests', 'It seems that', or 'The data shows'. "
            "Just say what you noticed. 3-6 sentences. No lists. No sign-offs."
        )

        user_prompt = f"DATA:\n{context}\n\nQUESTION: {query}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return client.chat(messages, temperature=0.65, max_tokens=800, timeout=120)

    # ── DELETE /api/charts/configs/<id> ───────────────────────────────────

    def _delete_charts_config(self, chart_id):
        filepath = os.path.join(DATABASE, "chart_configs.json")
        configs = _read_json(filepath, [])
        before = len(configs)
        configs = [c for c in configs if c.get("id") != chart_id]
        if len(configs) == before:
            self._json({"error": "Chart config not found"}, 404)
            return
        _write_json(filepath, configs)
        self._json({"ok": True})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8080))
    os.chdir(ROOT)
    auto_cleanup.start_cleanup_monitor()
    server = ThreadedHTTPServer(("0.0.0.0", port), APIHandler)
    print(f"Server running at http://localhost:{port}")
    print(f"Dashboard: http://localhost:{port}/ui/index.html")
    print(f"API endpoints:")
    print(f"  GET  /api/insights         - AI insights JSON")
    print(f"  GET  /api/kpis             - Dashboard KPIs")
    print(f"  GET  /api/records          - Paginated live records")
    print(f"  GET  /api/charts/data      - Aggregated chart data")
    print(f"  GET  /api/charts/configs   - Saved chart configs")
    print(f"  GET  /api/scrape/status    - Scrape job status")
    print(f"  GET  /api/survey/responses - Survey responses")
    print(f"  POST /api/charts/configs   - Save chart config")
    print(f"  POST /api/scrape           - Start scrape job")
    print(f"  POST /api/survey/submit    - Submit survey response")
    print(f"  GET  /api/products          - All active products with categories")
    print(f"  POST /api/search           - AI natural language search")
    print(f"  POST /api/feedback         - Log recommendation feedback (add_to_cart / not_interested)")
    print(f"  DEL  /api/charts/configs/<id> - Delete chart config")
    server.serve_forever()


if __name__ == "__main__":
    main()
