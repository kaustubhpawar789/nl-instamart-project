#!/usr/bin/env python3
"""
database/seed_mock_data.py — Phase 2 Mock Data Seeder
Populates all Phase 2 tables with realistic Swiggy Instamart data.

Usage:
    source .venv/bin/activate
    python database/seed_mock_data.py
"""

import os
import json
import random
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, "secrets", ".env"))


def get_connection():
    from database.db import get_db_connection
    return get_db_connection()


def _now():
    return datetime.now(timezone.utc)


def _days_ago(n):
    return _now() - timedelta(days=n)


# ══════════════════════════════════════════════════════════════════════
# SEED DATA
# ══════════════════════════════════════════════════════════════════════

# (name, sub_category, sort_order, image_url, mentions, gap_severity, business_impact)
CATEGORIES = [
    ("Groceries", "Staples & Pantry", 1, "https://images.example.com/cat/groceries.jpg", 450, "High", "High"),
    ("Snacks", "Biscuits, Chips & Namkeen", 2, "https://images.example.com/cat/snacks.jpg", 320, "Medium", "High"),
    ("Beverages", "Juices, Tea & Soft Drinks", 3, "https://images.example.com/cat/beverages.jpg", 280, "Medium", "Medium"),
    ("Dairy", "Milk, Curd & Paneer", 4, "https://images.example.com/cat/dairy.jpg", 210, "High", "High"),
    ("Personal Care", "Skin, Hair & Hygiene", 5, "https://images.example.com/cat/personal_care.jpg", 180, "Low", "Medium"),
    ("Household", "Cleaning & Essentials", 6, "https://images.example.com/cat/household.jpg", 150, "Low", "Medium"),
    ("Baby Products", "Diapers, Food & Care", 7, "https://images.example.com/cat/baby.jpg", 95, "Medium", "Low"),
    ("Pet Supplies", "Food, Treats & Accessories", 8, "https://images.example.com/cat/pet.jpg", 65, "Low", "Low"),
    ("Packaged Food", "Ready to Eat & Instant", 9, "https://images.example.com/cat/packaged.jpg", 310, "High", "High"),
    ("Bakery", "Bread, Cakes & Pastries", 10, "https://images.example.com/cat/bakery.jpg", 130, "Medium", "Medium"),
    ("Fruits & Vegetables", "Fresh Produce", 11, "https://images.example.com/cat/fresh.jpg", 380, "High", "High"),
    ("Cleaning", "Detergents & Disinfectants", 12, "https://images.example.com/cat/cleaning.jpg", 110, "Low", "Medium"),
]

