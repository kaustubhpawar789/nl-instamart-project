"""
Data Pipeline - Orchestrates scraping, cleaning, AI categorization, and database storage.

Usage:
    python scripts/data_pipeline.py --all
    python scripts/data_pipeline.py --sources reddit,trustpilot
    python scripts/data_pipeline.py --clean-only
    python scripts/data_pipeline.py --store-only
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

sys.path.insert(0, ROOT)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

DATA_DIR = os.path.join(ROOT, "database")
OUTPUT_FILE = os.path.join(DATA_DIR, "live_scraped_data.json")
CLEANED_FILE = os.path.join(DATA_DIR, "cleaned_feedback.json")
PIPELINE_LOG = os.path.join(DATA_DIR, "pipeline_log.json")

CATEGORIES = [
    "groceries", "snacks", "beverages", "household", "personal_care",
    "pet_supplies", "baby_products", "dairy", "packaged_food", "cleaning",
    "electronics", "general",
]


def load_existing_ids(filepath: str) -> set:
    """Load existing record IDs from a JSON file."""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return {r["id"] for r in data if "id" in r}
    except (json.JSONDecodeError, KeyError):
        return set()


def deduplicate_reviews(reviews: List[Dict], existing_ids: set) -> List[Dict]:
    """Remove duplicate reviews based on text hash and ID."""
    seen_hashes = set()
    unique = []

    for review in reviews:
        text_hash = hashlib.md5(review.get("text", "").encode("utf-8")).hexdigest()
        review_id = review.get("id", "")

        if text_hash in seen_hashes or review_id in existing_ids:
            continue

        seen_hashes.add(text_hash)
        unique.append(review)

    return unique


def clean_reviews(reviews: List[Dict]) -> List[Dict]:
    """Clean and validate review data."""
    cleaned = []
    for review in reviews:
        text = review.get("text", "").strip()
        if not text or len(text) < 10:
            continue

        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        text = " ".join(text.split())

        if not review.get("source"):
            continue
        if not review.get("date"):
            review["date"] = datetime.now().strftime("%Y-%m-%d")

        if review.get("intent") not in ["complaint", "suggestion", "praise", "observation", "question", "spam"]:
            from scripts.scrapers.base_scraper import BaseScraper
            review["intent"] = BaseScraper.determine_intent(text)

        if not review.get("categories") or review["categories"] == ["general"]:
            from scripts.scrapers.base_scraper import BaseScraper
            review["categories"] = BaseScraper.determine_categories(text)

        if review.get("rating") and (review["rating"] < 1 or review["rating"] > 5):
            review["rating"] = None

        review["text"] = text
        cleaned.append(review)

    return cleaned


def ai_categorize_batch(reviews: List[Dict], retry: int = 3) -> List[Dict]:
    """Use Groq AI to categorize and enrich a batch of reviews."""
    if not GROQ_API_KEY:
        print("  [AI] No GROQ_API_KEY, skipping AI categorization")
        return reviews

    prompt = """Analyze these user reviews and for each one provide enriched categorization.

For each review, return a JSON object with:
- "id": the review ID
- "intent": one of "complaint", "suggestion", "praise", "observation", "question"
- "categories": array of relevant categories from: groceries, snacks, beverages, household, personal_care, pet_supplies, baby_products, dairy, packaged_food, cleaning, electronics, general
- "sentiment": one of "positive", "neutral", "negative"
- "themes": array of 1-3 key themes (e.g., "delivery_quality", "product_quality", "customer_service", "pricing", "app_experience", "refund_issues")

Return ONLY a JSON array of objects. No other text.

