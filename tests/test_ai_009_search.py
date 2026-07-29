import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock
from http.server import HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

MOCK_OLLAMA_ANSWER = (
    "Based on the Discovery Engine data, users avoid personal care products "
    "primarily because they are invisible in the app's discovery flow. "
    "Reviews show users who buy groceries and snacks never see personal care "
    "recommendations.\n\n"
    "Key findings:\n"
    "- 5 mentions in the personal care category\n"
    "- 80% negative sentiment\n"
    "- Users report having to search specifically to find these products\n\n"
    "This suggests a cross-category discovery failure."
)

MOCK_REVIEWS = [
    {
        "id": "r1", "source": "Google Play Store", "text": "I never see personal care products recommended",
        "sentiment": "negative", "categories": ["personal_care"], "rating": 2
    },
    {
        "id": "r2", "source": "Reddit", "text": "The app only shows groceries, never shampoo or soap",
        "sentiment": "negative", "categories": ["personal_care"], "rating": 1
    },
    {
        "id": "r3", "source": "Google Play Store", "text": "Best app for groceries and snacks",
        "sentiment": "positive", "categories": ["groceries", "snacks"], "rating": 5
    },
]

MOCK_INSIGHTS = {
    "themes": [
        {"name": "Discovery Gaps", "mentions": 45, "frequency": "High"},
        {"name": "Delivery Issues", "mentions": 30, "frequency": "Medium"},
    ],
    "sentiment": {
        "positive": {"count": 54, "percentage": 31.4},
        "neutral": {"count": 29, "percentage": 16.9},
        "negative": {"count": 89, "percentage": 51.7},
    },
    "categories": [],
}


class TestAI009Search(unittest.TestCase):

    def setUp(self):
        import scripts.api_server as srv
        srv._ollama_client = None

    @patch("scripts.api_server._read_json")
    def test_search_returns_answer(self, mock_read_json):
        def side_effect(path, default=None):
            if "cleaned_feedback" in path:
                return MOCK_REVIEWS
            if "ai_insights" in path:
                return MOCK_INSIGHTS
            return default
        mock_read_json.side_effect = side_effect

        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat.return_value = MOCK_OLLAMA_ANSWER

        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._get_ollama_client = lambda: mock_client
        handler._json = MagicMock()
        handler._parse_body = lambda: {"query": "Why do users avoid personal care?"}
        handler._post_search()

        handler._json.assert_called_once()
        call_args = handler._json.call_args[0][0]
        self.assertIn("answer", call_args)
        self.assertIn("query", call_args)
        self.assertIn("sources", call_args)
        self.assertTrue(len(call_args["answer"]) > 0)
        mock_client.chat.assert_called_once()

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

    def test_search_returns_error_when_ollama_down(self):
        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._get_ollama_client = lambda: mock_client
        handler._json = MagicMock()
        handler._parse_body = lambda: {"query": "test"}
        handler._post_search()

        handler._json.assert_called_once()
        call_args = handler._json.call_args[0][0]
        self.assertIn("error", call_args)
        self.assertIn("Ollama", call_args["error"])

    @patch("scripts.api_server._read_json")
    def test_search_handles_ollama_failure(self, mock_read_json):
        def side_effect(path, default=None):
            if "cleaned_feedback" in path:
                return MOCK_REVIEWS
            if "ai_insights" in path:
                return MOCK_INSIGHTS
            return default
        mock_read_json.side_effect = side_effect

        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat.side_effect = Exception("API error")

        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._get_ollama_client = lambda: mock_client
        handler._json = MagicMock()
        handler._parse_body = lambda: {"query": "test question"}
        handler._post_search()

        handler._json.assert_called_once()
        call_args = handler._json.call_args[0][0]
        self.assertIn("error", call_args)
        self.assertEqual(handler._json.call_args[0][1], 502)

    @patch("scripts.api_server._read_json")
    def test_context_assembly_selects_relevant_reviews(self, mock_read_json):
        def side_effect(path, default=None):
            if "cleaned_feedback" in path:
                return MOCK_REVIEWS
            if "ai_insights" in path:
                return MOCK_INSIGHTS
            return default
        mock_read_json.side_effect = side_effect

        import scripts.api_server as srv
        handler = srv.APIHandler.__new__(srv.APIHandler)
        context = handler._build_search_context("personal care products")

        self.assertIn("context", context)
        self.assertIn("source_list", context)
        self.assertIn("personal care", context["context"].lower())

    @patch("scripts.api_server._read_json")
    def test_search_passes_query_to_ollama(self, mock_read_json):
        def side_effect(path, default=None):
            if "cleaned_feedback" in path:
                return MOCK_REVIEWS
            if "ai_insights" in path:
                return MOCK_INSIGHTS
            return default
        mock_read_json.side_effect = side_effect

        import scripts.api_server as srv

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat.return_value = "Some answer."

        handler = srv.APIHandler.__new__(srv.APIHandler)
        handler._get_ollama_client = lambda: mock_client
        handler._json = MagicMock()
        handler._parse_body = lambda: {"query": "What are delivery complaints?"}
        handler._post_search()

        call_kwargs = mock_client.chat.call_args
        payload = call_kwargs[0][0]
        user_msg = payload[-1]["content"]
        self.assertIn("delivery complaints", user_msg.lower())


if __name__ == "__main__":
    unittest.main()