PRODUCTS = [
    # Groceries
    ("Aashirvaad Atta 5kg", 1, "ITC", 285.00, 310.00, 150, "Premium whole wheat atta", "SKU-GRO-001",
     "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Fortune Sunlite Refined Oil 1L", 1, "Adani Wilmar", 142.50, 155.00, 200, "Light and healthy sunflower oil", "SKU-GRO-002",
     "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Tata Salt 1kg", 1, "Tata", 28.00, 30.00, 500, "Iodised refined salt", "SKU-GRO-003",
     "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Daawat Basmati Rice 1kg", 1, "Daawat", 165.00, 180.00, 120, "Long grain premium basmati", "SKU-GRO-004",
     "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Toor Dal 1kg", 1, "Tata Sampann", 175.00, 190.00, 180, "Unpolished toor dal", "SKU-GRO-005",
     "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=200&h=200&fit=crop&auto=format&q=70"),
    # Snacks
    ("Parle-G Biscuits 80g", 2, "Parle", 10.00, 10.00, 1000, "The iconic glucose biscuit", "SKU-SNK-001",
     "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Lays Classic Salted 95g", 2, "PepsiCo", 20.00, 20.00, 800, "Crispy potato chips", "SKU-SNK-002",
     "https://images.unsplash.com/photo-1566478989037-b58aad7e7e5c?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Haldiram Aloo Bhujia 200g", 2, "Haldiram", 55.00, 60.00, 350, "Spicy potato noodles snack", "SKU-SNK-003",
     "https://images.unsplash.com/photo-1599490659213-e2b9527bd087?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Kurkure Masala Munch 90g", 2, "PepsiCo", 20.00, 20.00, 600, "Crunchy corn puff snack", "SKU-SNK-004",
     "https://images.unsplash.com/photo-1621447504864-d8686e12698c?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Britannia Good Day 250g", 2, "Britannia", 60.00, 65.00, 250, "Butter cookies", "SKU-SNK-005",
     "https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=200&h=200&fit=crop&auto=format&q=70"),
    # Beverages
    ("Bisleri Mineral Water 1L", 3, "Bisleri", 20.00, 22.00, 2000, "Packaged drinking water", "SKU-BVG-001",
     "https://images.unsplash.com/photo-1560023907-5f339617b5f7?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Paper Boat Aam Panna 200ml", 3, "Paper Boat", 30.00, 30.00, 400, "Raw mango drink", "SKU-BVG-002",
     "https://images.unsplash.com/photo-1546173159-315724a31696?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Coca-Cola 750ml", 3, "Coca-Cola", 40.00, 40.00, 600, "Carbonated soft drink", "SKU-BVG-003",
     "https://images.unsplash.com/photo-1554866585-cd94c8801c3c?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Brooke Bond Red Label Tea 250g", 3, "HUL", 68.00, 72.00, 300, "Natural care tea", "SKU-BVG-004",
     "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Nescafe Classic 50g", 3, "Nestle", 160.00, 175.00, 200, "Instant coffee", "SKU-BVG-005",
     "https://images.unsplash.com/photo-1509042239860-f5f3a73e5f0c?w=200&h=200&fit=crop&auto=format&q=70"),
    # Dairy
    ("Amul Butter 100g", 4, "Amul", 56.00, 56.00, 500, "Pasteurised butter", "SKU-DAR-001",
     "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Amul Taaza Toned Milk 500ml", 4, "Amul", 30.00, 30.00, 800, "Fresh toned milk", "SKU-DAR-002",
     "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Mother Dairy Paneer 200g", 4, "Mother Dairy", 90.00, 95.00, 300, "Fresh cottage cheese", "SKU-DAR-003",
     "https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Epigamia Greek Yogurt Strawberry 90g", 4, "Epigamia", 49.00, 55.00, 250, "All-natural Greek yogurt", "SKU-DAR-004",
     "https://images.unsplash.com/photo-1488477181228-be5571b927f3?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Amul Gold Full Cream Milk 1L", 4, "Amul", 62.00, 62.00, 400, "Full cream homogenised milk", "SKU-DAR-005",
     "https://images.unsplash.com/photo-1563636619-e9143da7529f?w=200&h=200&fit=crop&auto=format&q=70"),
    # Personal Care
    ("Colgate MaxFresh 150g", 5, "Colgate-Palmolive", 95.00, 105.00, 400, "Spicy fresh toothpaste", "SKU-PSC-001",
     "https://images.unsplash.com/photo-1588776814546-1ffebb5e38b7?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Dove Shampoo 180ml", 5, "HUL", 185.00, 200.00, 300, "Nutritive solutions shampoo", "SKU-PSC-002",
     "https://images.unsplash.com/photo-1526045612212-70caf35c14df?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Nivea Soft Moisturizer 100ml", 5, "Beiersdorf", 199.00, 220.00, 250, "Light moisturizing cream", "SKU-PSC-003",
     "https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Dettol Soap 75g", 5, "Reckitt", 45.00, 48.00, 500, "Original antibacterial soap", "SKU-PSC-004",
     "https://images.unsplash.com/photo-1584305574667-ccc6a8246227?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Vivel Aloe Vera Body Wash 250ml", 5, "ITC", 149.00, 165.00, 200, "Moisturising body wash", "SKU-PSC-005",
     "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=200&h=200&fit=crop&auto=format&q=70"),
    # Household
    ("Vim Dishwash Liquid 500ml", 6, "HUL", 99.00, 105.00, 400, "Lemon dishwashing liquid", "SKU-HSH-001",
     "https://images.unsplash.com/photo-1583947215259-16aa7f99b4d5?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Harpic Power Plus 500ml", 6, "Reckitt", 85.00, 90.00, 350, "Toilet cleaner", "SKU-HSH-002",
     "https://images.unsplash.com/photo-1585155770447-2f66f08a2dbe?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Lizol Floor Cleaner 500ml", 6, "Reckitt", 99.00, 110.00, 300, "Citrus floor cleaner", "SKU-HSH-003",
     "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Odonil Air Freshener 75g", 6, "Reckitt", 55.00, 60.00, 250, "Gel air freshener", "SKU-HSH-004",
     "https://images.unsplash.com/photo-1600857544200-b2f468e9cdf4?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Surf Excel Easy Wash 1kg", 6, "HUL", 135.00, 145.00, 200, "Detergent powder", "SKU-HSH-005",
     "https://images.unsplash.com/photo-1545173168-9f1947eebb7f?w=200&h=200&fit=crop&auto=format&q=70"),
    # Baby Products
    ("MamyPoko Pants XL 4pcs", 7, "Unicharm", 99.00, 110.00, 300, "Absorbent baby diapers", "SKU-BBY-001",
     "https://images.unsplash.com/photo-1491013516836-7db643ee5b41?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Cerelac Wheat-Rice 300g", 7, "Nestle", 135.00, 145.00, 200, "Stage 1 infant cereal", "SKU-BBY-002",
     "https://images.unsplash.com/photo-1574781330855-d0db8cc6a79c?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Johnson's Baby Shampoo 200ml", 7, "Johnson & Johnson", 195.00, 210.00, 180, "No tears baby shampoo", "SKU-BBY-003",
     "https://images.unsplash.com/photo-1519689680058-324335c77eba?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Huggies Wonder Pants Medium 9pcs", 7, "Kimberly-Clark", 249.00, 270.00, 150, "Premium baby diapers", "SKU-BBY-004",
     "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=200&h=200&fit=crop&auto=format&q=70"),
    ("PediaSure 400g", 7, "Abbott", 420.00, 450.00, 120, "Complete nutrition supplement", "SKU-BBY-005",
     "https://images.unsplash.com/photo-1550159930-40066082a4fc?w=200&h=200&fit=crop&auto=format&q=70"),
    # Pet Supplies
    ("Drools Cat Dry Food 1.2kg", 8, "Drools", 399.00, 440.00, 150, "Chicken flavour cat food", "SKU-PET-001",
     "https://images.unsplash.com/photo-1574158622682-e719686a39ec?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Pedigree Dog Food 3kg", 8, "Mars", 520.00, 560.00, 200, "Chicken & vegetables dog food", "SKU-PET-002",
     "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Me-O Cat Wet Food Tuna 400g", 8, "Perfect Companion", 95.00, 105.00, 180, "Wet food for adult cats", "SKU-PET-003",
     "https://images.unsplash.com/photo-1513245543132-31f507417b26?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Scoobee Dog Biscuits 500g", 8, "Voyager", 120.00, 135.00, 250, "Oven-baked dog treats", "SKU-PET-004",
     "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Whiskas Cat Food 1.2kg", 8, "Mars", 380.00, 420.00, 160, "Tuna flavour cat dry food", "SKU-PET-005",
     "https://images.unsplash.com/photo-1592194996308-7b43878e84a6?w=200&h=200&fit=crop&auto=format&q=70"),
    # Packaged Food
    ("Maggi 2-Minute Noodles 70g", 9, "Nestle", 14.00, 14.00, 2000, "Masala flavour instant noodles", "SKU-PKF-001",
     "https://images.unsplash.com/photo-1569050467447-ce54b3bbc37d?w=200&h=200&fit=crop&auto=format&q=70"),
    ("MTR Ready to Eat Rajma 300g", 9, "MTR", 85.00, 95.00, 200, "Ready to eat kidney bean curry", "SKU-PKF-002",
     "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Yippee Noodles 60g", 9, "ITC", 12.00, 12.00, 1500, "Magic masala instant noodles", "SKU-PKF-003",
     "https://images.unsplash.com/photo-1552611052-33e04de081de?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Kissan Mixed Fruit Jam 500g", 9, "HUL", 115.00, 125.00, 300, "Delicious fruit jam", "SKU-PKF-004",
     "https://images.unsplash.com/photo-1543352634-a1c51d9f1fa7?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Saffola Oats 1kg", 9, "Marico", 160.00, 180.00, 250, "Masala Mediterranean oats", "SKU-PKF-005",
     "https://images.unsplash.com/photo-1584362917165-526a968579e8?w=200&h=200&fit=crop&auto=format&q=70"),
    # Bakery
    ("Britannia 100% Whole Wheat Bread 400g", 10, "Britannia", 42.00, 45.00, 500, "Healthy whole wheat bread", "SKU-BKR-001",
     "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=200&h=200&fit=crop&auto=format&q=70"),
    ("McVities Digestive Biscuits 250g", 10, "United Biscuits", 55.00, 60.00, 300, "Classic digestive biscuits", "SKU-BKR-002",
     "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=200&h=200&fit=crop&auto=format&q=70"),
    ("English Oven Premium Bread 400g", 10, "Britannia", 38.00, 40.00, 450, "Soft and fresh bread", "SKU-BKR-003",
     "https://images.unsplash.com/photo-1555951015-6da899b5c2cd?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Modern Breads 400g", 10, "Modern Foods", 35.00, 38.00, 400, "Everyday white bread", "SKU-BKR-004",
     "https://images.unsplash.com/photo-1549931319-a545dcf3bc73?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Britannia Fruit Cake 250g", 10, "Britannia", 65.00, 70.00, 200, "Rich fruit cake", "SKU-BKR-005",
     "https://images.unsplash.com/photo-1578985545062-70f4dc2a7914?w=200&h=200&fit=crop&auto=format&q=70"),
    # Fruits & Vegetables
    ("Fresh Apple Shimla 1kg", 11, "Local Farm", 120.00, 140.00, 300, "Fresh Shimla apples", "SKU-FRV-001",
     "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Banana Robusta 1kg", 11, "Local Farm", 45.00, 50.00, 500, "Fresh robusta bananas", "SKU-FRV-002",
     "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Onion 1kg", 11, "Local Farm", 35.00, 40.00, 800, "Fresh red onions", "SKU-FRV-003",
     "https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Tomato 1kg", 11, "Local Farm", 30.00, 35.00, 700, "Fresh ripe tomatoes", "SKU-FRV-004",
     "https://images.unsplash.com/photo-1546941453-5bdb803a2aca?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Potato 1kg", 11, "Local Farm", 28.00, 32.00, 900, "Fresh potatoes", "SKU-FRV-005",
     "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=200&h=200&fit=crop&auto=format&q=70"),
    # Cleaning
    ("Harpic Drain Master 500ml", 12, "Reckitt", 75.00, 80.00, 250, "Drain cleaner", "SKU-CLN-001",
     "https://images.unsplash.com/photo-1585155770447-2f66f08a2dbe?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Colin Glass Cleaner 500ml", 12, "SC Johnson", 85.00, 90.00, 200, "Streak-free glass cleaner", "SKU-CLN-002",
     "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Giffy Floor Cleaner 1L", 12, "Dabur", 79.00, 85.00, 300, "Neem floor cleaner", "SKU-CLN-003",
     "https://images.unsplash.com/photo-1600857544200-b2f468e9cdf4?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Vanish Oxi Action Powder 500g", 12, "Reckitt", 185.00, 200.00, 150, "Stain remover", "SKU-CLN-004",
     "https://images.unsplash.com/photo-1545173168-9f1947eebb7f?w=200&h=200&fit=crop&auto=format&q=70"),
    ("Lizol Disinfectant 99.9% 500ml", 12, "Reckitt", 115.00, 125.00, 200, "Kills 99.9% germs", "SKU-CLN-005",
     "https://images.unsplash.com/photo-1583947215259-16aa7f99b4d5?w=200&h=200&fit=crop&auto=format&q=70"),
]

