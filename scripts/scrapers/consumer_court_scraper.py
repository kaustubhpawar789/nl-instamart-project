"""
Consumer Complaints Court scraper - fetches complaints from consumercomplaintscourt.com.
"""
from typing import Dict, List
from .base_scraper import BaseScraper


class ConsumerCourtScraper(BaseScraper):
    SOURCE_NAME = "Consumer Complaints Court"
    PLATFORM = "web"
    RATE_LIMIT_SECONDS = 3.0

    BASE_URL = "https://consumercomplaintscourt.com"
    SEARCH_URLS = [
        "https://consumercomplaintscourt.com/?s=swiggy+instamart",
        "https://consumercomplaintscourt.com/?s=instamart",
        "https://consumercomplaintscourt.com/?s=swiggy+complaint",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape Consumer Complaints Court for Swiggy complaints."""
        reviews = []
        seen_texts = set()

        for url in self.SEARCH_URLS:
            print(f"  [ConsumerCourt] Fetching: {url}")
            soup = self._get_soup(url)
            if not soup:
                continue

            article_links = self._find_article_links(soup)
            for link in article_links[:20]:
                full_url = link if link.startswith("http") else f"{self.BASE_URL}{link}"
                print(f"  [ConsumerCourt] Fetching article: {full_url}")
                article_soup = self._get_soup(full_url)
                if article_soup:
                    review = self._parse_article(article_soup, full_url)
                    if review:
                        text_key = review["text"][:80]
                        if text_key not in seen_texts:
                            seen_texts.add(text_key)
                            reviews.append(review)

        print(f"  [ConsumerCourt] Total: {len(reviews)} unique complaints")
        return reviews

    def _find_article_links(self, soup) -> List[str]:
        """Find article links on a search results page."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.BASE_URL in href or href.startswith("/"):
                if "/swiggy" in href.lower() or "/instamart" in href.lower():
                    links.append(href)
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/20" in href and href.endswith("/"):
                    links.append(href)
        return list(set(links))

    def _parse_article(self, soup, url: str) -> Dict:
        """Parse a single complaint article."""
        title_el = soup.find("h1") or soup.find("h2")
        title = title_el.get_text(strip=True) if title_el else ""

        content_el = soup.find("div", class_=lambda c: c and ("content" in str(c).lower() or "entry" in str(c).lower()))
        if not content_el:
            content_el = soup.find("article")
        if not content_el:
            content_el = soup.find("div", class_="post-content")

        content = ""
        if content_el:
            paragraphs = content_el.find_all("p")
            content = " ".join(p.get_text(strip=True) for p in paragraphs)

        text = f"{title}. {content}" if title and content else (title or content)
        if not text or len(text) < 20:
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
            user="anonymous",
            location="India",
            rating=1,
        )
