"""
Indian Food Times scraper - fetches news articles about food industry and quick commerce.
"""
import feedparser
from typing import Dict, List
from .base_scraper import BaseScraper


class IndianFoodTimesScraper(BaseScraper):
    SOURCE_NAME = "Indian Food Times"
    PLATFORM = "news"
    RATE_LIMIT_SECONDS = 2.0

    BASE_URL = "https://indianfoodtimes.com"
    SEARCH_QUERIES = [
        "swiggy instamart",
        "quick commerce india",
        "swiggy complaints",
        "instamart dark patterns",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape Indian Food Times for food industry news."""
        reviews = []
        seen_texts = set()

        for query in self.SEARCH_QUERIES:
            print(f"  [IndianFoodTimes] Searching: {query}")
            articles = self._search_articles(query)
            for article in articles:
                text_key = article["text"][:80]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    reviews.append(article)

        print(f"  [IndianFoodTimes] Total: {len(reviews)} articles")
        return reviews

    def _search_articles(self, query: str) -> List[Dict]:
        """Search for articles."""
        reviews = []

        soup = self._get_soup(f"{self.BASE_URL}/?s={query.replace(' ', '+')}")
        if not soup:
            return reviews

        article_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.BASE_URL in href and "/20" in href:
                article_links.append(href)

        for link in list(set(article_links))[:5]:
            print(f"  [IndianFoodTimes] Fetching: {link}")
            article_soup = self._get_soup(link)
            if article_soup:
                review = self._parse_article(article_soup, link)
                if review:
                    reviews.append(review)

        rss_url = f"https://news.google.com/rss/search?q=site:indianfoodtimes.com+{query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
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
                user="Indian Food Times",
                location="India",
                rating=3,
            ))

        return reviews

    def _parse_article(self, soup, url: str) -> Dict:
        """Parse a single article."""
        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        content_el = soup.find("div", class_=lambda c: c and ("content" in str(c).lower() or "entry" in str(c).lower() or "article" in str(c).lower()))
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
            user="Indian Food Times",
            location="India",
            rating=3,
        )