USERS = [
    ("Priya Sharma", "priya.sharma@gmail.com", "9876543210", "Mumbai", "Maharashtra", "25-34"),
    ("Rahul Verma", "rahul.verma@outlook.com", "9812345678", "Delhi", "Delhi", "25-34"),
    ("Anjali Patel", "anjali.p@yahoo.com", "9900112233", "Ahmedabad", "Gujarat", "18-24"),
    ("Vikram Singh", "vikram.singh@gmail.com", "9988776655", "Bangalore", "Karnataka", "35-44"),
    ("Sneha Reddy", "sneha.r@outlook.com", "9871234567", "Hyderabad", "Telangana", "25-34"),
    ("Amit Joshi", "amit.joshi@gmail.com", "9911223344", "Pune", "Maharashtra", "25-34"),
    ("Kavitha Nair", "kavitha.nair@gmail.com", "9823456789", "Chennai", "Tamil Nadu", "35-44"),
    ("Deepak Gupta", "deepak.g@outlook.com", "9934567890", "Noida", "Uttar Pradesh", "18-24"),
    ("Meera Iyer", "meera.iyer@yahoo.com", "9845678901", "Mysore", "Karnataka", "45-54"),
    ("Arjun Menon", "arjun.menon@gmail.com", "9956789012", "Kochi", "Kerala", "25-34"),
]

