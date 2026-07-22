import json
import os
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(ROOT, "docs", "ai_insights.md")
SCRIPT = os.path.join(ROOT, "scripts", "ai_theme_extraction.py")

MOCK_BATCH_RESPONSE = {
    "choices": [{
        "message": {
            "content": (
                "## Theme Analysis\n\n"
                "### Theme: Repetitive Cart Experience\n"
                "**Frequency:** High — 45 mentions across categories: groceries, snacks, beverages\n"
                "**Direct Evidence:**\n"
                '- "I keep ordering the same vegetables every week." — Source: Google Play Store, Category: groceries\n'
                '- "Same Coke and Pepsi every time." — Source: Reddit, Category: beverages\n'
                '- "I always end up buying the same chips." — Source: Apple App Store, Category: snacks\n\n'
                "**Sentiment Breakdown:** Positive: 5 | Neutral: 10 | Negative: 30\n\n"
                "**Key Blockers:**\n- No discovery features in the app\n\n"
                "**Key Triggers:**\n- Cross-category recommendations\n\n"
                "## Structured Insights\n\n"
                "### Insight 1: Cart Loop Trap\n\n"
                "**Observation:** 45 reviews mention being stuck in repetitive purchase patterns.\n\n"
                "**User Need:** Users want to discover new products beyond their usual cart.\n\n"
                "**Root Cause:** The app prioritizes reorder over discovery.\n\n"
                "**Opportunity:** A Try Next Basket feature can break the loop.\n\n"
                "**Implication:** MVP should focus on cross-category discovery.\n\n"
                "## Sentiment Summary\n"
                "- Positive: 20 (14%)\n- Neutral: 35 (24%)\n- Negative: 90 (62%)\n\n"
                "## Category Priority Matrix\n"
                "| Category | Mentions | Gap Severity | Business Impact |\n|----------|----------|-------------|----------------|\n| groceries | 30 | High | High |\n\n"
                "## Recommendations\n"
                "1. Build a cross-category recommendation engine\n"
            )
        }
    }]
}


class TestAI003Groq(unittest.TestCase):
    @patch("scripts.ai_theme_extraction.requests.post")
    def test_script_executes_with_mocked_api(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_BATCH_RESPONSE
        mock_resp.text = ""
        mock_post.return_value = mock_resp

        import importlib
        import scripts.ai_theme_extraction as module
        importlib.reload(module)

        module.main()

        self.assertTrue(os.path.isfile(OUTPUT_FILE), "ai_insights.md not generated")
        mock_post.assert_called()

    def test_output_file_has_required_sections(self):
        if not os.path.isfile(OUTPUT_FILE):
            self.skipTest("Run script first to generate ai_insights.md")
        with open(OUTPUT_FILE, "r") as f:
            content = f.read()
        required = [
            "Theme Analysis",
            "Direct Evidence",
            "Sentiment Breakdown",
            "Structured Insights",
            "Observation",
            "User Need",
            "Root Cause",
            "Opportunity",
            "Implication",
        ]
        for section in required:
            self.assertIn(section, content, f"Missing section: {section}")

    def test_output_contains_quotes(self):
        if not os.path.isfile(OUTPUT_FILE):
            self.skipTest("Run script first to generate ai_insights.md")
        with open(OUTPUT_FILE, "r") as f:
            content = f.read()
        self.assertIn('"', content, "No quotes found in output")


if __name__ == "__main__":
    unittest.main()
