"""
ConsumerComplaints.in scraper - fetches complaints about Swiggy Instamart.
"""
from typing import Dict, List
from .base_scraper import BaseScraper


class ConsumerComplaintsScraper(BaseScraper):
    SOURCE_NAME = "ConsumerComplaints.in"
    PLATFORM = "web"
    RATE_LIMIT_SECONDS = 3.0

    URLS = [
        "https://consumercomplaints.in/bycompany/swiggy-instamart-a614346.html",
        "https://consumercomplaints.in/bycompany/instamart-a621096.html",
        "https://consumercomplaints.in/search?q=swiggy+instamart",
        "https://consumercomplaints.in/search?q=instamart",
    ]

    def scrape(self) -> List[Dict]:
        """Scrape ConsumerComplaints.in for Swiggy Instamart complaints."""
        reviews = []
        seen_texts = set()

        for url in self.URLS:
            print(f"  [ConsumerComplaints] Fetching: {url}")
            soup = self._get_soup(url)
            if not soup:
                continue

            page_reviews = self._parse_complaints_page(soup, url)
            for review in page_reviews:
                text_key = review["text"][:80]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    reviews.append(review)

        print(f"  [ConsumerComplaints] Total: {len(reviews)} unique complaints")
        return reviews

    def _parse_complaints_page(self, soup, base_url: str) -> List[Dict]:
        """Parse a ConsumerComplaints.in page."""
        reviews = []

        complaint_divs = soup.find_all("div", class_=lambda c: c and "complaint" in str(c).lower())
        if not complaint_divs:
            complaint_divs = soup.find_all("article")
        if not complaint_divs:
            complaint_divs = soup.find_all("div", class_="post-content")

        for div in complaint_divs:
            try:
                review = self._parse_single_complaint(div, base_url)
                if review and review["text"] and len(review["text"]) > 20:
                    reviews.append(review)
            except Exception:
                continue

        if not reviews:
            links = soup.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                if "/complaint/" in href or "/review/" in href:
                    full_url = href if href.startswith("http") else f"https://consumercomplaints.in{href}"
                    sub_soup = self._get_soup(full_url)
                    if sub_soup:
                        sub_reviews = self._parse_single_post(sub_soup, full_url)
                        reviews.extend(sub_reviews)

        return reviews

    def _parse_single_complaint(self, div, base_url: str) -> Dict:
        """Parse a single complaint from a page."""
        title_el = div.find(["h2", "h3", "h4", "a"])
        title = title_el.get_text(strip=True) if title_el else ""

        body_el = div.find("p") or div.find("div", class_="complaint-text")
        body = body_el.get_text(strip=True) if body_el else ""

        text = f"{title}. {body}" if title and body else (title or body)
        if not text or len(text) < 20:
            return None

        date_el = div.find("time") or div.find("span", class_=lambda c: c and "date" in str(c).lower())
        date = None
        if date_el:
            date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            date = self.normalize_date(date_text)

        user_el = div.find("a", class_=lambda c: c and "author" in str(c).lower())
        if not user_el:
            user_el = div.find("span", class_=lambda c: c and "user" in str(c).lower())
        user = user_el.get_text(strip=True) if user_el else "anonymous"

        link = div.find("a", href=True)
        url = base_url
        if link and link.get("href"):
            href = link["href"]
            url = href if href.startswith("http") else f"https://consumercomplaints.in{href}"

        return self._make_record(
            text=text,
            url=url,
            date=date,
            user=user,
            location="India",
            rating=1,
        )

    def _parse_single_post(self, soup, url: str) -> List[Dict]:
        """Parse a single complaint post page."""
        reviews = []
        content = soup.find("div", class_=lambda c: c and ("content" in str(c).lower() or "body" in str(c).lower()))
        if not content:
            content = soup.find("article")

        if content:
            text = content.get_text(strip=True)
            if text and len(text) > 20:
                date_el = soup.find("time")
                date = None
                if date_el:
                    date_text = date_el.get("datetime") or date_el.get_text(strip=True)
                    date = self.normalize_date(date_text)

                user_el = soup.find("a", class_=lambda c: c and "author" in str(c).lower())
                user = user_el.get_text(strip=True) if user_el else "anonymous"

                reviews.append(self._make_record(
                    text=text,
                    url=url,
                    date=date,
                    user=user,
                    location="India",
                    rating=1,
                ))

        return reviews
