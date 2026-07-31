import json
import os
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOCK_REVIEWS = [
    {
        "id": "r1", "source": "Google Play Store",
        "text": "I had a terrible experience buying from Instamart. I paid for my order "
                "but never received it. I didn't receive a refund either.",
        "sentiment": "negative", "categories": ["groceries"], "rating": 1,
        "intent": "complaint",
    },
    {
        "id": "r2", "source": "Google Play Store",
        "text": "very slow delivery, late delivery and not worth the money",
        "sentiment": "negative", "categories": ["delivery"], "rating": 1,
        "intent": "complaint",
    },
    {
        "id": "r3", "source": "Google Play Store",
        "text": "refund policy is confusing, no refund option appeared",
        "sentiment": "negative", "categories": ["general"], "rating": 2,
        "intent": "complaint",
    },
    {
        "id": "r4", "source": "Reddit",
        "text": "The app only shows groceries, never shampoo or soap",
        "sentiment": "negative", "categories": ["personal_care"], "rating": 1,
        "intent": "complaint",
    },
    {
        "id": "r5", "source": "Google Play Store",
        "text": "Best app for groceries and snacks, fast delivery",
        "sentiment": "positive", "categories": ["groceries", "snacks"], "rating": 5,
        "intent": "praise",
    },
]

MOCK_INSIGHTS = {
    "themes": [
        {"name": "Delivery Issues", "mentions": 30, "frequency": "Medium"},
        {"name": "Refund Issues", "mentions": 12, "frequency": "Low"},
    ],
    "sentiment": {
        "positive": {"count": 1, "percentage": 20},
        "neutral": {"count": 0, "percentage": 0},
        "negative": {"count": 4, "percentage": 80},
    },
    "categories": [],
}


def _mock_read_json(path, default=None):
    if "cleaned_feedback" in path:
        return MOCK_REVIEWS
    if "ai_insights" in path:
        return MOCK_INSIGHTS
    return default


class TestAI009Search(unittest.TestCase):

    def setUp(self):
        import scripts.api_server as srv
        srv._ollama_client = None
        srv._openai_client = None

    def test_search_rejects_empty_query(self):
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._json = MagicMock()
        handler._parse_body = lambda: {"query": ""}
        handler._post_search()

        handler._json.assert_called_once()
        call_args = handler._json.call_args[0][0]
        self.assertIn("error", call_args)
        self.assertEqual(handler._json.call_args[0][1], 400)

    def test_search_rejects_missing_query(self):
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._json = MagicMock()
        handler._parse_body = lambda: {}
        handler._post_search()

        handler._json.assert_called_once()
        call_args = handler._json.call_args[0][0]
        self.assertIn("error", call_args)

    @patch("scripts.api_server._read_json")
    def test_query_keywords_ignore_question_stopwords(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        self.assertEqual(
            handler._query_keywords("What are the top delivery complaints?"),
            ["delivery", "complaint"],
        )
        self.assertEqual(
            handler._query_keywords("How does Swiggy compare on refund issues?"),
            ["swiggy", "refund", "issu"],
        )

    @patch("scripts.api_server._read_json")
    def test_rank_reviews_prefers_on_topic_reviews(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        kwds = handler._query_keywords("refund issues")
        ranked = handler._rank_reviews(MOCK_REVIEWS, kwds, limit=10)
        ids = [r["id"] for r in ranked]
        self.assertIn("r1", ids)
        self.assertIn("r3", ids)
        self.assertNotIn("r2", ids)
        self.assertNotIn("r5", ids)

    @patch("scripts.api_server._read_json")
    def test_ai_search_returns_ai_answer_when_llm_available(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client._generate.return_value = "Delivery is the most common complaint."

        handler = srv.APIHandler.__new__(srv.APIHandler)
        result = handler._call_ai_search(mock_client, "What are the top delivery complaints?", {})
        self.assertEqual(result["mode"], "ai")
        self.assertIn("Delivery is the most common complaint.", result["answer"])

    @patch("scripts.api_server._read_json")
    def test_ai_search_falls_back_to_extractive_when_llm_fails(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client._generate.side_effect = RuntimeError("insufficient_quota")

        handler = srv.APIHandler.__new__(srv.APIHandler)
        result = handler._call_ai_search(mock_client, "refund issues", {})
        self.assertEqual(result["mode"], "extractive")
        self.assertIn("Based on", result["answer"])
        self.assertIn("refund", result["answer"].lower())

    @patch("scripts.api_server._read_json")
    def test_extractive_answer_answers_category_question_from_data(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        kwds = handler._query_keywords("Which categories have the worst sentiment?")
        relevant = handler._rank_reviews(MOCK_REVIEWS, kwds, limit=10)
        answer = handler._extractive_answer("Which categories have the worst sentiment?", relevant, kwds)
        self.assertIn("Worst sentiment categories", answer)

    @patch("scripts.api_server._read_json")
    def test_get_ai_client_prefers_openai_when_key_set(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        from scripts.openai_client import OpenAIClient
        from scripts.ollama_client import OllamaClient
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            self.assertIsInstance(handler._get_ai_client(), OpenAIClient)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(handler._get_ai_client(), OllamaClient)

    @patch("scripts.api_server._read_json")
    def test_context_assembly_selects_relevant_reviews(self, mock_read_json):
        mock_read_json.side_effect = _mock_read_json
        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        context = handler._build_search_context("delivery")

        self.assertIn("context", context)
        self.assertIn("source_list", context)
        self.assertIn("delivery", context["context"].lower())


if __name__ == "__main__":
    unittest.main()
