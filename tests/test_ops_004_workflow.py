import json
import os
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "research_processor.py")

MOCK_SURVEY = {
    "respondent_id": "TEST-001",
    "age_range": "25-34",
    "primary_platform": "Swiggy Instamart",
    "monthly_orders": "9-15",
    "categories_purchased": "Groceries, Snacks, Beverages",
    "repetition_score": 2,
    "discovery_barriers": "The app always shows me the same items I bought before. I never see new categories like pet supplies or personal care even though I might need them.",
    "discovery_methods": "Browsing, App recommendations",
    "trial_motivation": "If the app showed me a bundle that includes something new alongside my regular items, I would probably try it.",
    "discovery_story": "Once I searched for dog food manually because my neighbor mentioned it. The app never suggested it even though I buy groceries every week."
}

MOCK_GROQ_RESPONSE = {
    "choices": [{
        "message": {
            "content": json.dumps({
                "summary": "This respondent orders frequently but feels stuck in repetitive patterns. They explicitly mention the app showing only past purchases and failing to surface new categories. They discovered a product only through manual search prompted by a social cue.",
                "matched_themes": [
                    "Repetitive Cart Experience",
                    "Cross-Category Blind Spots",
                    "Discovery Feature Gap",
                    "Habit-Driven Shopping"
                ],
                "contradicted_themes": [],
                "quality_score": 85,
                "score_rationale": "Strong personal evidence supporting multiple AI-discovered themes with specific examples.",
                "recommendation": "Prioritize cross-category bundles in the Try Next Basket MVP to break repetitive cart patterns."
            })
        }
    }]
}


class TestOPS004Workflow(unittest.TestCase):
    @patch("scripts.research_processor.requests.post")
    def test_process_survey_returns_valid_structure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GROQ_RESPONSE
        mock_resp.text = ""
        mock_post.return_value = mock_resp

        import importlib
        import scripts.research_processor as module
        importlib.reload(module)

        result = module.process_survey(MOCK_SURVEY, api_key="test-key")

        self.assertIsInstance(result, dict)
        self.assertIn("summary", result)
        self.assertIn("matched_themes", result)
        self.assertIn("quality_score", result)
        self.assertIn("recommendation", result)
        self.assertIsInstance(result["matched_themes"], list)
        self.assertIsInstance(result["quality_score"], int)
        self.assertGreaterEqual(result["quality_score"], 0)
        self.assertLessEqual(result["quality_score"], 100)

    @patch("scripts.research_processor.requests.post")
    def test_quality_score_in_range(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GROQ_RESPONSE
        mock_resp.text = ""
        mock_post.return_value = mock_resp

        import importlib
        import scripts.research_processor as module
        importlib.reload(module)

        result = module.process_survey(MOCK_SURVEY, api_key="test-key")
        score = result["quality_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    @patch("scripts.research_processor.requests.post")
    def test_mocked_webhook_json_processes(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GROQ_RESPONSE
        mock_resp.text = ""
        mock_post.return_value = mock_resp

        import importlib
        import scripts.research_processor as module
        importlib.reload(module)

        mock_file = os.path.join(ROOT, "database", "mock_survey.json")
        with open(mock_file, "w") as f:
            json.dump(MOCK_SURVEY, f, indent=2)

        result = module.process_from_file(mock_file)
        self.assertEqual(result["respondent_id"], "TEST-001")
        self.assertIn("summary", result)
        os.remove(mock_file)


if __name__ == "__main__":
    unittest.main()
