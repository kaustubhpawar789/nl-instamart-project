import json
import os
import sys
from dotenv import load_dotenv
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
INSIGHTS_FILE = os.path.join(ROOT, "docs", "ai_insights.md")

PHASE1_THEMES = [
    "Repetitive Cart Experience",
    "Cross-Category Blind Spots",
    "Discovery Feature Gap",
    "Habit-Driven Shopping",
    "Information Barrier to Trial",
    "Segment-Driven Experimentation",
    "Unmet Cross-Sell Needs",
]

SUMMARIZER_PROMPT = """You are a user research analyst validating AI-discovered insights about quick-commerce shopping behavior.

You will receive a single survey response from a user. Your tasks:

1. **Summarize** the respondent's answers in 2-3 concise sentences.

2. **Match Themes**: Check which of these Phase 1 AI-discovered themes the response supports or contradicts:
   - Repetitive Cart Experience
   - Cross-Category Blind Spots
   - Discovery Feature Gap
   - Habit-Driven Shopping
   - Information Barrier to Trial
   - Segment-Driven Experimentation
   - Unmet Cross-Sell Needs

3. **Quality Score** (0-100): Rate how well this response validates the AI insights:
   - 80-100: Strongly validates multiple themes with specific personal examples
   - 60-79: Moderately validates themes with general observations
   - 40-59: Partially relevant, some tangential validation
   - 20-39: Weak connection to themes, mostly generic feedback
   - 0-19: Does not validate or contradicts AI insights

4. **Recommendation**: One sentence on how this response should influence the MVP.

Return ONLY valid JSON in this exact format:
{
  "summary": "2-3 sentence summary of the response",
  "matched_themes": ["Theme Name", "Theme Name"],
  "contradicted_themes": ["Theme Name"],
  "quality_score": 75,
  "score_rationale": "One sentence explaining the score",
  "recommendation": "One sentence recommendation for MVP"
}
"""


def load_insights_context():
    if os.path.isfile(INSIGHTS_FILE):
        with open(INSIGHTS_FILE, "r") as f:
            content = f.read()
        return content[:2000]
    return "Phase 1 AI insights not available yet."


def process_survey(survey_data, api_key=None):
    key = api_key or GROQ_API_KEY
    if not key:
        raise ValueError("GROQ_API_KEY not set")

    insights_context = load_insights_context()

    user_message = (
        f"## Phase 1 AI Insights Context (abbreviated)\n{insights_context}\n\n"
        f"## Survey Response\n"
        f"Respondent: {survey_data.get('respondent_id', 'Unknown')}\n"
        f"Age: {survey_data.get('age_range', 'N/A')}\n"
        f"Platform: {survey_data.get('primary_platform', 'N/A')}\n"
        f"Monthly Orders: {survey_data.get('monthly_orders', 'N/A')}\n"
        f"Categories Purchased: {survey_data.get('categories_purchased', 'N/A')}\n"
        f"Repetition Score (1=same, 5=different): {survey_data.get('repetition_score', 'N/A')}\n"
        f"Discovery Barriers: {survey_data.get('discovery_barriers', 'N/A')}\n"
        f"Discovery Methods: {survey_data.get('discovery_methods', 'N/A')}\n"
        f"Trial Motivation: {survey_data.get('trial_motivation', 'N/A')}\n"
        f"Discovery Story: {survey_data.get('discovery_story', 'N/A')}\n"
    )

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SUMMARIZER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    import time
    for attempt in range(4):
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"]
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw[:-3]
            return json.loads(raw)
        if resp.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")

    raise RuntimeError("Groq API: max retries exceeded")


def process_from_file(input_path, output_path=None):
    with open(input_path, "r") as f:
        survey = json.load(f)
    result = process_survey(survey)
    result["respondent_id"] = survey.get("respondent_id", "Unknown")
    if output_path:
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Result written to {output_path}")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Process survey response via Groq AI")
    parser.add_argument("--input", help="Path to survey JSON file")
    parser.add_argument("--output", help="Path to write result JSON")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    args = parser.parse_args()

    if args.stdin:
        survey = json.load(sys.stdin)
    elif args.input:
        with open(args.input, "r") as f:
            survey = json.load(f)
    else:
        raise SystemExit("Provide --input or --stdin")

    result = process_survey(survey)
    result["respondent_id"] = survey.get("respondent_id", "Unknown")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
