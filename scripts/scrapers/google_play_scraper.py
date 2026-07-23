"""
Google Play Store scraper - fetches reviews using google-play-scraper library.
"""
from typing import Dict, List
from .base_scraper import BaseScraper


class GooglePlayScraper(BaseScraper):
    SOURCE_NAME = "Google Play Store"
    PLATFORM = "android"
    RATE_LIMIT_SECONDS = 2.0

    PACKAGE_NAME = "in.swiggy.android"
    MAX_REVIEWS = 500

    def scrape(self) -> List[Dict]:
        """Scrape Google Play Store reviews for Swiggy."""
        reviews = []
        seen_texts = set()

        try:
            from google_play_scraper import Sort, reviews as gp_reviews
        except ImportError:
            print("  [Google Play] google-play-scraper not installed. Run: pip install google-play-scraper")
            return reviews

        print(f"  [Google Play] Fetching reviews for {self.PACKAGE_NAME}...")

        try:
            result, continuation_token = gp_reviews(
                self.PACKAGE_NAME,
                lang="en",
                country="in",
                sort=Sort.NEWEST,
                count=200,
                filter_score_with=None,
            )

            for r in result:
                review = self._parse_review(r)
                if review:
                    text_key = review["text"][:80]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        reviews.append(review)

            if continuation_token:
                try:
                    page = 2
                    print(f"  [Google Play] Fetching page {page}...")
                    result2, _ = gp_reviews(
                        self.PACKAGE_NAME,
                        lang="en",
                        country="in",
                        sort=Sort.NEWEST,
                        count=200,
                        continuation_token=continuation_token,
                    )
                    for r in result2:
                        review = self._parse_review(r)
                        if review:
                            text_key = review["text"][:80]
                            if text_key not in seen_texts:
                                seen_texts.add(text_key)
                                reviews.append(review)
                except Exception:
                    pass

        except Exception as e:
            print(f"  [Google Play] Error: {e}")

        print(f"  [Google Play] Total: {len(reviews)} unique reviews")
        return reviews

    def _parse_review(self, r: dict) -> Dict:
        """Parse a single Google Play review."""
        text = r.get("content", "").strip()
        if not text or len(text) < 10:
            return None

        score = r.get("score", 3)
        at = r.get("at")
        date = None
        if at:
            try:
                date = at.strftime("%Y-%m-%d")
            except Exception:
                pass

        user = r.get("userName", "anonymous")
        version = r.get("reviewCreatedVersion", "")

        record = self._make_record(
            text=text,
            url=f"https://play.google.com/store/apps/details?id={self.PACKAGE_NAME}&hl=en&gl=in",
            date=date,
            user=user,
            location="India",
            rating=score,
        )
        return record