TICKET_SUBJECTS = [
    ("Missing items in order", "delivery", "high", "in_progress"),
    ("Expired product received", "product", "urgent", "open"),
    ("Refund not processed", "support", "high", "open"),
    ("Wrong item delivered", "delivery", "medium", "resolved"),
    ("App crashing on checkout", "app_experience", "high", "in_progress"),
    ("Delayed delivery - 2 hours late", "delivery", "medium", "resolved"),
    ("Damaged packaging", "delivery", "low", "closed"),
    ("Coupon code not working", "app_experience", "medium", "open"),
    ("Product quality issue - stale bread", "product", "medium", "in_progress"),
    ("Payment charged but order cancelled", "support", "urgent", "open"),
    ("Delivery agent rude behavior", "delivery", "medium", "resolved"),
    ("Substitution without consent", "product", "high", "open"),
    ("App shows wrong MRP", "app_experience", "low", "closed"),
    ("Bulk order discount not applied", "support", "medium", "in_progress"),
    ("Cold chain broken for dairy", "product", "urgent", "open"),
]

WORKFLOW_NAMES = [
    ("live_scrape", "api_trigger"),
    ("ai_theme_extraction", "scheduled"),
    ("sentiment_analysis", "data_pipeline"),
    ("recommendation_engine", "daily_batch"),
    ("feedback_categorization", "event_trigger"),
    ("report_generation", "weekly_schedule"),
    ("data_cleanup", "maintenance"),
    ("notion_sync", "hourly"),
]

