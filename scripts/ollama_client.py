import json
import os
import time

import requests as _http
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_ENDPOINT = f"{OLLAMA_BASE_URL}/v1/chat/completions"


class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self._chat_endpoint = f"{self.base_url}/v1/chat/completions"

    def chat(self, messages, temperature=0.4, max_tokens=2000, timeout=90):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        resp = _http.post(self._chat_endpoint, json=payload, timeout=timeout)
        retries = 0
        max_retries = 3
        while resp.status_code == 429 and retries < max_retries:
            retries += 1
            wait = 5 * retries
            time.sleep(wait)
            resp = _http.post(self._chat_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def is_available(self):
        try:
            resp = _http.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self):
        try:
            resp = _http.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
            return []
        except Exception:
            return []


_default_client = None


def get_client(base_url=None, model=None):
    global _default_client
    if base_url or model or _default_client is None:
        _default_client = OllamaClient(base_url=base_url, model=model)
    return _default_client
