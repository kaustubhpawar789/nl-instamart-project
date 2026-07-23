"""
Apple App Store scraper - fetches reviews using iTunes Search/RSS API.
"""
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List
from .base_scraper import BaseScraper


class AppleStoreScraper(BaseScraper):
    SOURCE_NAME = "Apple App Store"
    PLATFORM = "ios"
    RATE_LIMIT_SECONDS = 2.0

    APP_ID = "989540920"
    RSS_BASE = "https://itunes.apple.com/in/rss/customerreviews/id={app_id}/page={page}/sortby=mostRecent/json"
    MAX_PAGES = 10

    def scrape(self) -> List[Dict]:
        """Scrape Apple App Store reviews for Swiggy."""
        reviews = []
        seen_texts = set()

        for page in range(1, self.MAX_PAGES + 1):
            url = self.RSS_BASE.format(app_id=self.APP_ID, page=page)
            print(f"  [Apple Store] Fetching page {page}")
            resp = self._get(url, use_default_headers=True)
            if not resp:
                continue

            try:
                data = resp.json()
                entries = data.get("feed", {}).get("entry", [])
                if not entries:
                    print(f"  [Apple Store] No more entries on page {page}, stopping")
                    break

                for entry in entries:
                    review = self._parse_entry(entry)
                    if review:
                        text_key = review["text"][:80]
                        if text_key not in seen_texts:
                            seen_texts.add(text_key)
                            reviews.append(review)
            except Exception as e:
                print(f"  [Apple Store] Parse error on page {page}: {e}")
                continue

        print(f"  [Apple Store] Total: {len(reviews)} unique reviews")
        return reviews

    def _parse_entry(self, entry: dict) -> Dict:
        """Parse a single App Store review entry."""
        text = entry.get("content", {}).get("label", "")
        if not text or len(text) < 10:
            return None

        title = entry.get("title", {}).get("label", "")
        if title and title != text[:len(title)]:
            text = f"{title}. {text}"

        rating = None
        rating_str = entry.get("im:rating", {}).get("label", "")
        if rating_str:
            try:
                rating = int(rating_str)
            except ValueError:
                pass

        user = entry.get("author", {}).get("name", {}).get("label", "anonymous")
        date_str = entry.get("updated", {}).get("label", "")
        date = self.normalize_date(date_str)

        version = entry.get("im:version", {}).get("label", "")

        record = self._make_record(
            text=text,
            url=f"https://apps.apple.com/in/app/swiggy-food-instamart-dineout/id{self.APP_ID}",
            date=date,
            user=user,
            location="India",
            rating=rating,
        )
        return record
