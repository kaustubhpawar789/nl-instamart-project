"""
Generate AI Insights JSON from scraped review data.
Computes themes, sentiment, categories from live_scraped_data.json
and writes structured JSON to ai_insights.json.
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(ROOT, "database")


def generate_insights():
    live_path = os.path.join(DATABASE, "cleaned_feedback.json")
    if not os.path.exists(live_path):
        live_path = os.path.join(DATABASE, "live_scraped_data.json")
    insights_path = os.path.join(DATABASE, "ai_insights.json")

    if not os.path.exists(live_path):
        print("  [Insights] No live_scraped_data.json found")
        return

    with open(live_path, "r") as f:
        reviews = json.load(f)

    if not isinstance(reviews, list) or not reviews:
        print("  [Insights] No reviews to analyze")
        _write_empty_insights(insights_path)
        return

    print(f"  [Insights] Analyzing {len(reviews)} reviews...")

    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    category_counts = Counter()
    source_counts = Counter()
    intent_counts = Counter()
    theme_data = defaultdict(lambda: {"mentions": 0, "positive": 0, "neutral": 0, "negative": 0, "sources": set(), "quotes": []})

    THEME_KEYWORDS = {
        "delivery_issues": ["delivery", "delivered", "late", "delayed", "cancelled", "cancel", "missing item", "wrong item"],
        "product_quality": ["expired", "rotten", "spoiled", "fake", "counterfeit", "damaged", "broken", "bad quality", "poor quality"],
        "customer_service": ["customer service", "support", "refund", "replacement", "unresponsive", "rude", "no response", "call center"],
        "pricing_issues": ["price", "expensive", "overpriced", "hidden fee", "charge", "deducted", "penalty"],
        "app_experience": ["app", "interface", "ui", "bug", "crash", "slow", "confusing", "counterintuitive"],
        "underweight_products": ["underweight", "weight", "less quantity", "short weight", "145g", "250g"],
        "wrong_orders": ["wrong item", "incorrect", "different product", "wrong size", "wrong order"],
        "refund_problems": ["refund", "no refund", "partial refund", "coupon", "voucher", "credit"],
    }

    for review in reviews:
        text = (review.get("text", "") or "").lower()
        source = review.get("source", "unknown")
        intent = review.get("intent", "observation")
        categories = review.get("categories", ["general"]) or ["general"]
        sentiment = review.get("sentiment", "neutral") or "neutral"
        rating = review.get("rating", 3) or 3

        if sentiment not in ("positive", "neutral", "negative"):
            if rating <= 2:
                sentiment = "negative"
            elif rating >= 4:
                sentiment = "positive"
            else:
                sentiment = "neutral"

        sentiment_counts[sentiment] += 1
        source_counts[source] += 1
        intent_counts[intent] += 1

        for cat in categories:
            category_counts[cat] += 1

        for theme_name, keywords in THEME_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                theme_data[theme_name]["mentions"] += 1
                theme_data[theme_name][sentiment] += 1
                theme_data[theme_name]["sources"].add(source)
                if len(theme_data[theme_name]["quotes"]) < 3 and len(text) > 20:
                    theme_data[theme_name]["quotes"].append({
                        "text": review.get("text", "")[:200],
                        "source": source,
                        "category": categories[0] if categories else "general",
                    })

    total = len(reviews)
    themes = []
    for name, data in sorted(theme_data.items(), key=lambda x: -x[1]["mentions"]):
        mentions = data["mentions"]
        freq = "High" if mentions >= 10 else ("Medium" if mentions >= 5 else "Low")
        themes.append({
            "name": name.replace("_", " ").title(),
            "frequency": freq,
            "mentions": mentions,
            "sentiment": {"positive": data["positive"], "neutral": data["neutral"], "negative": data["negative"]},
            "blockers": [f"Issue reported {mentions} times across {len(data['sources'])} sources"],
            "triggers": ["Improved quality control", "Better customer support"],
            "evidence": data["quotes"],
        })

    pos_pct = round(sentiment_counts["positive"] / total * 100, 1) if total else 0
    neu_pct = round(sentiment_counts["neutral"] / total * 100, 1) if total else 0
    neg_pct = round(sentiment_counts["negative"] / total * 100, 1) if total else 0

    sentiment = {
        "positive": {"count": sentiment_counts["positive"], "percentage": pos_pct},
        "neutral": {"count": sentiment_counts["neutral"], "percentage": neu_pct},
        "negative": {"count": sentiment_counts["negative"], "percentage": neg_pct},
    }

    top_cats = category_counts.most_common(15)
    categories_list = []
    for name, count in top_cats:
        neg_in_cat = sum(1 for r in reviews if name in (r.get("categories") or []) and r.get("sentiment") == "negative")
        neg_ratio = neg_in_cat / count if count else 0
        gap_severity = "High" if neg_ratio > 0.5 else ("Medium" if neg_ratio > 0.3 else "Low")
        business_impact = "High" if count > 20 else ("Medium" if count > 10 else "Low")
        categories_list.append({
            "name": name,
            "mentions": count,
            "gap_severity": gap_severity,
            "business_impact": business_impact,
        })

    insights_list = []
    if themes:
        top_theme = themes[0]
        insights_list.append({
            "title": f"Primary Concern: {top_theme['name']}",
            "observation": f"{top_theme['name']} is the most mentioned theme with {top_theme['mentions']} mentions across {len(top_theme['sentiment'])} sentiment categories.",
            "user_need": "Users need resolution for this recurring issue to maintain trust in the platform.",
            "root_cause": f"The high frequency of {top_theme['name'].lower()} reports suggests systemic issues in the current process.",
            "opportunity": "Addressing this systematically could significantly improve user satisfaction and reduce churn.",
            "implication": "This should be prioritized in the product roadmap as it directly impacts user retention.",
        })
    if len(themes) > 1:
        t2 = themes[1]
        insights_list.append({
            "title": f"Secondary Concern: {t2['name']}",
            "observation": f"{t2['name']} appears {t2['mentions']} times, indicating it's a significant pain point.",
            "user_need": "Users expect reliable resolution for these issues.",
            "root_cause": f"Process gaps in {t2['name'].lower()} handling.",
            "opportunity": "Streamlining this area could differentiate from competitors.",
            "implication": "Invest in automation or better processes for this area.",
        })
    if sentiment_counts["negative"] > sentiment_counts["positive"]:
        insights_list.append({
            "title": "Negative Sentiment Dominance",
            "observation": f"Negative reviews ({neg_pct}%) significantly outweigh positive ({pos_pct}%).",
            "user_need": "Users are frustrated and need tangible improvements.",
            "root_cause": "Multiple unresolved issues across delivery, quality, and support.",
            "opportunity": "Turning negative experiences into positive ones through proactive outreach.",
            "implication": "Urgent intervention needed to prevent further reputation damage.",
        })

    insights_data = {
        "themes": themes,
        "insights": insights_list,
        "sentiment": sentiment,
        "categories": categories_list,
        "generated_at": datetime.now().isoformat(),
        "total_reviews": total,
    }

    with open(insights_path, "w") as f:
        json.dump(insights_data, f, indent=2, ensure_ascii=False)

    print(f"  [Insights] Generated: {len(themes)} themes, {len(insights_list)} insights, {len(categories_list)} categories")
    print(f"  [Insights] Sentiment: +{sentiment_counts['positive']}({pos_pct}%) ={sentiment_counts['neutral']}({neu_pct}%) -{sentiment_counts['negative']}({neg_pct}%)")
    return insights_data


def _write_empty_insights(path):
    data = {
        "themes": [],
        "insights": [],
        "sentiment": {"positive": {"count": 0, "percentage": 0}, "neutral": {"count": 0, "percentage": 0}, "negative": {"count": 0, "percentage": 0}},
        "categories": [],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    generate_insights()
