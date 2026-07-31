import os
import time

import requests as _http
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


class OpenAIClient:
    """OpenAI chat-completions client.

    Kept as a separate setup from the Ollama client on purpose — the Ollama
    path (scripts/ollama_client.py) stays untouched so both backends can
    coexist. The API server prefers OpenAI when OPENAI_API_KEY is set and
    falls back to Ollama otherwise.
    """

    def __init__(self, api_key=None, model=None, base_url=None):
        self.base_url = (base_url or OPENAI_BASE_URL).rstrip("/")
        self.model = model or OPENAI_MODEL
        self._api_key = api_key or OPENAI_API_KEY
        self._chat_endpoint = f"{self.base_url}/chat/completions"

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def chat(self, messages, temperature=0.4, max_tokens=2000, timeout=300, format=None):
        first_err = None
        for attempt in range(3):
            try:
                return self._generate(messages, temperature, max_tokens, timeout, format)
            except Exception as e:
                first_err = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"OpenAI request failed: {first_err}")

    def _generate(self, messages, temperature, max_tokens, timeout, format=None):
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if format:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(2):
            resp = _http.post(self._chat_endpoint, json=payload, headers=self._headers(), timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if content:
                    return content
            elif attempt == 0 and resp.status_code in (429, 500, 503):
                # Rate limited / transient — retry once after a short backoff.
                time.sleep(2)

        raise RuntimeError(
            f"OpenAI /chat/completions returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    def _warmup(self):
        # OpenAI has no local model to pre-load; nothing to do.
        return True

    def is_available(self):
        if not self._api_key:
            return False
        try:
            resp = _http.post(self._chat_endpoint, json={
                "model": self.model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "stream": False,
            }, timeout=15, headers=self._headers())
            return resp.status_code == 200
        except Exception:
            return False


_default_client = None


def get_openai_client(api_key=None, model=None, base_url=None):
    global _default_client
    if api_key or model or base_url or _default_client is None:
        _default_client = OpenAIClient(api_key=api_key, model=model, base_url=base_url)
    return _default_client
