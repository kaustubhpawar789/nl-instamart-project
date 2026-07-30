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
        self._chat_endpoint = f"{self.base_url}/v1/chat/completions"
        self._generate_endpoint = f"{self.base_url}/api/generate"

    def chat(self, messages, temperature=0.4, max_tokens=2000, timeout=90, format=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if format:
            payload["format"] = format

        last_error = None
        for attempt in range(3):
            try:
                resp = _http.post(self._chat_endpoint, json=payload, timeout=timeout)
                if resp.status_code == 429:
                    wait = 5 * (attempt + 1)
                    time.sleep(wait)
                    continue
                if resp.status_code == 404:
                    return self._fallback_generate(messages, temperature, max_tokens, timeout, format)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except _http.exceptions.ConnectionError as e:
                last_error = _http.exceptions.ConnectionError(
                    f"Ollama is not running (connection refused). Start with: ollama serve. Details: {e}"
                )
                time.sleep(1 * (attempt + 1))
            except _http.exceptions.Timeout as e:
                last_error = _http.exceptions.Timeout(
                    f"Ollama request timed out after {timeout}s. The model may still be loading or under heavy load."
                )
                break
            except _http.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 404:
                    return self._fallback_generate(messages, temperature, max_tokens, timeout, format)
                last_error = _http.exceptions.HTTPError(
                    f"Ollama returned HTTP {status}. Model '{self.model}' may not be available. Run: ollama pull {self.model}"
                )
                time.sleep(1 * (attempt + 1))
            except (KeyError, json.JSONDecodeError) as e:
                last_error = RuntimeError(f"Ollama returned an unexpected response: {e}")
                break

        raise last_error or RuntimeError("Ollama request failed after 3 retries")

    def _pull_model(self):
        """Pull the configured model via Ollama API, returns True on success."""
        try:
            pull_url = f"{self.base_url}/api/pull"
            resp = _http.post(pull_url, json={"name": self.model, "stream": False}, timeout=300)
            return resp.status_code == 200
        except Exception:
            return False

    def _fallback_generate(self, messages, temperature, max_tokens, timeout, format=None):
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
        resp = _http.post(self._generate_endpoint, json=payload, timeout=timeout)
        if resp.status_code == 404 and "not found" in resp.text:
            if self._pull_model():
                resp = _http.post(self._generate_endpoint, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", "")
            raise RuntimeError(
                f"Ollama model '{self.model}' not found and auto-pull failed. "
                f"Run: ollama pull {self.model}"
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama /api/generate returned HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        data = resp.json()
        return data.get("response", "")

    def is_available(self):
        try:
            resp = _http.get(f"{self.base_url}/api/tags", timeout=3)
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
