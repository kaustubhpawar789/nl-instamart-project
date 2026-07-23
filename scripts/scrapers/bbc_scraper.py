"""
BBC scraper - fetches news articles about Swiggy/quick commerce from BBC.
"""
import feedparser
from typing import Dict, List
from .base_scraper import BaseScraper


class BBCScraper(BaseScraper):
    SOURCE_NAME = "BBC"
    PLATFORM = "news"
    RATE_LIMIT_SECONDS = 2.0

    SEARCH_QUERIES = [
        "swiggy instamart india",
        "swiggy quick commerce india",
        "india quick commerce delivery",
        "swiggy dark store india",
        "instamart complaints india",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape BBC for Swiggy/quick commerce news."""
        reviews = []
        seen_texts = set()

        for query in self.SEARCH_QUERIES:
            print(f"  [BBC] Searching: {query}")
            articles = self._search_bbc(query)
            for article in articles:
                text_key = article["text"][:80]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    reviews.append(article)

        print(f"  [BBC] Total: {len(reviews)} articles")
        return reviews

    def _search_bbc(self, query: str) -> List[Dict]:
        """Search BBC using Google News RSS."""
        reviews = []
        rss_url = f"https://news.google.com/rss/search?q=site:bbc.com+{query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"

        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")

            text = f"{title}. {summary}" if summary else title
            if not text or len(text) < 20:
                continue

            date = self.normalize_date(published)

            reviews.append(self._make_record(
                text=text,
                url=link,
                date=date,
                user="BBC Reporter",
                location="India",
                rating=3,
            ))

        return reviews
