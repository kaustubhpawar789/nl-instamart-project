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

import requests as _http_requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(ROOT, "database")

load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

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


class APIHandler(SimpleHTTPRequestHandler):
    # ── Routing ────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
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
        }

        handler = routes.get(path)
        if handler:
            handler(params)
        elif path.startswith("/ui/") or path == "/ui" or path == "/":
            if path in ("", "/"):
                self.path = "/ui/index.html"
            super().do_GET()
        else:
            self.send_error(404)

    def send_response(self, code, message=None):
        super().send_response(code, message)
        # Disable caching for all static UI assets so CSS/JS changes are immediate
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")

    def do_POST(self):
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
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/charts/configs/"):
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
                from scripts.scrapers.apple_store_scraper import AppleStoreScraper
                from scripts.scrapers.base_scraper import BaseScraper

                live_path = os.path.join(DATABASE, "live_scraped_data.json")
                live = _read_json(live_path, [])
                if not isinstance(live, list):
                    live = []
                existing_ids = {r.get("id") for r in live}
                existing_texts = {r.get("text", "")[:80] for r in live}

                apple_scraper = AppleStoreScraper()
                print("[API Scrape] Scraping Apple App Store...")
                apple_reviews = apple_scraper.scrape()
                new_apple = 0
                for r in apple_reviews:
                    text_key = r["text"][:80]
                    if r["id"] not in existing_ids and text_key not in existing_texts:
                        r["sentiment"] = "neutral"
                        r["themes"] = []
                        live.append(r)
                        existing_ids.add(r["id"])
                        existing_texts.add(text_key)
                        new_apple += 1
                print(f"[API Scrape] Apple App Store: {new_apple} new reviews")

                try:
                    from scripts.scrapers.google_play_scraper import GooglePlayScraper
                    gp_scraper = GooglePlayScraper()
                    print("[API Scrape] Scraping Google Play Store...")
                    gp_reviews = gp_scraper.scrape()
                    new_gp = 0
                    for r in gp_reviews:
                        text_key = r["text"][:80]
                        if r["id"] not in existing_ids and text_key not in existing_texts:
                            r["sentiment"] = "neutral"
                            r["themes"] = []
                            live.append(r)
                            existing_ids.add(r["id"])
                            existing_texts.add(text_key)
                            new_gp += 1
                    print(f"[API Scrape] Google Play Store: {new_gp} new reviews")
                except ImportError:
                    print("[API Scrape] Google Play scraper not available, skipping")

                _write_json(live_path, live)
                added = new_apple
                try:
                    added += new_gp
                except Exception:
                    pass

                try:
                    from scripts.generate_insights import generate_insights
                    generate_insights()
                    print("[API Scrape] Insights regenerated")
                except Exception as e:
                    print(f"[API Scrape] Insights generation skipped: {e}")

            except Exception as e:
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

        if not GROQ_API_KEY:
            self._json({"error": "AI service not configured — GROQ_API_KEY missing"}, 503)
            return

        query = self._sanitize_query(query)

        try:
            context = self._build_search_context(query)
            answer = self._call_groq_search(query, context)
            self._json({"answer": answer, "query": query, "sources": context["source_list"]})
        except Exception as e:
            self._json({"error": f"AI service temporarily unavailable: {str(e)}"}, 502)

    def _sanitize_query(self, query):
        query = re.sub(r'<[^>]+>', '', query)
        query = re.sub(r'[`$]', '', query)
        return query[:500]

    def _build_search_context(self, query):
        cleaned = _read_json(os.path.join(DATABASE, "cleaned_feedback.json"), [])
        if not isinstance(cleaned, list):
            cleaned = []
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

        sections.append(f"\n=== REVIEWS (showing {min(80, total)} of {total} — negative/neutral prioritized) ===")
        sections.append("Format: [SENTIMENT] (Source, Categories, Rating) — Review text")

        neg_reviews = [r for r in cleaned if r.get("sentiment") == "negative"]
        neu_reviews = [r for r in cleaned if r.get("sentiment") == "neutral"]
        pos_reviews = [r for r in cleaned if r.get("sentiment") == "positive"]
        curated = neg_reviews[:40] + neu_reviews[:25] + pos_reviews[:15]

        for r in curated:
            text = (r.get("text") or "").strip()[:150]
            sentiment = r.get("sentiment", "unknown")
            cats = ", ".join(r.get("categories") or ["general"])
            source = r.get("source", "unknown")
            rating = r.get("rating", "N/A")
            themes_str = ", ".join(r.get("themes") or [])
            sections.append(f"- [{sentiment}] ({source}, {cats}, rating={rating}, themes=[{themes_str}]): {text}")

        context_text = "\n".join(sections)
        return {"context": context_text, "source_list": sorted(source_set)}

    def _call_groq_search(self, query, context):
        system_prompt = (
            "You are a sharp, insightful product analyst. A PM has given you a dataset of "
            "274 user reviews from Swiggy Instamart (India's grocery delivery app) along with "
            "pre-computed analytics (sentiment, themes, category breakdowns, insights).\n\n"
            "Answer the question directly — no introductions, no filler, no 'Based on the data...'. "
            "Start with your answer immediately.\n\n"
            "Rules:\n"
            "- Think before answering. Identify what the data actually says vs what you're inferring.\n"
            "- Use specific numbers and quote real reviews to back up claims.\n"
            "- If you're inferring something, say so briefly ('This likely means...' or 'The pattern suggests...').\n"
            "- Keep it concise. Aim for a clear, meaty 2-4 paragraph answer. Don't pad with headers and bullet points unless the question truly needs them.\n"
            "- Write like a thoughtful colleague, not a report template.\n"
            "- Never say 'the data doesn't contain enough information'. Work with what you have.\n"
            "- Never start with 'Introduction' or 'To understand...'. Just answer."
        )

        user_prompt = f"DATA:\n{context}\n\nQUESTION: {query}"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 2000,
        }

        resp = _http_requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=90)

        retries = 0
        max_retries = 3
        while resp.status_code == 429 and retries < max_retries:
            retries += 1
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after else (5 * retries)
            time.sleep(wait)
            resp = _http_requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=90)

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    os.chdir(ROOT)
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
    print(f"  POST /api/search           - AI natural language search")
    print(f"  DEL  /api/charts/configs/<id> - Delete chart config")
    server.serve_forever()


if __name__ == "__main__":
    main()
