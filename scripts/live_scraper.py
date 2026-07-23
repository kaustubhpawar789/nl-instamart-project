"""
Swiggy Instamart Live Scraper - Main Entry Point

Scrapes real user reviews and feedback from multiple sources:
- Reddit (r/swiggy, r/LegalAdviceIndia, r/india)
- Trustpilot
- Apple App Store
- ConsumerComplaints.in
- Consumer Complaints Court
- FSSAI Reports
- BBC
- Indian Food Times
- Digital in Asia
- Confetti Design

Usage:
    python scripts/live_scraper.py --all              # Scrape all sources
    python scripts/live_scraper.py --sources reddit,trustpilot  # Specific sources
    python scripts/live_scraper.py --clear            # Clear DB and scrape fresh
    python scripts/live_scraper.py --no-ai            # Skip AI categorization
    python scripts/live_scraper.py --no-db            # Skip database storage

Environment:
    GROQ_API_KEY      - Required for AI categorization
    DATABASE_URL      - PostgreSQL connection URL
"""
import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

DATA_DIR = os.path.join(ROOT, "database")
OUTPUT_FILE = os.path.join(DATA_DIR, "live_scraped_data.json")


def main():
    parser = argparse.ArgumentParser(
        description="Swiggy Instamart Live Scraper - Scrape real user reviews from multiple sources"
    )
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--sources", type=str, help="Comma-separated list of sources (e.g., reddit,trustpilot)")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before scraping")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI categorization")
    parser.add_argument("--no-db", action="store_true", help="Skip database storage")
    parser.add_argument("--list-sources", action="store_true", help="List all available sources")
    args = parser.parse_args()

    if args.list_sources:
        from scripts.scrapers import ALL_SCRAPERS
        print("\nAvailable scraping sources:")
        print("-" * 40)
        for name, cls in ALL_SCRAPERS.items():
            print(f"  {name:25s} - {cls.SOURCE_NAME}")
        print()
        return

    from scripts.data_pipeline import main as pipeline_main

    pipeline_args = []
    if args.all:
        pipeline_args.append("--all")
    if args.sources:
        pipeline_args.extend(["--sources", args.sources])
    if args.clear:
        pipeline_args.append("--clear")
    if args.no_ai:
        pipeline_args.append("--no-ai")
    if args.no_db:
        pipeline_args.append("--no-db")

    if not any([args.all, args.sources]):
        pipeline_args.append("--all")

    sys.argv = ["data_pipeline.py"] + pipeline_args
    pipeline_main()


if __name__ == "__main__":
    main()
