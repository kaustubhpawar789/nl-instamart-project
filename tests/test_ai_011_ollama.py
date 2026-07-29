import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOCK_OLLAMA_RESPONSE = {
    "choices": [{
        "message": {
            "content": (
                "Based on the Discovery Engine data, users avoid personal care products "
                "primarily because they are invisible in the app's discovery flow."
            )
        }
    }]
}

MOCK_REVIEWS = [
    {
        "id": "r1", "source": "Google Play Store",
        "text": "I never see personal care products recommended",
        "sentiment": "negative", "categories": ["personal_care"], "rating": 2
    },
    {
        "id": "r2", "source": "Reddit",
        "text": "The app only shows groceries, never shampoo or soap",
        "sentiment": "negative", "categories": ["personal_care"], "rating": 1
    },
    {
        "id": "r3", "source": "Google Play Store",
        "text": "Best app for groceries and snacks",
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

AI_CATEGORIZE_RESPONSE = json.dumps([
    {"id": "r1", "intent": "complaint", "categories": ["personal_care"], "sentiment": "negative", "themes": ["discovery_gaps"]},
    {"id": "r2", "intent": "complaint", "categories": ["personal_care"], "sentiment": "negative", "themes": ["discovery_gaps"]},
    {"id": "r3", "intent": "praise", "categories": ["groceries", "snacks"], "sentiment": "positive", "themes": ["product_quality"]},
])


class TestOllamaClient(unittest.TestCase):

    @patch("scripts.ollama_client._http")
    def test_chat_returns_content(self, mock_http):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OLLAMA_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_resp

        from scripts.ollama_client import OllamaClient
        client = OllamaClient(base_url="http://localhost:11434", model="llama3.2:1b")

        result = client.chat(
            [{"role": "user", "content": "test query"}],
            temperature=0.4, max_tokens=2000
        )
        self.assertEqual(
            result,
            "Based on the Discovery Engine data, users avoid personal care products "
            "primarily because they are invisible in the app's discovery flow."
        )
        mock_http.post.assert_called_once()

    @patch("scripts.ollama_client._http")
    def test_is_available_returns_true(self, mock_http):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http.get.return_value = mock_resp

        from scripts.ollama_client import OllamaClient
        client = OllamaClient()
        self.assertTrue(client.is_available())

    @patch("scripts.ollama_client._http")
    def test_is_available_returns_false(self, mock_http):
        mock_http.get.side_effect = Exception("Connection refused")

        from scripts.ollama_client import OllamaClient
        client = OllamaClient()
        self.assertFalse(client.is_available())

    @patch("scripts.ollama_client._http")
    def test_chat_retries_on_429(self, mock_http):
        rate_resp = MagicMock()
        rate_resp.status_code = 429

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = MOCK_OLLAMA_RESPONSE
        ok_resp.raise_for_status = MagicMock()

        mock_http.post.side_effect = [rate_resp, ok_resp]

        from scripts.ollama_client import OllamaClient
        client = OllamaClient()
        result = client.chat([{"role": "user", "content": "test"}])
        self.assertIn("personal care", result)
        self.assertEqual(mock_http.post.call_count, 2)

    def test_get_client_singleton(self):
        from scripts.ollama_client import get_client, OllamaClient
        c1 = get_client()
        c2 = get_client()
        self.assertIs(c1, c2)

    def test_get_client_updates_on_new_args(self):
        from scripts.ollama_client import get_client, OllamaClient
        c1 = get_client()
        c2 = get_client(base_url="http://other:11434")
        c3 = get_client()
        self.assertIs(c2, c3)


class TestApiSearchWithOllama(unittest.TestCase):

    def setUp(self):
        import scripts.api_server as srv
        srv._ollama_client = None

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
        mock_client.chat.return_value = "Users avoid personal care because of discovery gaps."

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
        self.assertEqual(handler._json.call_args[0][1], 503)

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
        mock_client.chat.side_effect = Exception("Ollama API error")

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
        self.assertIsNotNone(call_kwargs)
        messages = call_kwargs[0][0]
        user_msg = messages[-1]["content"]
        self.assertIn("delivery complaints", user_msg.lower())


class TestDataPipelineWithOllama(unittest.TestCase):

    @patch("scripts.data_pipeline.get_client")
    def test_ai_categorize_batch_falls_back_when_ollama_down(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_get_client.return_value = mock_client

        from scripts.data_pipeline import ai_categorize_batch
        result = ai_categorize_batch(MOCK_REVIEWS)
        self.assertEqual(result, MOCK_REVIEWS)
        mock_client.chat.assert_not_called()

    @patch("scripts.data_pipeline.get_client")
    def test_ai_categorize_batch_calls_ollama(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat.return_value = AI_CATEGORIZE_RESPONSE
        mock_get_client.return_value = mock_client

        from scripts.data_pipeline import ai_categorize_batch
        result = ai_categorize_batch(MOCK_REVIEWS)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["sentiment"], "negative")
        self.assertEqual(result[0]["intent"], "complaint")
        self.assertEqual(result[2]["sentiment"], "positive")
        mock_client.chat.assert_called()


class TestResearchProcessorWithOllama(unittest.TestCase):

    @patch("scripts.research_processor.get_client")
    def test_process_survey_calls_ollama(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat.return_value = json.dumps({
            "summary": "User finds discovery difficult.",
            "matched_themes": ["Discovery Feature Gap"],
            "contradicted_themes": [],
            "quality_score": 75,
            "score_rationale": "Specific examples align with theme.",
            "recommendation": "Improve discovery features."
        })
        mock_get_client.return_value = mock_client

        from scripts.research_processor import process_survey
        result = process_survey({
            "respondent_id": "R1",
            "age_range": "25-34",
            "monthly_orders": "5-10",
        })

        self.assertEqual(result["quality_score"], 75)
        self.assertIn("Discovery Feature Gap", result["matched_themes"])

    @patch("scripts.research_processor.get_client")
    def test_process_survey_raises_when_ollama_down(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_get_client.return_value = mock_client

        from scripts.research_processor import process_survey
        with self.assertRaises(RuntimeError) as ctx:
            process_survey({"respondent_id": "R1"})
        self.assertIn("Ollama", str(ctx.exception))


class TestLiveScraperDocstring(unittest.TestCase):

    def test_live_scraper_no_longer_refers_to_groq(self):
        path = os.path.join(ROOT, "scripts", "live_scraper.py")
        with open(path) as f:
            content = f.read()
        self.assertNotIn("GROQ", content)


if __name__ == "__main__":
    unittest.main()
