"""
Scrapers package for collecting real user reviews and feedback from multiple sources.
"""
from .reddit_scraper import RedditScraper
from .trustpilot_scraper import TrustpilotScraper
from .apple_store_scraper import AppleStoreScraper
from .google_play_scraper import GooglePlayScraper
from .consumer_complaints_scraper import ConsumerComplaintsScraper
from .consumer_court_scraper import ConsumerCourtScraper
from .fssai_scraper import FSSAIScraper
from .bbc_scraper import BBCScraper
from .indian_food_times_scraper import IndianFoodTimesScraper
from .digital_in_asia_scraper import DigitalInAsiaScraper
from .confetti_design_scraper import ConfettiDesignScraper

ALL_SCRAPERS = {
    "reddit": RedditScraper,
    "trustpilot": TrustpilotScraper,
    "apple_store": AppleStoreScraper,
    "google_play": GooglePlayScraper,
    "consumer_complaints": ConsumerComplaintsScraper,
    "consumer_court": ConsumerCourtScraper,
    "fssai": FSSAIScraper,
    "bbc": BBCScraper,
    "indian_food_times": IndianFoodTimesScraper,
    "digital_in_asia": DigitalInAsiaScraper,
    "confetti_design": ConfettiDesignScraper,
}
