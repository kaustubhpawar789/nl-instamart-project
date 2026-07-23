"""
Database Cleanup Script - Clears all mock/stale data from database tables.

Usage:
    python scripts/clear_database.py              # Clear instamart database
    python scripts/clear_database.py --all        # Clear both instamart and discovery_engine
    python scripts/clear_database.py --discovery  # Clear discovery_engine only
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))


def clear_instamart_db():
    """Clear all tables in the instamart database."""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()

        print("[instamart] Clearing Phase 1 tables...")
        cur.execute("""
            TRUNCATE TABLE
                theme_categories, theme_triggers, theme_blockers, theme_evidence,
                themes, insights, research_data, reviews, sentiment
                CASCADE
        """)

        print("[instamart] Clearing Phase 2 tables...")
        try:
            cur.execute("""
                TRUNCATE TABLE
                    workflow_outputs, test_data, tickets, feedback,
                    recommendations, products, users
                    CASCADE
            """)
        except Exception as e:
            print(f"  [instamart] Phase 2 tables skip: {e}")
            conn.rollback()
            conn = get_connection()
            cur = conn.cursor()

        print("[instamart] Clearing categories table...")
        try:
            cur.execute("DELETE FROM categories")
        except Exception as e:
            print(f"  [instamart] Categories skip: {e}")

        conn.commit()
        cur.close()
        conn.close()
        print("[instamart] All tables cleared successfully")
        return True
    except Exception as e:
        print(f"[instamart] Error: {e}")
        return False


def clear_discovery_engine_db():
    """Clear all tables in the discovery_engine database."""
    try:
        import psycopg2
        DISCOVERY_DB_URL = os.getenv("DISCOVERY_DB_URL", "postgresql://nitin:nitin@localhost:5432/discovery_engine")
        conn = psycopg2.connect(DISCOVERY_DB_URL)
        cur = conn.cursor()

        tables = [
            "scrape_jobs", "kpi_snapshots", "chart_configs",
            "survey_responses", "scraped_reviews",
        ]

        for table in tables:
            try:
                cur.execute(f"DELETE FROM {table}")
                print(f"  [discovery_engine] Cleared {table}")
            except Exception as e:
                print(f"  [discovery_engine] Skip {table}: {e}")
                conn.rollback()
                conn = psycopg2.connect(DISCOVERY_DB_URL)
                cur = conn.cursor()

        conn.commit()
        cur.close()
        conn.close()
        print("[discovery_engine] All tables cleared successfully")
        return True
    except Exception as e:
        print(f"[discovery_engine] Error: {e}")
        return False


def clear_json_files():
    """Clear JSON data files with correct default types."""
    import json as _json
    data_dir = os.path.join(ROOT, "database")

    files_to_clear = {
        "live_scraped_data.json": [],
        "cleaned_feedback.json": [],
        "chart_configs.json": [],
        "survey_responses.json": [],
        "scrape_status.json": {"running": False, "added": 0, "error": None, "started_at": None, "finished_at": None},
        "ai_insights.json": {
            "themes": [],
            "insights": [],
            "sentiment": {"positive": {"count": 0, "percentage": 0}, "neutral": {"count": 0, "percentage": 0}, "negative": {"count": 0, "percentage": 0}},
            "categories": [],
        },
    }

    for filename, default_val in files_to_clear.items():
        filepath = os.path.join(data_dir, filename)
        with open(filepath, "w") as f:
            _json.dump(default_val, f, indent=2)
        print(f"  [JSON] Cleared {filename}")


def main():
    parser = argparse.ArgumentParser(description="Clear database tables")
    parser.add_argument("--all", action="store_true", help="Clear both databases and JSON files")
    parser.add_argument("--discovery", action="store_true", help="Clear discovery_engine only")
    parser.add_argument("--json-only", action="store_true", help="Clear JSON files only")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("DATABASE CLEANUP")
    print("="*60 + "\n")

    if args.json_only:
        clear_json_files()
    elif args.all:
        clear_instamart_db()
        clear_discovery_engine_db()
        clear_json_files()
    elif args.discovery:
        clear_discovery_engine_db()
    else:
        clear_instamart_db()

    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
