import json
import hashlib
import random
import os
from datetime import datetime, timedelta

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "cleaned_feedback.json")

PLATFORMS = ["android", "ios", "reddit", "twitter", "forum"]
CATEGORIES = [
    "groceries", "snacks", "beverages", "household", "personal_care",
    "pet_supplies", "baby_products", "dairy", "packaged_food", "cleaning",
]
INTENTS = ["complaint", "suggestion", "praise", "question", "observation"]
SOURCES_MAP = {
    "android": "Google Play Store",
    "ios": "Apple App Store",
    "reddit": "Reddit",
    "twitter": "Twitter/X",
    "forum": "Community Forum",
}

REVIEW_TEMPLATES = {
    "groceries": [
        "I keep ordering the same vegetables every week. There are so many other items on the app I never see.",
        "Grocery delivery is great but the app keeps pushing me back to my usual cart. I want to try something new.",
        "Why does the app only show me dal and rice? I already buy those. Show me something different.",
        "Love the grocery section but there is no way to discover organic snacks or imported items easily.",
        "Fresh produce is good but I wish the app recommended items from other categories I might like.",
        "Grocery repeat orders are convenient but I feel stuck in a loop with no discovery.",
        "The app remembers what I buy but never suggests anything beyond my usual vegetables.",
        "I buy onions and tomatoes every week. Would love to see recipes or ingredient bundles.",
        "Grocery shopping on this app is efficient but completely lacks serendipity.",
        "Wish the app had a try something new section for grocery buyers like me.",
        "My grocery list is identical every week because the app never shows alternatives.",
        "Why does the homepage always show me the same grocery items? I want variety.",
        "The grocery reorder feature is a trap. It keeps me from exploring new products.",
        "I discovered a new spice brand by accident. The app should help me find things like that.",
        "Groceries are my main use case but I never get personalized suggestions for new items.",
        "The app should suggest seasonal produce or local specials to repeat grocery buyers.",
        "I have been buying the same rice brand for months. Show me alternatives please.",
        "Grocery section is fine but there is zero motivation to browse beyond my usual.",
        "Love quick grocery delivery but hate that I never discover new products in this category.",
        "The reorder button is too prominent. I want to explore, not just repeat.",
    ],
    "snacks": [
        "I always end up buying the same chips and biscuits. The recommendation engine is stuck.",
        "Snacks section is repetitive. Where are the healthy alternatives or new brands?",
        "The app keeps showing Maggi and Lay's. I want to explore Korean snacks or protein bars.",
        "Great snack selection but zero discovery. I only find new things by accident.",
        "Why cant the app suggest snacks based on my grocery purchases? I buy diapers too, show me baby snacks.",
        "Snack recommendations are stale. I see the same five brands every time.",
        "Would love to try exotic snacks but the app only shows mainstream options.",
        "I buy chips weekly but never see nuts, dried fruit, or healthy snack alternatives.",
        "The snack aisle on this app needs a complete overhaul in terms of discovery.",
        "Why doesnt the app have a snack of the week feature? That would help me try new things.",
        "I am bored of the same biscuits. Show me something from a new brand.",
        "Snack section is huge but poorly organized. Discovery is nearly impossible.",
        "The app recommends snacks I already bought. I want new and interesting options.",
        "I found a great protein bar by searching randomly. The app should surface these.",
        "Snack buyers are stuck in a rut. The app needs better cross-category suggestions.",
        "Why cant I filter snacks by mood or occasion? That would make discovery easier.",
        "I buy savory snacks but never see sweet alternatives suggested. Weird.",
        "The snack discovery problem is real. I have been buying the same items for a year.",
        "Love the snack variety available but the app never helps me find new things.",
        "Snack recommendations should be based on what I have NOT bought before.",
    ],
    "beverages": [
        "Same Coke and Pepsi every time. I want to see cold pressed juices or kombucha.",
        "Beverage recommendations are stuck in a loop. Nothing new ever appears.",
        "I buy coffee daily but never see tea alternatives or energy drinks suggested.",
        "The drink section needs better discovery. I had to search manually for coconut water.",
        "Would love if the app showed me beverages from other categories like health drinks.",
        "Beverage section is dominated by colas. Where are the artisanal options?",
        "I want to try matcha or oat milk but the app never suggests them.",
        "Why does the app keep showing me the same bottled water brand?",
        "Beverage discovery is broken. I only see what I have already purchased.",
        "The app should have a drink of the day feature for beverage exploration.",
        "I buy juice every morning but never see smoothie alternatives. Annoying.",
        "Beverage section needs better curation. Everything looks the same.",
        "Why cant the app suggest seasonal drinks like lassi in summer or chai in winter?",
        "I drink coffee but would love to discover cold brew or specialty teas.",
        "The beverage aisle is cluttered. Finding new drinks is exhausting.",
        "Beverage recommendations should learn from my grocery patterns, not just drink history.",
        "I saw a new energy drink at a store. The app should stock and recommend these.",
        "Why does the app only show mainstream beverages? I want local or craft options.",
        "Beverage section is the most repetitive category on the app. Needs fixing.",
        "I wish the app would suggest beverages that pair with my grocery items.",
    ],
    "household": [
        "Household essentials are fine but I never discover new cleaning products.",
        "The app keeps showing me the same detergent. There are better options out there.",
        "Why doesnt the app recommend kitchen organizers or storage solutions?",
        "I buy the same cleaning supplies every month. Suggest me something different.",
        "Household section feels stale. Show me eco-friendly alternatives or new brands.",
        "Household essentials are on autopilot. I want to discover better products.",
        "Why does the app never suggest upgraded versions of what I buy?",
        "I buy basic detergent but there are premium options I never see.",
        "Household section needs a refresh. Same products recommended every time.",
        "Would love to see smart home products or organizational tools recommended.",
        "The app knows my household purchases. Why not suggest related items?",
        "I buy trash bags but never see recycling bins or eco alternatives.",
        "Household discovery is non-existent. I am stuck buying the same brand forever.",
        "Why doesnt the app show me trending household products or new arrivals?",
        "I spend a lot on household items but get zero personalized discovery.",
        "The household section should have a try new brands section.",
        "I buy tissues and paper towels but never see cloth alternatives suggested.",
        "Household product recommendations are predictable and boring.",
        "Would love a household essentials bundle that includes new product samples.",
        "The app should suggest seasonal household items like mosquito repellent in summer.",
    ],
    "personal_care": [
        "I never browse personal care because the app never suggests it during grocery checkout.",
        "Found a great shampoo by accident. The app should surface personal care items to grocery buyers.",
        "Personal care section is hidden. I buy groceries but never see skincare or haircare.",
        "Would love to discover new personal care brands but the app keeps me in my bubble.",
        "The app knows I buy household items. Why not suggest personal care bundles?",
        "Personal care is a blind spot for the app. No cross-category discovery at all.",
        "I buy soap but never see face wash or moisturizer alternatives.",
        "Why does the app hide personal care from grocery shoppers? We need these products too.",
        "Personal care recommendations are generic. Show me products based on my profile.",
        "I discovered a new sunscreen by searching. The app should recommend these proactively.",
        "Personal care section needs better visibility for first-time browsers.",
        "Why doesnt the app suggest personal care during checkout for relevant buyers?",
        "I buy the same shampoo for years. Show me alternatives or new launches.",
        "Personal care discovery is broken. I only find things through manual search.",
        "The app should have a grooming essentials section for new product discovery.",
        "I would buy more personal care items if the app showed them to me.",
        "Personal care products are hard to find. The app needs better cross-selling.",
        "Why are personal care recommendations so basic? Show me serums, masks, and tools.",
        "I buy household cleaning products but never see personal care bundles.",
        "Personal care should be surfaced to users based on their purchase patterns.",
    ],
    "pet_supplies": [
        "I have a dog but never see pet food recommendations despite buying groceries weekly.",
        "Pet supplies are completely invisible unless you search. No cross-category discovery.",
        "Bought pet food once manually. The app never suggested it again or showed related items.",
        "Where is the pet section? I only found it by browsing every category manually.",
        "As a pet owner, I want the app to suggest treats and toys alongside my grocery order.",
        "Pet supplies need better integration with the main shopping experience.",
        "I buy pet food but never see grooming products or accessories suggested.",
        "The app should recommend pet products to users who buy pet-adjacent items.",
        "Pet supply discovery is zero. I found everything through Google, not the app.",
        "Why doesn't the app have a pet parent section with curated recommendations?",
        "I buy pet treats but never see health supplements or toys. Frustrating.",
        "Pet supplies are buried in the app. Needs a dedicated discovery flow.",
        "Would love to see seasonal pet products like cooling mats in summer.",
        "The app should suggest pet products based on the pet type if the user specifies.",
        "I am a cat owner but the app shows me dog products. Needs better targeting.",
        "Pet supply recommendations are random. They should be based on purchase history.",
        "Why cant the app create a pet essentials bundle for new pet owners?",
        "I buy premium pet food but never see matching premium toys or beds.",
        "Pet section is an afterthought on this app. Needs proper discovery features.",
        "The app should cross-sell pet products during grocery checkout for pet owners.",
    ],
    "baby_products": [
        "New parent here. The app never suggests baby products even though I buy diapers.",
        "Baby care is hard to find. The app should recommend it to first-time parents.",
        "I buy milk and snacks but never see baby formula or wipes suggested.",
        "Parenting is exhausting. The app should make discovering baby products easier.",
        "Baby products section exists but the app never surfaces it to relevant buyers.",
        "I buy diapers weekly but never see baby shampoo or lotion suggested.",
        "The app should have a new parent onboarding flow for baby product discovery.",
        "Baby product recommendations are generic. Show me age-appropriate items.",
        "I discovered baby food by accident. The app should surface these proactively.",
        "Why doesn't the app suggest baby products to users who buy milk and cereals?",
        "Baby care section is well stocked but impossible to discover naturally.",
        "I would buy more baby products if the app showed them during my grocery runs.",
        "Baby product discovery is critical for new parents. The app fails here.",
        "Why cant the app suggest baby essentials based on the child's age?",
        "I buy baby wipes but never see diaper cream or rash solutions.",
        "Baby section needs a curated new parent essentials bundle.",
        "The app should recommend baby products alongside dairy and food purchases.",
        "Baby product recommendations are stale. Show me new arrivals and safety-tested items.",
        "I spend hours searching for baby products. The app should make this effortless.",
        "Baby care discovery is the biggest gap in this app's recommendation engine.",
    ],
    "dairy": [
        "Dairy is my most bought category but I never see cheese alternatives or yogurt varieties.",
        "I buy milk daily. Why not suggest flavored yogurt or plant-based milk?",
        "Dairy section needs better curation. Same Amul products every time.",
        "Would love to discover artisanal cheese or greek yogurt but the app doesnt show them.",
        "Dairy purchases should trigger recommendations for breakfast items or healthy snacks.",
        "Dairy is repetitive. I see the same milk and butter every day.",
        "Why doesn't the app suggest cheese or yogurt to milk buyers?",
        "I buy paneer but never see cream, sour cream, or other dairy alternatives.",
        "Dairy section needs better product diversity in its recommendations.",
        "Would love to discover plant-based dairy alternatives but the app never suggests them.",
        "Dairy recommendations are predictable. Show me something new and interesting.",
        "I buy ghee every month but never see cooking oils or spreads suggested.",
        "Dairy section should have a try something new feature for regular buyers.",
        "Why does the app only recommend full cream milk? Show me toned or flavored options.",
        "Dairy purchases should unlock breakfast or recipe-based product suggestions.",
        "I buy curd daily but never see raita or probiotic drinks suggested.",
        "Dairy discovery is stuck. Same products, same brands, same recommendations.",
        "The app should suggest dairy pairings like cheese with crackers or yogurt with granola.",
        "Dairy section is the most purchased but least discoverable category.",
        "Would love seasonal dairy suggestions like kulfi in summer or paneer tikka kits.",
    ],
    "packaged_food": [
        "Packaged food is repetitive. Same noodles and pasta every time.",
        "I want to try international snacks but the app only shows domestic brands.",
        "Packaged food section is huge but discovery is terrible. Everything looks the same.",
        "Why does the app recommend the same pasta sauce? Show me Thai curry paste or hummus.",
        "Packaged food needs better categorization. I cannot find healthy options easily.",
        "Packaged food recommendations are stuck in a loop. Same brands, same products.",
        "I buy instant noodles but never see ramen or pho alternatives.",
        "Why doesn't the app suggest international packaged foods to adventurous eaters?",
        "Packaged food section is overwhelming. I need curated discovery features.",
        "Would love to see meal kit components or recipe-specific packaged items.",
        "I buy pasta but never see sauces, oils, or seasoning blends suggested.",
        "Packaged food discovery is non-existent. I only buy what I already know.",
        "The app should have a world food section for discovering international products.",
        "Packaged food recommendations are boring. Show me gourmet or artisanal options.",
        "I buy cereal but never see granola, muesli, or oat alternatives.",
        "Packaged food needs better cross-selling. Snacks should pair with beverages.",
        "Why cant the app suggest packaged foods based on cuisine or dietary preference?",
        "I discovered a new pasta brand at a store. The app should stock and recommend these.",
        "Packaged food section is the largest but has the worst discovery experience.",
        "Would love a try new foods section that rotates weekly featured products.",
    ],
    "cleaning": [
        "Cleaning supplies never change. I want to see new disinfectant brands or tools.",
        "The app keeps showing me Harpic and Lizol. There are better options.",
        "Cleaning section is basic. Show me steam cleaners or eco-friendly alternatives.",
        "I buy floor cleaner but never see window cleaners or kitchen sprays suggested.",
        "Cleaning products need cross-selling. I buy mops but never see replacement heads.",
        "Cleaning supplies are on autopilot. I want to discover better and greener options.",
        "Why does the app only show chemical cleaners? I want eco-friendly alternatives.",
        "I buy dish soap but never see scrubbers, brushes, or kitchen organization tools.",
        "Cleaning section needs a complete discovery overhaul.",
        "Would love to see smart cleaning devices or automated solutions recommended.",
        "Cleaning product recommendations are stale. Same brands, same products every time.",
        "I buy bathroom cleaner but never see mold removers or grout cleaners.",
        "The app should suggest cleaning bundles based on the room or task.",
        "Cleaning section is neglected. No new products or brands are ever surfaced.",
        "Why doesn't the app recommend cleaning tools alongside cleaning chemicals?",
        "I buy laundry detergent but never see stain removers or fabric softeners.",
        "Cleaning product discovery should be based on household size and needs.",
        "Would love to see subscription options for regular cleaning supply deliveries.",
        "Cleaning section has zero personality. It needs curated recommendations.",
        "The app should suggest seasonal cleaning products like spring cleaning kits.",
    ],
}

