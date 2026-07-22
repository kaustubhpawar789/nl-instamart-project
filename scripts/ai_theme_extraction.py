import json
import os
import sys
from dotenv import load_dotenv
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DATA_FILE = os.path.join(ROOT, "database", "cleaned_feedback.json")
OUTPUT_FILE = os.path.join(ROOT, "docs", "ai_insights.md")
MODEL = "llama-3.3-70b-versatile"


SYSTEM_PROMPT = """You are a senior product research analyst specializing in quick-commerce consumer behavior.

You will receive a batch of user reviews from a quick-commerce platform (like Swiggy Instamart). Each review has: source, date, platform, category, intent, and text.

Your task is to produce a structured analysis in EXACTLY this Markdown format:

## Theme Analysis

For each major theme you identify (aim for 5-8 themes), provide:

### Theme: [Theme Name]
**Frequency:** [High/Medium/Low] — [N] mentions across categories: [list categories]
**Direct Evidence:**
- "[exact quote from review 1]" — Source: [source], Category: [category]
- "[exact quote from review 2]" — Source: [source], Category: [category]
- "[exact quote from review 3]" — Source: [source], Category: [category]

**Sentiment Breakdown:** Positive: [N] | Neutral: [N] | Negative: [N]

**Key Blockers:**
- [What prevents users from overcome this issue]

**Key Triggers:**
- [What would motivate users to change behavior]

## Structured Insights

For each of the top 5 insights, provide:

### Insight [N]: [Title]

**Observation:** [What the data shows — be specific and data-driven]

**User Need:** [What the user actually wants but is not getting]

**Root Cause:** [Why this gap exists in the current product]

**Opportunity:** [How solving this creates value for users and the business]

**Implication:** [What this means for product strategy and the MVP we are building]

## Sentiment Summary

Provide an overall sentiment breakdown across all reviews:
- Positive: [count] ([%])
- Neutral: [count] ([%])
- Negative: [count] ([%])

## Category Priority Matrix

Rank categories by discovery gap (highest to lowest), showing:
| Category | Mentions | Discovery Gap Severity | Business Impact |
|----------|----------|----------------------|-----------------|

## Recommendations

Provide 3-5 actionable recommendations for the MVP based on the analysis.

RULES:
1. Use ONLY direct quotes from the provided reviews as evidence.
2. Be specific — cite exact categories and sources for every quote.
3. Frequency must reflect actual mention counts from the data.
4. Do NOT fabricate quotes or data points.
5. Format output as clean Markdown.
"""


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def chunk_data(reviews, chunk_size=50):
    for i in range(0, len(reviews), chunk_size):
        yield reviews[i:i + chunk_size]


def call_groq(data_chunk, retry=5):
    import time
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze these {len(data_chunk)} user reviews:\n\n{json.dumps(data_chunk, indent=2)}"},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    for attempt in range(retry):
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        print(f"Groq API error {resp.status_code}: {resp.text}", file=sys.stderr)
        return None
    print("Groq API: max retries exceeded", file=sys.stderr)
    return None


def build_final_prompt(chunk_analyses, total_count):
    import time
    combined = "\n\n---\n\n".join(
        f"### Batch {i+1} Analysis ({len(a)} chars)\n{a}"
        for i, a in enumerate(chunk_analyses) if a
    )
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"You have received batch analyses of {total_count} total reviews. "
                "Below are the per-batch results. Now produce a SINGLE unified analysis "
                "that merges themes across batches, deduplicates quotes, recalculates "
                "frequencies, and produces the final structured output in the exact format "
                "specified in the system prompt.\n\n" + combined
            )},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    for attempt in range(5):
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        if resp.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"  Consolidation rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        print(f"Groq consolidation error {resp.status_code}: {resp.text}", file=sys.stderr)
        return None
    print("Groq consolidation: max retries exceeded", file=sys.stderr)
    return None


def main():
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY not set in .env")

    reviews = load_data()
    print(f"Loaded {len(reviews)} reviews")

    chunks = list(chunk_data(reviews, chunk_size=50))
    chunk_analyses = []
    import time
    for i, chunk in enumerate(chunks):
        if i > 0:
            print("  Waiting 15s between batches to avoid rate limits...")
            time.sleep(15)
        print(f"Processing batch {i+1}/{len(chunks)} ({len(chunk)} reviews)...")
        result = call_groq(chunk)
        if result:
            chunk_analyses.append(result)
            print(f"  Batch {i+1} complete ({len(result)} chars)")
        else:
            print(f"  Batch {i+1} failed, skipping")

    if not chunk_analyses:
        raise SystemExit("All batches failed. No analysis produced.")

    print("Consolidating across batches...")
    final_analysis = build_final_prompt(chunk_analyses, len(reviews))

    if not final_analysis:
        raise SystemExit("Consolidation failed.")

    header = (
        "# Swiggy Instamart Discovery Engine — AI Insights\n\n"
        f"**Total Reviews Analyzed:** {len(reviews)}\n\n"
        f"**Source:** AI-generated analysis via Groq ({MODEL})\n\n"
        "---\n\n"
    )
    with open(OUTPUT_FILE, "w") as f:
        f.write(header + final_analysis)

    print(f"Insights written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
