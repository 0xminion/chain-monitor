"""Direct xAI Grok API provider — calls api.x.ai with X Search tool."""

import json
import logging
import os
from datetime import datetime, timezone

import httpx

from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage

logger = logging.getLogger(__name__)

# Token-efficient system prompt: JSON-only extraction, no commentary
EXTRACTION_SYSTEM_PROMPT = (
    "Extract tweets from search results as a raw JSON array. "
    "Return ONLY the JSON. No markdown, no commentary, no code fences. "
    "Schema per tweet: {"
    '"id": "tweet_id_str", '
    '"handle": "author_handle_without_@", '
    '"text": "full_tweet_text", '
    '"created_at": "ISO8601", '
    '"is_retweet": bool, '
    '"retweeted_handle": "original_author_or_null", '
    '"likes": int, '
    '"retweets": int, '
    '"replies": int'
    "}. Omit tweets not from the requested handles."
)

# Minimal user message — the handles + date range are passed via tool params
USER_MESSAGE_TEMPLATE = "Search posts from these X handles within {from_date} to {to_date}."


class DirectXAIProvider(XSearchProvider):
    """Calls xAI Grok API directly for X Search extraction.

    Uses grok-4.3 with x_search tool. Requires XAI_API_KEY in env.
    Token pricing (May 2026): $1.25/1M input, $2.50/1M output, $5/1K x-search calls.
    """

    BASE_URL = "https://api.x.ai/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "grok-4.3",
        timeout: float = 60.0,
    ):
        self._api_key = api_key or os.environ.get("XAI_API_KEY", "")
        self._model = model
        self._timeout = timeout

        if not self._api_key:
            raise ValueError(
                "XAI_API_KEY not set. Provide api_key= or set XAI_API_KEY env var."
            )

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    @property
    def name(self) -> str:
        return "direct_xai"

    @property
    def model(self) -> str:
        return self._model

    async def search(
        self,
        handles: list[str],
        from_date: str,
        to_date: str,
    ) -> SearchResult:
        """Send one X Search request to Grok API.

        Uses allowed_x_handles to scope to specific accounts (max 10).
        from_date/to_date restrict time window.
        """
        if len(handles) > 10:
            raise ValueError(f"Max 10 handles per call, got {len(handles)}")

        # Build the x_search tool specification
        x_search_tool = {
            "type": "x_search",
            "allowed_x_handles": handles,
            "from_date": from_date,
            "to_date": to_date,
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_MESSAGE_TEMPLATE.format(
                        from_date=from_date,
                        to_date=to_date,
                    ),
                },
            ],
            "tools": [x_search_tool],
            "temperature": 0.0,  # Deterministic extraction
            "stream": False,
        }

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[DirectXAI] HTTP {e.response.status_code}: {e.response.text[:300]}")
            return SearchResult(error=f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"[DirectXAI] Request failed: {e}")
            return SearchResult(error=str(e))

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> SearchResult:
        """Parse Grok API response into SearchResult with tweets + token usage."""
        usage_raw = data.get("usage", {})

        # Extract the assistant message content
        choices = data.get("choices", [])
        content = ""
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

        # Parse JSON array from response (handle markdown wrapping)
        tweets = []
        if content:
            tweets = self._parse_tweets_json(content)

        return SearchResult(
            tweets=tweets,
            usage=TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens", 0),
                output_tokens=usage_raw.get("completion_tokens", 0),
                cached_tokens=usage_raw.get("prompt_tokens_details", {}).get(
                    "cached_tokens", 0
                ),
            ),
        )

    @staticmethod
    def _parse_tweets_json(content: str) -> list[dict]:
        """Extract JSON array from response content (robust to markdown wrapping)."""
        # Try direct parse first
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "tweets" in parsed:
                return parsed["tweets"]
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # Find first newline after opening fence
            nl = cleaned.find("\n")
            if nl > 0:
                cleaned = cleaned[nl + 1 :]
            # Remove closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Last resort: find JSON array boundaries
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

        return []

    async def close(self):
        await self._client.aclose()
