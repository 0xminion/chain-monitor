"""LLM client — thin wrapper for Ollama and OpenRouter.

Implements direct HTTP calls to Ollama (user preference: avoid subprocess overhead)
with optional fallback to OpenRouter.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(key, default)


class LLMError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""
    pass


class LLMResponseError(LLMError):
    """LLM returned invalid or unexpected response."""
    pass


class LLMClient:
    """Unified LLM client with Ollama (primary) and OpenRouter (fallback) support."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        temperature: float = 0.1,
        timeout: float = 30.0,
        max_retries: int = 1,
    ):
        self.provider = provider or get_env("LLM_PROVIDER", "ollama")
        self.model = model or get_env("LLM_MODEL", "gemma4:31b-cloud")
        self.fallback_model = fallback_model or get_env("LLM_FALLBACK_MODEL", "gemma4:31b-cloud")
        self.temperature = temperature
        self.timeout = timeout or float(get_env("OLLAMA_TIMEOUT", "120.0"))
        self.max_retries = max_retries
        self._session = requests.Session()

    def generate(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, num_predict: Optional[int] = None) -> str:
        """Generate text from LLM. Returns raw text response.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system instruction.
            model: Override model name for this call.
            num_predict: Override max tokens for this call (default 2048).
        """
        model = model or self.model
        try:
            return self._generate_ollama(prompt, system_prompt, model, num_predict=num_predict)
        except (LLMTimeoutError, LLMResponseError) as e:
            logger.warning(f"Primary LLM failed ({model}): {e}")
            if model != self.fallback_model and self.fallback_model:
                logger.info(f"Trying fallback LLM: {self.fallback_model}")
                try:
                    return self._generate_ollama(prompt, system_prompt, self.fallback_model, num_predict=num_predict)
                except Exception as fe:
                    logger.error(f"Fallback LLM also failed: {fe}")
                    raise LLMError(f"Both primary and fallback LLM failed: {e}")
            raise

    def _generate_ollama(self, prompt: str, system_prompt: Optional[str], model: str, num_predict: Optional[int] = None) -> str:
        """Call Ollama generate endpoint directly via HTTP."""
        url = f"{OLLAMA_HOST}/api/generate"
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": num_predict or 2048,
                "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", 262144)),
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                if "response" not in data:
                    raise LLMResponseError(f"Ollama response missing 'response' key: {data.keys()}")
                raw = data["response"].strip()
                if not raw:
                    raise LLMResponseError("Ollama returned empty response")
                return raw
            except requests.exceptions.Timeout as e:
                logger.warning(f"Ollama timeout (attempt {attempt+1}/{self.max_retries+1}): {e}")
                if attempt >= self.max_retries:
                    raise LLMTimeoutError(f"Ollama timed out after {self.max_retries+1} attempts")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Ollama connection error (attempt {attempt+1}): {e}")
                if attempt >= self.max_retries:
                    raise LLMResponseError(f"Ollama unreachable: {e}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Ollama request error (attempt {attempt+1}): {e}")
                if attempt >= self.max_retries:
                    raise LLMResponseError(f"Ollama request failed: {e}")

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> dict:
        """Generate structured JSON response from LLM.

        Returns parsed dict. Raises LLMResponseError on parse failure.
        """
        raw = self.generate(prompt, system_prompt, model)
        text = raw.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        for tag in ("<think>", "</think>", "<thinking>", "</thinking>"):
            text = text.replace(tag, "")
        # Strip "Thinking Process:" or similar preamble before JSON
        for marker in ("Thinking Process:", "Thinking process:", "thinking process:"):
            idx = text.find(marker)
            if idx != -1:
                # Find the next JSON boundary after the thinking block
                rest = text[idx + len(marker):]
                json_start = -1
                for j, ch in enumerate(rest):
                    if ch in "[{":
                        json_start = j
                        break
                if json_start != -1:
                    text = rest[json_start:]
                    break

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM JSON parse failed: {e}\nRaw response:\n{text[:500]}")
            raise LLMResponseError(f"Failed to parse LLM JSON response: {e}")

    def generate_json_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
        backoff: float = 2.0,
    ) -> dict:
        """Generate JSON with auto-retry on empty/truncated responses.

        Handles cloud model flakiness by retrying with exponential backoff.
        Raises LLMResponseError if all retries exhausted.
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                raw = self.generate(prompt, system_prompt, model)
                text = raw.strip()

                # Strip markdown fences
                if text.startswith("```"):
                    lines = text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    text = "\n".join(lines).strip()

                # Strip thinking tags
                for tag in ("<think>", "</think>", "<thinking>", "</thinking>"):
                    text = text.replace(tag, "")

                # Strip thinking prose preamble
                for marker in ("Thinking Process:", "Thinking process:", "thinking process:"):
                    idx = text.find(marker)
                    if idx != -1:
                        rest = text[idx + len(marker):]
                        json_start = -1
                        for j, ch in enumerate(rest):
                            if ch in "[{":
                                json_start = j
                                break
                        if json_start != -1:
                            text = rest[json_start:]
                            break

                # If still empty after stripping, retry
                if not text:
                    raise LLMResponseError("Empty response after stripping")

                return json.loads(text)
            except (json.JSONDecodeError, LLMResponseError) as e:
                last_exc = e
                wait = backoff * (2 ** attempt)
                logger.warning(f"LLM JSON attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {wait:.1f}s...")
                if attempt < max_retries:
                    import time
                    time.sleep(wait)

        logger.error(f"LLM JSON exhausted all {max_retries + 1} attempts: {last_exc}")
        raise LLMResponseError(f"Failed to parse LLM JSON after {max_retries + 1} attempts: {last_exc}")

    @classmethod
    def from_env(cls) -> "LLMClient":
        """Create LLMClient from environment variables."""
        return cls(
            provider=get_env("LLM_PROVIDER", "ollama"),
            model=get_env("LLM_MODEL", "minimax-m2.7:cloud"),
            fallback_model=get_env("LLM_FALLBACK_MODEL", "gemma4:31b-cloud"),
            temperature=float(get_env("LLM_TEMPERATURE", "0.1")),
            timeout=float(get_env("LLM_TIMEOUT", "120")),
        )
