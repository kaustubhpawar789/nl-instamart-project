"""
Migration script: loads JSON data into Postgres.

Usage:
    export DATABASE_URL="postgresql://..."
    python database/migrate.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database.db import get_connection


def run_migration():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: Set DATABASE_URL environment variable")
        print("  export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        sys.exit(1)

    conn = get_connection()
    cur = conn.cursor()

    print("Running schema...")
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r") as f:
        cur.execute(f.read())
    conn.commit()
    print("  Schema created.")

    _load_sentiment(cur)
    _load_themes(cur)
    _load_insights(cur)
    _load_categories(cur)
    _load_research(cur)
    _load_live_reviews(cur)
    _load_cleaned_feedback(cur)

    conn.commit()
    cur.close()
    conn.close()
    print("\nMigration complete.")


def _load_sentiment(cur):
    path = os.path.join(ROOT, "database", "ai_insights.json")
    if not os.path.exists(path):
        print("  Skipping sentiment (ai_insights.json not found)")
        return
    with open(path) as f:
        data = json.load(f)
    s = data["sentiment"]
    cur.execute("""
        INSERT INTO sentiment (id, positive_count, positive_pct, neutral_count, neutral_pct,
                               negative_count, negative_pct, total_reviews)
        VALUES (1, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            positive_count=EXCLUDED.positive_count, positive_pct=EXCLUDED.positive_pct,
            neutral_count=EXCLUDED.neutral_count, neutral_pct=EXCLUDED.neutral_pct,
            negative_count=EXCLUDED.negative_count, negative_pct=EXCLUDED.negative_pct,
            total_reviews=EXCLUDED.total_reviews, updated_at=NOW()
    """, (s["positive"]["count"], s["positive"]["percentage"],
          s["neutral"]["count"], s["neutral"]["percentage"],
          s["negative"]["count"], s["negative"]["percentage"],
          data["total_reviews_analyzed"]))
    print("  Sentiment loaded.")


def _load_themes(cur):
    path = os.path.join(ROOT, "database", "ai_insights.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)

    for theme in data["themes"]:
        cur.execute("""
            INSERT INTO themes (name, frequency, mentions, sentiment_pos, sentiment_neu, sentiment_neg)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                frequency=EXCLUDED.frequency, mentions=EXCLUDED.mentions,
                sentiment_pos=EXCLUDED.sentiment_pos, sentiment_neu=EXCLUDED.sentiment_neu,
                sentiment_neg=EXCLUDED.sentiment_neg
            RETURNING id
        """, (theme["name"], theme["frequency"], theme["mentions"],
              theme["sentiment"]["positive"], theme["sentiment"]["neutral"],
              theme["sentiment"]["negative"]))
        theme_id = cur.fetchone()[0]

        cur.execute("DELETE FROM theme_evidence WHERE theme_id=%s", (theme_id,))
        cur.execute("DELETE FROM theme_blockers WHERE theme_id=%s", (theme_id,))
        cur.execute("DELETE FROM theme_triggers WHERE theme_id=%s", (theme_id,))
        cur.execute("DELETE FROM theme_categories WHERE theme_id=%s", (theme_id,))

        for ev in theme["evidence"]:
            cur.execute("""
                INSERT INTO theme_evidence (theme_id, quote, source, category)
                VALUES (%s, %s, %s, %s)
            """, (theme_id, ev["quote"], ev["source"], ev.get("category")))

        for bl in theme["blockers"]:
            cur.execute("INSERT INTO theme_blockers (theme_id, blocker) VALUES (%s, %s)",
                        (theme_id, bl))

        for tr in theme["triggers"]:
            cur.execute("INSERT INTO theme_triggers (theme_id, trigger_text) VALUES (%s, %s)",
                        (theme_id, tr))

        for cat in theme["categories"]:
            cur.execute("INSERT INTO theme_categories (theme_id, category) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (theme_id, cat))

    print(f"  {len(data['themes'])} themes loaded.")


def _load_insights(cur):
    path = os.path.join(ROOT, "database", "ai_insights.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)

    for ins in data["insights"]:
        cur.execute("""
            INSERT INTO insights (title, observation, user_need, root_cause, opportunity, implication)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (title) DO UPDATE SET
                observation=EXCLUDED.observation, user_need=EXCLUDED.user_need,
                root_cause=EXCLUDED.root_cause, opportunity=EXCLUDED.opportunity,
                implication=EXCLUDED.implication
        """, (ins["title"], ins["observation"], ins["user_need"],
              ins["root_cause"], ins["opportunity"], ins["implication"]))
    print(f"  {len(data['insights'])} insights loaded.")


def _load_categories(cur):
    path = os.path.join(ROOT, "database", "ai_insights.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)

    for cat in data["categories"]:
        cur.execute("""
            INSERT INTO categories (name, mentions, gap_severity, business_impact)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                mentions=EXCLUDED.mentions, gap_severity=EXCLUDED.gap_severity,
                business_impact=EXCLUDED.business_impact
        """, (cat["name"], cat["mentions"], cat["gap_severity"], cat["business_impact"]))
    print(f"  {len(data['categories'])} categories loaded.")


def _load_research(cur):
    path = os.path.join(ROOT, "database", "ai_insights.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)

    for r in data.get("mock_research_data", []):
        cur.execute("""
            INSERT INTO research_data (respondent_id, summary, matched_themes, quality_score, recommendation)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (respondent_id) DO UPDATE SET
                summary=EXCLUDED.summary, matched_themes=EXCLUDED.matched_themes,
                quality_score=EXCLUDED.quality_score, recommendation=EXCLUDED.recommendation
        """, (r["respondent_id"], r["summary"], r["matched_themes"],
              r["quality_score"], r["recommendation"]))
    print(f"  {len(data.get('mock_research_data', []))} research entries loaded.")


def _load_live_reviews(cur):
    path = os.path.join(ROOT, "database", "live_scraped_data.json")
    if not os.path.exists(path):
        print("  Skipping live reviews (file not found)")
        return
    with open(path) as f:
        data = json.load(f)

    for r in data:
        cur.execute("""
            INSERT INTO reviews (id, source, date, platform, user_name, location, text,
                                 intent, categories, rating, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                source=EXCLUDED.source, date=EXCLUDED.date, platform=EXCLUDED.platform,
                user_name=EXCLUDED.user_name, location=EXCLUDED.location, text=EXCLUDED.text,
                intent=EXCLUDED.intent, categories=EXCLUDED.categories,
                rating=EXCLUDED.rating, url=EXCLUDED.url
        """, (r["id"], r["source"], r["date"], r.get("platform"),
              r.get("user"), r.get("location"), r["text"],
              r["intent"], r["categories"], r["rating"], r.get("url")))
    print(f"  {len(data)} live reviews loaded.")


def _load_cleaned_feedback(cur):
    path = os.path.join(ROOT, "database", "cleaned_feedback.json")
    if not os.path.exists(path):
        print("  Skipping cleaned feedback (file not found)")
        return
    with open(path) as f:
        data = json.load(f)

    count = 0
    for i, r in enumerate(data, 1):
        review_id = f"FB-{i:04d}"
        cat = r.get("category", "general")
        cats = [cat] if isinstance(cat, str) else cat
        cur.execute("""
            INSERT INTO reviews (id, source, date, platform, user_name, text,
                                 intent, categories, rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (review_id, r["source"], r["date"], r.get("platform"),
              None, r["text"], r["intent"], cats, None))
        count += 1
    print(f"  {count} cleaned feedback records loaded.")


if __name__ == "__main__":
    run_migration()
