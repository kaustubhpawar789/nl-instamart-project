import json
import os
import time

import requests as _http
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
OLLAMA_ENDPOINT = f"{OLLAMA_BASE_URL}/v1/chat/completions"


class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self._api_key = os.getenv("OLLAMA_API_KEY") or os.getenv("GROQ_API_KEY") or ""
        self._chat_endpoint = f"{self.base_url}/v1/chat/completions"
        self._generate_endpoint = f"{self.base_url}/api/generate"

    def chat(self, messages, temperature=0.4, max_tokens=2000, timeout=300, format=None):
        last_err = None
        is_external = "localhost" not in self.base_url and "127.0.0.1" not in self.base_url
        try_order = [self._chat_completions, self._generate] if is_external else [self._generate, self._chat_completions]
        for attempt in range(3):
            for fn in try_order:
                try:
                    return fn(messages, temperature, max_tokens, timeout, format)
                except Exception as e:
                    last_err = e
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"AI request failed after 3 retries: {last_err}")

    def _pull_model(self):
        """Pull the configured model via Ollama API, returns True on success."""
        try:
            print(f"[ollama] Pulling model '{self.model}'...")
            pull_url = f"{self.base_url}/api/pull"
            resp = _http.post(pull_url, json={"name": self.model, "stream": False}, timeout=300, headers=self._headers())
            if resp.status_code == 200:
                print(f"[ollama] Model '{self.model}' pulled successfully")
            return resp.status_code == 200
        except Exception as e:
            print(f"[ollama] Pull failed: {e}")
            return False

    def _generate(self, messages, temperature, max_tokens, timeout, format=None):
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        prompt_parts = []
        for m in system_msgs:
            prompt_parts.append(f"System: {m['content']}")
        for m in user_msgs:
            prompt_parts.append(f"User: {m['content']}")
        prompt = "\n".join(prompt_parts)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if format:
            payload["format"] = format

        for attempt in range(2):
            resp = _http.post(self._generate_endpoint, json=payload, timeout=timeout, headers=self._headers())
            if resp.status_code == 404 and "not found" in resp.text.lower():
                if self._pull_model():
                    resp = _http.post(self._generate_endpoint, json=payload, timeout=timeout, headers=self._headers())
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("response", "")
                raise RuntimeError(
                    f"Ollama model '{self.model}' not found and auto-pull failed."
                )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "")
            if attempt == 0 and resp.status_code in (500, 503):
                time.sleep(3)

        raise RuntimeError(
            f"Ollama /api/generate returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    def _chat_completions(self, messages, temperature, max_tokens, timeout, format=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if format:
            payload["format"] = format

        for attempt in range(2):
            resp = _http.post(self._chat_endpoint, json=payload, timeout=timeout, headers=self._headers())
            if resp.status_code == 404 and "not found" in resp.text.lower():
                if self._pull_model():
                    resp = _http.post(self._chat_endpoint, json=payload, timeout=timeout, headers=self._headers())
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
                raise RuntimeError(
                    f"Ollama model '{self.model}' not found and auto-pull failed."
                )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            if attempt == 0 and resp.status_code in (500, 503):
                time.sleep(3)

        raise RuntimeError(
            f"Ollama /v1/chat/completions returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _warmup(self):
        """Pre-load the model into memory so the first user query is fast."""
        try:
            resp = _http.post(self._generate_endpoint, json={
                "model": self.model, "prompt": "hi", "stream": False
            }, timeout=300, headers=self._headers())
            if resp.status_code == 200:
                print(f"[ollama] Model '{self.model}' warmed up and ready")
        except Exception as e:
            print(f"[ollama] Warmup failed (will load on first request): {e}")

    def is_available(self):
        try:
            resp = _http.post(self._chat_endpoint, json={
                "model": self.model, "messages": [{"role": "user", "content": "hi"}], "stream": False
            }, timeout=10, headers=self._headers())
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self):
        try:
            resp = _http.get(f"{self.base_url}/api/tags", timeout=5, headers=self._headers())
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
