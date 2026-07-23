"""
Trustpilot scraper - fetches reviews from Swiggy's Trustpilot page.
Uses Google News RSS as fallback when direct scraping is blocked.
"""
import feedparser
from typing import Dict, List
from .base_scraper import BaseScraper


class TrustpilotScraper(BaseScraper):
    SOURCE_NAME = "Trustpilot"
    PLATFORM = "web"
    RATE_LIMIT_SECONDS = 3.0

    BASE_URL = "https://www.trustpilot.com/review/swiggy.com"
    SEARCH_QUERIES = [
        "site:trustpilot.com swiggy review",
        "site:trustpilot.com swiggy instamart review",
        "site:trustpilot.com swiggy complaint",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape Trustpilot reviews for Swiggy."""
        reviews = []
        seen_texts = set()

        print(f"  [Trustpilot] Trying direct scraping...")
        direct_reviews = self._scrape_direct()
        for review in direct_reviews:
            text_key = review["text"][:100]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                reviews.append(review)

        if not reviews:
            print(f"  [Trustpilot] Direct scraping blocked, using Google News RSS...")
            for query in self.SEARCH_QUERIES:
                print(f"  [Trustpilot] Searching: {query}")
                rss_reviews = self._search_google_news(query)
                for review in rss_reviews:
                    text_key = review["text"][:100]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        reviews.append(review)

        print(f"  [Trustpilot] Total: {len(reviews)} unique reviews")
        return reviews

    def _scrape_direct(self) -> List[Dict]:
        """Try direct scraping of Trustpilot."""
        reviews = []
        try:
            soup = self._get_soup(f"{self.BASE_URL}?page=1")
            if not soup:
                return reviews

            page_reviews = self._parse_reviews_page(soup)
            for review in page_reviews[:5]:
                reviews.append(review)
        except Exception:
            pass
        return reviews

    def _search_google_news(self, query: str) -> List[Dict]:
        """Search for Trustpilot reviews via Google News RSS."""
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

            date = self.normalize_date(published)

            record = self._make_record(
                text=text,
                url=link,
                date=date,
                user="Trustpilot User",
                location="India",
                rating=2,
            )
            reviews.append(record)

        return reviews

    def _parse_reviews_page(self, soup) -> List[Dict]:
        """Parse a Trustpilot reviews page."""
        reviews = []
        review_cards = soup.find_all("article", {"class": "paper_paper__1PY90"})

        if not review_cards:
            review_cards = soup.find_all("section", {"data-service-review-card-paper": "true"})

        if not review_cards:
            review_cards = soup.find_all("article")

        for card in review_cards:
            try:
                review = self._parse_review_card(card)
                if review and review["text"] and len(review["text"]) > 10:
                    reviews.append(review)
            except Exception:
                continue

        return reviews

    def _parse_review_card(self, card) -> Dict:
        """Parse a single Trustpilot review card."""
        text_el = card.find("p", {"data-service-review-text-typography": "true"})
        if not text_el:
            text_el = card.find("p", class_=lambda c: c and "reviewContent" in str(c))
        if not text_el:
            text_p = card.find_all("p")
            text_el = text_p[-1] if text_p else None

        text = text_el.get_text(strip=True) if text_el else ""
        if not text:
            return None

        date_el = card.find("time")
        date = None
        if date_el:
            date = date_el.get("datetime") or date_el.get_text(strip=True)
            date = self.normalize_date(date)

        import re
        rating_el = card.find("img", alt=lambda a: a and "Rated" in str(a))
        rating = None
        if rating_el:
            alt = rating_el.get("alt", "")
            match = re.search(r"Rated (\d) out of", alt)
            if match:
                rating = int(match.group(1))

        title_el = card.find("h2")
        title = title_el.get_text(strip=True) if title_el else ""
        full_text = f"{title}. {text}" if title else text

        user_el = card.find("span", {"data-consumer-name-typography": "true"})
        if not user_el:
            user_el = card.find("a", {"data-consumer-profile-typography": "true"})
        user = user_el.get_text(strip=True) if user_el else "anonymous"

        location_el = card.find("span", {"data-consumer-country-typography": "true"})
        location = location_el.get_text(strip=True) if location_el else "India"

        record = self._make_record(
            text=full_text,
            url=self.BASE_URL,
            date=date,
            user=user,
            location=location,
            rating=rating,
        )
        return record