SPAM_TEMPLATES = [
    "BUY NOW!!! FREE SHIPPING!!! CLICK HERE!!!",
    "Great app, download my app too at spam-link.com",
    "Visit www.totally-not-spam.com for deals",
    "Follow me on Instagram for tips!",
    "ASDFGHJKLZXCVBNM",
    "10/10 would recommend (this is a bot)",
    "Click here for free iPhone giveaway!!!",
    "Earn money from home visit cash-now.biz",
    "This is definitely a human review and not a bot at all",
    "Congratulations you won a prize claim now",
]


def generate_raw_reviews(n=300):
    reviews = []
    base_date = datetime(2026, 1, 1)
    for i in range(n):
        platform = random.choice(PLATFORMS)
        category = random.choice(CATEGORIES)
        is_spam = random.random() < 0.08
        if is_spam:
            text = random.choice(SPAM_TEMPLATES)
            intent = "spam"
        else:
            text = random.choice(REVIEW_TEMPLATES[category])
            intent = random.choice(INTENTS)
        days_offset = random.randint(0, 180)
        review_date = base_date + timedelta(days=days_offset)
        reviews.append({
            "source": SOURCES_MAP[platform],
            "date": review_date.strftime("%Y-%m-%d"),
            "platform": platform,
            "category": category,
            "intent": intent,
            "text": text,
        })
    return reviews


def clean_reviews(reviews):
    seen_hashes = set()
    cleaned = []
    for r in reviews:
        content_hash = hashlib.md5(r["text"].lower().strip().encode()).hexdigest()
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        if r["intent"] == "spam":
            continue
        text = r["text"].strip()
        text = " ".join(text.split())
        cleaned.append({
            "source": r["source"],
            "date": r["date"],
            "platform": r["platform"],
            "category": r["category"],
            "intent": r["intent"],
            "text": text,
        })
    return cleaned


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    raw = generate_raw_reviews(300)
    cleaned = clean_reviews(raw)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)
    print(f"Raw reviews: {len(raw)}")
    print(f"Cleaned reviews: {len(cleaned)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