TEST_NAMES = [
    ("test_api_kpis", "integration"),
    ("test_scrape_endpoint", "e2e"),
    ("test_user_creation", "unit"),
    ("test_product_search", "unit"),
    ("test_recommendation_score", "unit"),
    ("test_ticket_workflow", "integration"),
    ("test_feedback_rating", "unit"),
    ("test_bulk_import", "performance"),
    ("test_search_latency", "performance"),
    ("test_auth_flow", "e2e"),
]


def seed_categories(cur):
    cur.execute("SELECT COUNT(*) FROM categories")
    existing = cur.fetchone()[0]
    if existing >= len(CATEGORIES):
        print(f"  · Categories already seeded ({existing} rows)")
        return

    for name, sub, sort_order, img, mentions, gap_sev, biz_impact in CATEGORIES:
        cur.execute("""
            INSERT INTO categories (name, mentions, gap_severity, business_impact, sub_category, image_url, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (name) DO UPDATE SET
                sub_category = EXCLUDED.sub_category,
                image_url = EXCLUDED.image_url,
                sort_order = EXCLUDED.sort_order
        """, (name, mentions, gap_sev, biz_impact, sub, img, sort_order))
    print(f"  ✓ Seeded {len(CATEGORIES)} categories")


def get_category_id(cur, name):
    cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
    row = cur.fetchone()
    return row[0] if row else None


