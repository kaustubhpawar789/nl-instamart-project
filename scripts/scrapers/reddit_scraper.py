"""
Reddit scraper - fetches posts and comments about Swiggy/Instamart.
Uses Google News RSS as primary source since Reddit JSON API is blocked.
"""
import feedparser
import re
from typing import Dict, List
from .base_scraper import BaseScraper


class RedditScraper(BaseScraper):
    SOURCE_NAME = "Reddit"
    PLATFORM = "reddit"
    RATE_LIMIT_SECONDS = 2.0

    SEARCH_QUERIES = [
        "site:reddit.com swiggy instamart",
        "site:reddit.com swiggy instamart complaint",
        "site:reddit.com swiggy instamart delivery",
        "site:reddit.com swiggy instamart refund",
        "site:reddit.com swiggy instamart expired",
        "site:reddit.com instamart review india",
        "site:reddit.com instamart missing items",
        "site:reddit.com instamart customer service",
        "site:reddit.com r/swiggy instamart",
        "site:reddit.com r/LegalAdviceIndia swiggy",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape Reddit for Swiggy/Instamart mentions via Google News RSS."""
        reviews = []
        seen_texts = set()

        for query in self.SEARCH_QUERIES:
            print(f"  [Reddit] Searching: {query}")
            articles = self._search_google_news(query)
            for article in articles:
                text_key = article["text"][:80]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    reviews.append(article)

        print(f"  [Reddit] Total: {len(reviews)} unique records")
        return reviews

    def _search_google_news(self, query: str) -> List[Dict]:
        """Search for Reddit posts via Google News RSS."""
        reviews = []
        rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"

        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")

            text = f"{title}. {summary}" if summary else title
            if not text or len(text) < 20:
                continue

            if not self.is_swiggy_related(text):
                continue

            date = self.normalize_date(published)
            subreddit = self._extract_subreddit(link, text)

            record = self._make_record(
                text=text,
                url=link,
                date=date,
                user="Reddit User",
                location="India",
                rating=2,
            )
            record["source"] = f"Reddit {subreddit}"
            reviews.append(record)

        return reviews

    @staticmethod
    def _extract_subreddit(url: str, text: str) -> str:
        """Extract subreddit name from URL or text."""
        url_lower = url.lower()
        text_lower = text.lower()

        subreddits = [
            "r/swiggy", "r/LegalAdviceIndia", "r/india", "r/Bangalore",
            "r/mumbai", "r/delhi", "r/hyderabad", "r/chennai", "r/pune",
            "r/kolkata", "r/IndianStreetBazaar",
        ]

        for sub in subreddits:
            if sub.lower() in url_lower or sub.lower() in text_lower:
                return sub

        if "swiggy" in text_lower:
            return "r/swiggy"
        return "r/india"