Reviews:
"""

    chunk_size = 15
    enriched = []

    for i in range(0, len(reviews), chunk_size):
        chunk = reviews[i:i + chunk_size]
        chunk_data = [
            {
                "id": r["id"],
                "text": r["text"][:500],
                "source": r["source"],
                "existing_intent": r.get("intent"),
                "existing_categories": r.get("categories"),
            }
            for r in chunk
        ]

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a data categorization assistant. Return only valid JSON."},
                {"role": "user", "content": prompt + json.dumps(chunk_data, indent=2)},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        for attempt in range(retry):
            try:
                resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    result = resp.json()["choices"][0]["message"]["content"]
                    result = result.strip()
                    if result.startswith("```"):
                        result = result.split("\n", 1)[1].rsplit("```", 1)[0]
                    ai_data = json.loads(result)
                    ai_map = {item["id"]: item for item in ai_data if "id" in item}

                    for review in chunk:
                        if review["id"] in ai_map:
                            ai_info = ai_map[review["id"]]
                            review["intent"] = ai_info.get("intent", review.get("intent"))
                            review["categories"] = ai_info.get("categories", review.get("categories"))
                            review["sentiment"] = ai_info.get("sentiment", "neutral")
                            review["themes"] = ai_info.get("themes", [])
                        else:
                            review["sentiment"] = "neutral"
                            review["themes"] = []
                        enriched.append(review)
                    break
                elif resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"  [AI] Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [AI] Error {resp.status_code}: {resp.text[:200]}")
                    for review in chunk:
                        review["sentiment"] = "neutral"
                        review["themes"] = []
                        enriched.append(review)
                    break
            except Exception as e:
                print(f"  [AI] Exception: {e}")
                for review in chunk:
                    review["sentiment"] = "neutral"
                    review["themes"] = []
                    enriched.append(review)
                break
        else:
            for review in chunk:
                review["sentiment"] = "neutral"
                review["themes"] = []
                enriched.append(review)

        if i + chunk_size < len(reviews):
            time.sleep(2)

    return enriched


def store_to_database(reviews: List[Dict], clear_existing: bool = False):
    """Store reviews into PostgreSQL databases."""
    try:
        from database.db import get_connection, execute, query
    except ImportError:
        print("  [DB] Could not import database module, skipping DB storage")
        return

    if clear_existing:
        print("  [DB] Clearing existing data from all tables...")
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                TRUNCATE TABLE
                    theme_categories, theme_triggers, theme_blockers, theme_evidence,
                    themes, insights, research_data, reviews, sentiment
                    CASCADE
            """)

            try:
                cur.execute("""
                    TRUNCATE TABLE
                        workflow_outputs, test_data, tickets, feedback,
                        recommendations, products, users
                        CASCADE
                """)
            except Exception:
                conn.rollback()
                conn = get_connection()
                cur = conn.cursor()

            conn.commit()
            cur.close()
            conn.close()
            print("  [DB] Tables cleared successfully")
        except Exception as e:
            print(f"  [DB] Error clearing tables: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    print(f"  [DB] Inserting {len(reviews)} reviews into instamart database...")
    insert_sql = """
        INSERT INTO reviews (id, source, date, platform, user_name, location, text, intent, categories, rating, url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            intent = EXCLUDED.intent,
            categories = EXCLUDED.categories,
            rating = EXCLUDED.rating
    """
    params_list = []
    for r in reviews:
        params_list.append((
            r.get("id"),
            r.get("source"),
            r.get("date"),
            r.get("platform", "web"),
            r.get("user", "anonymous"),
            r.get("location", "India"),
            r.get("text"),
            r.get("intent", "observation"),
            r.get("categories", ["general"]),
            r.get("rating"),
            r.get("url", "#"),
        ))

    try:
        from database.db import execute_many
        execute_many(insert_sql, params_list)
        print(f"  [DB] Inserted {len(params_list)} reviews into instamart.reviews")
    except Exception as e:
        print(f"  [DB] Error inserting reviews: {e}")

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM reviews")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  [DB] Total reviews in instamart.reviews: {count}")
    except Exception as e:
        print(f"  [DB] Error counting reviews: {e}")


