"""
Abstract base scraper class with common functionality.
"""
import hashlib
import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

SWIGGY_KEYWORDS = [
    "swiggy", "instamart", "swiggy instamart", "swiggy instamart",
    "swiggy delivery", "swiggy order", "swiggy food", "swiggy complaint",
]


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    SOURCE_NAME: str = "unknown"
    PLATFORM: str = "web"
    RATE_LIMIT_SECONDS: float = 2.0

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            time.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, use_default_headers: bool = False, **kwargs) -> Optional[requests.Response]:
        """Make a GET request with rate limiting and error handling."""
        self._rate_limit()
        try:
            if use_default_headers:
                resp = requests.get(url, timeout=30, **kwargs)
            else:
                resp = self.session.get(url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"  [ERROR] {self.SOURCE_NAME}: Failed to fetch {url}: {e}")
            return None

    def _get_soup(self, url: str, parser: str = "lxml") -> Optional[BeautifulSoup]:
        """Fetch a URL and return BeautifulSoup object."""
        resp = self._get(url)
        if resp:
            return BeautifulSoup(resp.text, parser)
        return None

    @staticmethod
    def make_id(text: str, prefix: str = "REV") -> str:
        """Generate a deterministic ID from text content."""
        hash_val = hashlib.md5(text.encode("utf-8")).hexdigest()[:8].upper()
        return f"{prefix}-{hash_val}"

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        text = text.strip()
        text = " ".join(text.split())
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        return text

    @staticmethod
    def normalize_date(date_str: str) -> Optional[str]:
        """Try to parse various date formats into YYYY-MM-DD."""
        if not date_str:
            return None
        formats = [
            "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
            "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y",
            "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def is_swiggy_related(text: str) -> bool:
        """Check if text mentions Swiggy/Instamart."""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in SWIGGY_KEYWORDS)

    @staticmethod
    def determine_intent(text: str) -> str:
        """Determine the intent of a review based on keywords."""
        text_lower = text.lower()
        complaint_words = [
            "complaint", "worst", "terrible", "awful", "bad", "poor", "horrible",
            "scam", "fraud", "cheated", "fake", "expired", "rotten", "damaged",
            "missing", "wrong", "delayed", "refund", "replacement", "unacceptable",
            "frustrated", "angry", "disappointed", "never again", "avoid",
        ]
        suggestion_words = [
            "suggest", "improve", "should", "could", "recommend", "better",
            "feature", "add", "fix", "need", "wish", "希望",
        ]
        praise_words = [
            "great", "excellent", "amazing", "love", "best", "fantastic",
            "wonderful", "perfect", "awesome", "good service", "thank",
        ]

        complaint_score = sum(1 for w in complaint_words if w in text_lower)
        suggestion_score = sum(1 for w in suggestion_words if w in text_lower)
        praise_score = sum(1 for w in praise_words if w in text_lower)

        if complaint_score > suggestion_score and complaint_score > praise_score:
            return "complaint"
        elif suggestion_score > praise_score:
            return "suggestion"
        elif praise_score > 0:
            return "praise"
        return "observation"

    @staticmethod
    def determine_categories(text: str) -> List[str]:
        """Auto-categorize review text into product categories."""
        text_lower = text.lower()
        categories = []
        cat_keywords = {
            "groceries": ["grocery", "vegetable", "fruit", "paneer", "atta", "rice", "dal", "oil", "masala", "onion", "tomato", "potato"],
            "snacks": ["snack", "chips", "biscuit", "namkeen", "chocolate", "cookie", "treat"],
            "beverages": ["beverage", "juice", "water", "cola", "tea", "coffee", "drink", "soda", "milk"],
            "household": ["household", "cleaning", "detergent", "soap", "broom", "mop", "cloth"],
            "personal_care": ["personal care", "shampoo", "toothpaste", "cream", "lotion", "cosmetic", "beauty", "gnc"],
            "pet_supplies": ["pet", "dog food", "cat food", "pet care"],
            "baby_products": ["baby", "diaper", "mamy poko", "pampers", "infant", "toddler"],
            "dairy": ["dairy", "milk", "curd", "yogurt", "butter", "cheese", "cream", "ghee"],
            "packaged_food": ["packaged", "frozen", "ready to eat", "instant", "noodle", "pasta", "cereal"],
            "electronics": ["electronic", "earphone", "headphone", "charger", "cable", "gadget", "phone"],
        }
        for cat, keywords in cat_keywords.items():
            if any(kw in text_lower for kw in keywords):
                categories.append(cat)
        if not categories:
            categories.append("general")
        return categories

    @abstractmethod
    def scrape(self) -> List[Dict]:
        """Scrape data from the source. Returns list of review dicts."""
        pass

    def _make_record(self, text: str, url: str, date: str = None,
                     user: str = "anonymous", location: str = "India",
                     rating: int = None) -> Dict:
        """Create a standardized review record."""
        return {
            "id": self.make_id(text, self.SOURCE_NAME.upper()[:4]),
            "source": self.SOURCE_NAME,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "platform": self.PLATFORM,
            "user": user,
            "location": location,
            "text": self.clean_text(text),
            "intent": self.determine_intent(text),
            "categories": self.determine_categories(text),
            "rating": rating,
            "url": url,
        }
