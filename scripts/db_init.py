"""
db_init.py  —  Create/reset the discovery_engine PostgreSQL schema
Usage:  python scripts/db_init.py [--reset]
"""

import sys
import os
import json
import psycopg2
from psycopg2.extras import Json

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(ROOT, "database")

# ── Connection helper ──────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(
        host="/tmp",
        port=5432,
        user=os.environ.get("PGUSER", "nitin"),
        dbname="discovery_engine",
    )

def create_db_if_missing():
    """Connect to postgres default DB and create discovery_engine if absent."""
    conn = psycopg2.connect(host="/tmp", port=5432,
                            user=os.environ.get("PGUSER", "nitin"),
                            dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='discovery_engine'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE discovery_engine")
        print("  ✓ Created database: discovery_engine")
    else:
        print("  · Database discovery_engine already exists")
    cur.close()
    conn.close()

# ── DDL ────────────────────────────────────────────────────────────────────────
DDL = """
-- Scraped reviews from all sources
CREATE TABLE IF NOT EXISTS scraped_reviews (
    id            TEXT PRIMARY KEY,
    source        TEXT        NOT NULL,
    date          DATE        NOT NULL,
    platform      TEXT        NOT NULL,
    usr           TEXT        NOT NULL,
    location      TEXT        NOT NULL DEFAULT 'India',
    text          TEXT        NOT NULL,
    intent        TEXT        NOT NULL,
    categories    TEXT[]      NOT NULL DEFAULT '{}',
    rating        SMALLINT    NOT NULL DEFAULT 3,
    url           TEXT        NOT NULL DEFAULT '#',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reviews_source   ON scraped_reviews(source);
CREATE INDEX IF NOT EXISTS idx_reviews_intent   ON scraped_reviews(intent);
CREATE INDEX IF NOT EXISTS idx_reviews_date     ON scraped_reviews(date DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_cats     ON scraped_reviews USING GIN(categories);

-- Survey responses collected through the in-app screening form
CREATE TABLE IF NOT EXISTS survey_responses (
    id               SERIAL      PRIMARY KEY,
    respondent_name  TEXT        NOT NULL,
    email            TEXT        NOT NULL,
    city             TEXT        NOT NULL,
    age_group        TEXT        NOT NULL,
    order_frequency  TEXT        NOT NULL,
    categories       TEXT[]      NOT NULL DEFAULT '{}',
    blockers         TEXT[]      NOT NULL DEFAULT '{}',
    suggestion       TEXT        NOT NULL DEFAULT '',
    quality_score    SMALLINT    NOT NULL DEFAULT 50,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Saved custom chart configurations
CREATE TABLE IF NOT EXISTS chart_configs (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL,
    chart_type  TEXT        NOT NULL,
    x_axis      TEXT        NOT NULL,
    y_axis      TEXT        NOT NULL,
    filters     JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- KPI history snapshots (captured on every scrape)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id           SERIAL      PRIMARY KEY,
    metric_name  TEXT        NOT NULL,
    value        NUMERIC     NOT NULL,
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Scrape job log
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id           SERIAL      PRIMARY KEY,
    status       TEXT        NOT NULL DEFAULT 'running',
    records_added INTEGER     NOT NULL DEFAULT 0,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);
"""

# ── Seed data loader ──────────────────────────────────────────────────────────
def seed_reviews(cur):
    """Load the 30 curated real reviews from live_scraper.py data into DB."""
    live_path = os.path.join(DATABASE, "live_scraped_data.json")
    cleaned_path = os.path.join(DATABASE, "cleaned_feedback.json")

    records = []
    if os.path.exists(live_path):
        with open(live_path) as f:
            records.extend(json.load(f))
    if os.path.exists(cleaned_path):
        raw = json.load(open(cleaned_path))
        # cleaned_feedback has different schema — normalise
        for i, r in enumerate(raw):
            records.append({
                "id":         f"CLN-{i+1:04d}",
                "source":     r.get("source", "Unknown"),
                "date":       r.get("date", "2026-01-01"),
                "platform":   r.get("platform", "web"),
                "user":       r.get("user", "anonymous"),
                "location":   r.get("location", "India"),
                "text":       r.get("text", ""),
                "intent":     r.get("intent", "observation"),
                "categories": [r["category"]] if "category" in r else r.get("categories", []),
                "rating":     r.get("rating", 3),
                "url":        r.get("url", "#"),
            })

    inserted = 0
    for r in records:
        try:
            cur.execute("""
                INSERT INTO scraped_reviews
                    (id, source, date, platform, usr, location, text, intent, categories, rating, url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
            """, (
                r["id"], r["source"], r["date"], r["platform"],
                r.get("user","anonymous"), r.get("location","India"),
                r["text"], r["intent"],
                r.get("categories",[]), r.get("rating",3), r.get("url","#")
            ))
            inserted += cur.rowcount
        except Exception as e:
            print(f"    ⚠ Skipped {r.get('id','?')}: {e}")

    return inserted


def main():
    reset = "--reset" in sys.argv

    print("── Discovery Engine DB Init ─────────────────────────────────────")
    create_db_if_missing()

    conn = get_conn()
    conn.autocommit = False
    cur  = conn.cursor()

    if reset:
        print("  ⚠ --reset: dropping all tables…")
        cur.execute("""
            DROP TABLE IF EXISTS scraped_reviews, survey_responses,
                                 chart_configs, kpi_snapshots, scrape_jobs CASCADE
        """)
        conn.commit()

    cur.execute(DDL)
    conn.commit()
    print("  ✓ Schema ready")

    inserted = seed_reviews(cur)
    conn.commit()
    print(f"  ✓ Seeded {inserted} reviews from local JSON files")

    # Snapshot initial KPIs
    cur.execute("SELECT COUNT(*) FROM scraped_reviews"); total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT source) FROM scraped_reviews"); sources = cur.fetchone()[0]
    for metric, value in [("total_reviews", total), ("data_sources", sources)]:
        cur.execute("INSERT INTO kpi_snapshots(metric_name,value) VALUES(%s,%s)", (metric, value))
    conn.commit()

    cur.close(); conn.close()
    print(f"\n  DB: discovery_engine  |  Reviews: {total}  |  Sources: {sources}")
    print("─────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