def aggregate_themes(reviews: List[Dict]):
    """Aggregate themes from reviews and store in database."""
    try:
        from database.db import get_connection
    except ImportError:
        return

    theme_counts = {}
    for review in reviews:
        themes = review.get("themes", [])
        sentiment = review.get("sentiment", "neutral")
        for theme in themes:
            if theme not in theme_counts:
                theme_counts[theme] = {"count": 0, "pos": 0, "neu": 0, "neg": 0}
            theme_counts[theme]["count"] += 1
            if sentiment == "positive":
                theme_counts[theme]["pos"] += 1
            elif sentiment == "negative":
                theme_counts[theme]["neg"] += 1
            else:
                theme_counts[theme]["neu"] += 1

    if not theme_counts:
        return

    print(f"  [DB] Aggregating {len(theme_counts)} themes...")
    try:
        conn = get_connection()
        cur = conn.cursor()

        for theme_name, counts in theme_counts.items():
            freq = "High" if counts["count"] >= 10 else ("Medium" if counts["count"] >= 5 else "Low")
            cur.execute("""
                INSERT INTO themes (name, frequency, mentions, sentiment_pos, sentiment_neu, sentiment_neg)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    mentions = EXCLUDED.mentions,
                    sentiment_pos = EXCLUDED.sentiment_pos,
                    sentiment_neu = EXCLUDED.sentiment_neu,
                    sentiment_neg = EXCLUDED.sentiment_neg
            """, (theme_name, freq, counts["count"], counts["pos"], counts["neu"], counts["neg"]))

        conn.commit()
        cur.close()
        conn.close()
        print(f"  [DB] Themes aggregated and stored")
    except Exception as e:
        print(f"  [DB] Error aggregating themes: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def aggregate_sentiment(reviews: List[Dict]):
    """Calculate and store sentiment summary."""
    try:
        from database.db import get_connection
    except ImportError:
        return

    total = len(reviews)
    if total == 0:
        return

    pos = sum(1 for r in reviews if r.get("sentiment") == "positive")
    neg = sum(1 for r in reviews if r.get("sentiment") == "negative")
    neu = total - pos - neg

    pos_pct = round(pos / total * 100, 1)
    neu_pct = round(neu / total * 100, 1)
    neg_pct = round(neg / total * 100, 1)

    print(f"  [DB] Sentiment: +{pos}({pos_pct}%) ={neu}({neu_pct}%) -{neg}({neg_pct}%)")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sentiment (id, positive_count, positive_pct, neutral_count, neutral_pct,
                                   negative_count, negative_pct, total_reviews, updated_at)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                positive_count = EXCLUDED.positive_count, positive_pct = EXCLUDED.positive_pct,
                neutral_count = EXCLUDED.neutral_count, neutral_pct = EXCLUDED.neutral_pct,
                negative_count = EXCLUDED.negative_count, negative_pct = EXCLUDED.negative_pct,
                total_reviews = EXCLUDED.total_reviews, updated_at = NOW()
        """, (pos, pos_pct, neu, neu_pct, neg, neg_pct, total))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [DB] Error storing sentiment: {e}")


def store_to_discovery_engine(reviews: List[Dict]):
    """Store reviews into discovery_engine database."""
    try:
        import psycopg2
        import psycopg2.extras
        DISCOVERY_DB_URL = os.getenv("DISCOVERY_DB_URL", "postgresql://nitin:nitin@localhost:5432/discovery_engine")
        conn = psycopg2.connect(DISCOVERY_DB_URL)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scraped_reviews (
                id TEXT PRIMARY KEY, source TEXT, date DATE, platform TEXT,
                usr TEXT, location TEXT DEFAULT 'India', text TEXT,
                intent TEXT, categories TEXT[], rating SMALLINT DEFAULT 3,
                url TEXT DEFAULT '#', created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        insert_sql = """
            INSERT INTO scraped_reviews (id, source, date, platform, usr, location, text, intent, categories, rating, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, intent = EXCLUDED.intent
        """
        for r in reviews:
            try:
                cur.execute(insert_sql, (
                    r.get("id"), r.get("source"), r.get("date"), r.get("platform", "web"),
                    r.get("user", "anonymous"), r.get("location", "India"), r.get("text"),
                    r.get("intent", "observation"), r.get("categories", ["general"]),
                    r.get("rating", 3), r.get("url", "#"),
                ))
            except Exception:
                continue

        conn.commit()
        cur.close()
        conn.close()
        print(f"  [DB] Stored {len(reviews)} reviews in discovery_engine.scraped_reviews")
    except Exception as e:
        print(f"  [DB] discovery_engine storage skipped: {e}")


def log_pipeline(stats: Dict):
    """Log pipeline execution stats."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        **stats,
    }

    log_data = []
    if os.path.exists(PIPELINE_LOG):
        try:
            with open(PIPELINE_LOG, "r") as f:
                log_data = json.load(f)
        except Exception:
            log_data = []

    log_data.append(log_entry)
    log_data = log_data[-50:]

    with open(PIPELINE_LOG, "w") as f:
        json.dump(log_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Swiggy Instamart Data Pipeline")
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--sources", type=str, help="Comma-separated list of sources to scrape")
    parser.add_argument("--clean-only", action="store_true", help="Only clean existing data")
    parser.add_argument("--store-only", action="store_true", help="Only store to database")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI categorization")
    parser.add_argument("--no-db", action="store_true", help="Skip database storage")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before storing")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    all_reviews = []
    cleaned_reviews = []

    if not args.clean_only and not args.store_only:
        from scripts.scrapers import ALL_SCRAPERS

        sources_to_scrape = list(ALL_SCRAPERS.keys())
        if args.sources:
            sources_to_scrape = [s.strip() for s in args.sources.split(",")]

        print(f"\n{'='*60}")
        print(f"SCRAPING {len(sources_to_scrape)} SOURCES")
        print(f"{'='*60}\n")

        for source_name in sources_to_scrape:
            if source_name not in ALL_SCRAPERS:
                print(f"  Unknown source: {source_name}, skipping")
                continue

            scraper_class = ALL_SCRAPERS[source_name]
            scraper = scraper_class()
            print(f"\n--- Scraping: {source_name} ---")
            try:
                source_reviews = scraper.scrape()
                all_reviews.extend(source_reviews)
                print(f"  Collected: {len(source_reviews)} records")
            except Exception as e:
                print(f"  Error scraping {source_name}: {e}")

        print(f"\n{'='*60}")
        print(f"RAW TOTAL: {len(all_reviews)} records")
        print(f"{'='*60}")

        output_file = os.path.join(DATA_DIR, "live_scraped_data.json")
        with open(output_file, "w") as f:
            json.dump(all_reviews, f, indent=2)
        print(f"Saved raw data to {output_file}")

    if args.store_only:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r") as f:
                all_reviews = json.load(f)
        elif os.path.exists(CLEANED_FILE):
            with open(CLEANED_FILE, "r") as f:
                all_reviews = json.load(f)
        print(f"Loaded {len(all_reviews)} reviews from file")

    if all_reviews:
        print(f"\n{'='*60}")
        print(f"CLEANING DATA")
        print(f"{'='*60}")

        existing_ids = load_existing_ids(CLEANED_FILE)
        unique_reviews = deduplicate_reviews(all_reviews, existing_ids)
        print(f"After dedup: {len(unique_reviews)} records (removed {len(all_reviews) - len(unique_reviews)})")

        cleaned_reviews = clean_reviews(unique_reviews)
        print(f"After cleaning: {len(cleaned_reviews)} records")

        with open(CLEANED_FILE, "w") as f:
            json.dump(cleaned_reviews, f, indent=2)
        print(f"Saved cleaned data to {CLEANED_FILE}")

    if cleaned_reviews and not args.no_ai:
        print(f"\n{'='*60}")
        print(f"AI CATEGORIZATION ({len(cleaned_reviews)} reviews)")
        print(f"{'='*60}")

        cleaned_reviews = ai_categorize_batch(cleaned_reviews)

        with open(CLEANED_FILE, "w") as f:
            json.dump(cleaned_reviews, f, indent=2)
        print(f"Saved AI-enriched data to {CLEANED_FILE}")

    if cleaned_reviews and not args.no_db:
        print(f"\n{'='*60}")
        print(f"STORING TO DATABASE")
        print(f"{'='*60}")

        store_to_database(cleaned_reviews, clear_existing=args.clear)
        aggregate_themes(cleaned_reviews)
        aggregate_sentiment(cleaned_reviews)
        store_to_discovery_engine(cleaned_reviews)

    stats = {
        "total_scraped": len(all_reviews) if all_reviews else 0,
        "total_cleaned": len(cleaned_reviews) if cleaned_reviews else 0,
        "sources_scraped": len(set(r.get("source", "") for r in all_reviews)) if all_reviews else 0,
    }
    log_pipeline(stats)

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total scraped: {stats['total_scraped']}")
    print(f"  Total cleaned: {stats['total_cleaned']}")
    print(f"  Sources: {stats['sources_scraped']}")


if __name__ == "__main__":
    main()
