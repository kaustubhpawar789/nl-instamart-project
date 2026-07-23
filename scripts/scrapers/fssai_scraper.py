"""
FSSAI Report scraper - fetches news about FSSAI notices and food safety issues.
"""
import feedparser
from typing import Dict, List
from .base_scraper import BaseScraper


class FSSAIScraper(BaseScraper):
    SOURCE_NAME = "FSSAI Report"
    PLATFORM = "news"
    RATE_LIMIT_SECONDS = 2.0

    NEWS_SOURCES = [
        {
            "name": "The Hindu Business Line",
            "url": "https://www.thehindubusinessline.com/companies/food-standards-authority-issues-9-notices-to-swiggy-instamart-over-consumer-complaints/article71209786.ece",
            "type": "article",
        },
        {
            "name": "Economic Times",
            "search": "swiggy instamart fssai notice",
            "type": "search",
        },
        {
            "name": "NDTV",
            "search": "swiggy instamart food safety fssai",
            "type": "search",
        },
        {
            "name": "Times of India",
            "search": "fssai swiggy instamart expired products",
            "type": "search",
        },
        {
            "name": "Moneycontrol",
            "search": "swiggy instamart fssai food safety",
            "type": "search",
        },
    ]

    def scrape(self) -> List[Dict]:
        """Scrape FSSAI-related news about Swiggy Instamart."""
        reviews = []
        seen_texts = set()

        for source in self.NEWS_SOURCES:
            print(f"  [FSSAI] Fetching from: {source['name']}")
            if source.get("type") == "article":
                review = self._fetch_article(source["url"], source["name"])
                if review:
                    text_key = review["text"][:80]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        reviews.append(review)
            elif source.get("type") == "search":
                search_reviews = self._search_news(source["search"], source["name"])
                for r in search_reviews:
                    text_key = r["text"][:80]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        reviews.append(r)

        print(f"  [FSSAI] Total: {len(reviews)} articles")
        return reviews

    def _fetch_article(self, url: str, source_name: str) -> Dict:
        """Fetch a single news article."""
        soup = self._get_soup(url)
        if not soup:
            return None

        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        content_el = soup.find("div", class_=lambda c: c and ("article" in str(c).lower() or "story" in str(c).lower() or "content" in str(c).lower()))
        if not content_el:
            content_el = soup.find("article")

        content = ""
        if content_el:
            paragraphs = content_el.find_all("p")
            content = " ".join(p.get_text(strip=True) for p in paragraphs[:10])

        text = f"{title}. {content}" if title and content else (title or content)
        if not text or len(text) < 30:
            return None

        date_el = soup.find("time") or soup.find("span", class_=lambda c: c and "date" in str(c).lower())
        date = None
        if date_el:
            date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            date = self.normalize_date(date_text)

        return self._make_record(
            text=text,
            url=url,
            date=date,
            user=source_name,
            location="New Delhi",
            rating=2,
        )

    def _search_news(self, query: str, source_name: str) -> List[Dict]:
        """Search for news articles using Google News RSS."""
        reviews = []
        rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"

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
                user=source_name,
                location="India",
                rating=2,
            ))

        return reviews