def seed_products(cur):
    cur.execute("SELECT COUNT(*) FROM products")
    existing = cur.fetchone()[0]
    if existing >= len(PRODUCTS):
        print(f"  · Products already seeded ({existing} rows)")
        return

    cat_map = {}
    pos_to_name = {}
    for name, _, sort_order, _, _, _, _ in CATEGORIES:
        cat_map[name] = get_category_id(cur, name)
        pos_to_name[sort_order] = name

    for name, cat_pos, brand, price, mrp, stock, desc, sku, img_url in PRODUCTS:
        cat_name = pos_to_name.get(cat_pos)
        cat_id = cat_map.get(cat_name) if cat_name else None
        cur.execute("""
            INSERT INTO products (name, category_id, brand, price, mrp, stock_quantity, description, sku, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sku) DO UPDATE SET image_url = EXCLUDED.image_url
        """, (name, cat_id, brand, price, mrp, stock, desc, sku, img_url))
    print(f"  ✓ Seeded {len(PRODUCTS)} products")


def seed_users(cur):
    cur.execute("SELECT COUNT(*) FROM users")
    existing = cur.fetchone()[0]
    if existing >= len(USERS):
        print(f"  · Users already seeded ({existing} rows)")
        return

    for name, email, phone, city, state, age in USERS:
        cur.execute("""
            INSERT INTO users (email, name, phone, city, state, age_group)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (email, name, phone, city, state, age))
    print(f"  ✓ Seeded {len(USERS)} users")


def seed_recommendations(cur):
    cur.execute("SELECT COUNT(*) FROM recommendations")
    if cur.fetchone()[0] > 0:
        print("  · Recommendations already seeded")
        return

    cur.execute("SELECT id FROM users")
    user_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM products")
    product_ids = [r[0] for r in cur.fetchall()]

    rows = []
    for user_id in user_ids:
        sampled = random.sample(product_ids, min(5, len(product_ids)))
        for prod_id in sampled:
            score = round(random.uniform(0.55, 0.99), 4)
            reason = random.choice([
                "Frequently bought by similar users",
                "Matches your purchase history",
                "Trending in your city",
                "You may like based on category preference",
                "Popular in your age group",
            ])
            algo = random.choice(["collaborative_filtering", "content_based", "hybrid", "trending"])
            rows.append((user_id, prod_id, score, reason, algo))

    cur.executemany("""
        INSERT INTO recommendations (user_id, product_id, score, reason, algorithm)
        VALUES (%s, %s, %s, %s, %s)
    """, rows)
    print(f"  ✓ Seeded {len(rows)} recommendations")


def seed_feedback(cur):
    cur.execute("SELECT COUNT(*) FROM feedback")
    if cur.fetchone()[0] > 0:
        print("  · Feedback already seeded")
        return

    cur.execute("SELECT id FROM users")
    user_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM products")
    product_ids = [r[0] for r in cur.fetchall()]

    fb_types = ["product", "delivery", "app_experience", "support"]
    comments = {
        5: ["Excellent product, will buy again!", "Perfect quality and fast delivery", "Best in category"],
        4: ["Good product overall", "Satisfied with the purchase", "Decent quality for the price"],
        3: ["Average product", "Okay but expected better", "Does the job"],
        2: ["Below expectations", "Quality could be better", "Not worth the price"],
        1: ["Terrible experience", "Product was damaged on arrival", "Never buying again"],
    }

    rows = []
    used = set()
    for _ in range(40):
        user_id = random.choice(user_ids)
        prod_id = random.choice(product_ids)
        key = (user_id, prod_id)
        if key in used:
            continue
        used.add(key)
        rating = random.choices([1, 2, 3, 4, 5], weights=[10, 15, 25, 30, 20])[0]
        comment = random.choice(comments[rating])
        fb_type = random.choice(fb_types)
        rows.append((user_id, prod_id, rating, comment, fb_type))

    cur.executemany("""
        INSERT INTO feedback (user_id, product_id, rating, comment, feedback_type)
        VALUES (%s, %s, %s, %s, %s)
    """, rows)
    print(f"  ✓ Seeded {len(rows)} feedback entries")


def seed_tickets(cur):
    cur.execute("SELECT COUNT(*) FROM tickets")
    if cur.fetchone()[0] > 0:
        print("  · Tickets already seeded")
        return

    cur.execute("SELECT id FROM users")
    user_ids = [r[0] for r in cur.fetchall()]

    rows = []
    for i, (subject, category, priority, status) in enumerate(TICKET_SUBJECTS):
        user_id = user_ids[i % len(user_ids)]
        desc = f"Customer reported: {subject}. Needs immediate attention."
        resolved_at = _days_ago(random.randint(1, 15)) if status in ("resolved", "closed") else None
        assigned = random.choice(["Agent Priya", "Agent Rahul", "Agent System", None])
        rows.append((user_id, subject, desc, status, priority, category, assigned, resolved_at))

    cur.executemany("""
        INSERT INTO tickets (user_id, subject, description, status, priority, category, assigned_to, resolved_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, rows)
    print(f"  ✓ Seeded {len(rows)} tickets")


def seed_test_data(cur):
    cur.execute("SELECT COUNT(*) FROM test_data")
    if cur.fetchone()[0] > 0:
        print("  · Test data already seeded")
        return

    rows = []
    for name, ttype in TEST_NAMES:
        inp = json.dumps({"test_id": name, "params": {"verbose": True}})
        expected = json.dumps({"status": "pass", "assertions": random.randint(3, 12)})
        actual = json.dumps({"status": "pass", "assertions": random.randint(3, 12)})
        status = random.choice(["passed", "passed", "passed", "failed"])
        duration = random.randint(15, 2500)
        rows.append((name, ttype, inp, expected, actual, status, duration))

    cur.executemany("""
        INSERT INTO test_data (test_name, test_type, input_data, expected_output, actual_output, status, duration_ms)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
    """, rows)
    print(f"  ✓ Seeded {len(rows)} test data entries")


def seed_workflow_outputs(cur):
    cur.execute("SELECT COUNT(*) FROM workflow_outputs")
    if cur.fetchone()[0] > 0:
        print("  · Workflow outputs already seeded")
        return

    rows = []
    for wf_name, source in WORKFLOW_NAMES:
        input_p = json.dumps({"source": source, "batch_size": random.randint(50, 500)})
        status = random.choice(["completed", "completed", "completed", "failed"])
        output = json.dumps({"records_processed": random.randint(100, 1000), "errors": random.randint(0, 5)})
        error = "Timeout exceeded" if status == "failed" else None
        started = _days_ago(random.randint(0, 7))
        completed = started + timedelta(minutes=random.randint(1, 30))
        rows.append((wf_name, source, input_p, output, status, error, started, completed))

    cur.executemany("""
        INSERT INTO workflow_outputs (workflow_name, trigger_source, input_params, output_data, status, error_message, started_at, completed_at)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
    """, rows)
    print(f"  ✓ Seeded {len(rows)} workflow outputs")


def main():
    print("── DB-005: Phase 2 Mock Data Seeder ─" + "─" * 37)
    conn = get_connection()
    cur = conn.cursor()

    try:
        seed_categories(cur)
        seed_products(cur)
        seed_users(cur)
        seed_recommendations(cur)
        seed_feedback(cur)
        seed_tickets(cur)
        seed_test_data(cur)
        seed_workflow_outputs(cur)
        conn.commit()

        # Print summary
        tables = [
            "categories", "products", "users", "recommendations",
            "feedback", "tickets", "test_data", "workflow_outputs",
        ]
        print("\n  Summary:")
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"    {t:20s} → {count} rows")

        print("─" * 57)
    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
