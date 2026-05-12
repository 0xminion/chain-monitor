"""Antseed buyer proxy provider — uses P2P network to find Grok sellers.

Workflow:
  1. antseed buyer start --port <port>    (starts local proxy)
  2. This provider sends OpenAI-compatible requests to localhost:<port>
  3. Antseed routes to the best-priced seller offering Grok services

The buyer proxy endpoint is OpenAI-compatible (/v1/chat/completions).
Buy credits via surplusintelligence.ai, deposit USDC via antseed buyer deposit.

Requires: antseed daemon running + buyer proxy started.
"""

import json
import logging
import os
from typing import Optional

import httpx

from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage

logger = logging.getLogger(__name__)

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


class AntseedBuyerProvider(XSearchProvider):
    """Routes X Search requests through antseed buyer proxy to P2P Grok sellers.

    The antseed buyer proxy exposes an OpenAI-compatible endpoint.
    When the seller wraps xAI API, x_search tools are forwarded transparently.
    """

    # Whitelist of model names that resolve on the antseed P2P network.
    # Any name NOT in this list may trigger the $10/$10 default pricing tier
    # because the peer listing won't match the service.
    _VALID_MODELS = frozenset({"grok-4.20", "grok-4.3", "grok-4.1", "grok-4.1-fast-non-reasoning"})

    def __init__(
        self,
        proxy_url: str | None = None,
        model: str = "grok-4.20",
        api_key: str = "antseed-local",  # placeholder — proxy doesn't auth
        timeout: float = 60.0,
    ):
        if model not in self._VALID_MODELS:
            raise ValueError(
                f"Model '{model}' is not in the antseed P2P service whitelist. "
                f"Unknown models trigger $10/$10 default pricing. "
                f"Valid models: {sorted(self._VALID_MODELS)}. "
                f"Check the peer listing via 'antseed buyer services --json'."
            )
        self._proxy_url = (proxy_url or
            os.environ.get("ANTSEED_PROXY_URL", "http://localhost:8080"))
        self._model = model
        self._timeout = timeout

        base = self._proxy_url.rstrip("/")
        self._chat_url = f"{base}/v1/chat/completions"

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    @property
    def name(self) -> str:
        return "antseed_buyer"

    @property
    def model(self) -> str:
        return self._model

    async def search(
        self,
        handles: list[str],
        from_date: str,
        to_date: str,
    ) -> SearchResult:
        if len(handles) > 10:
            raise ValueError(f"Max 10 handles per call, got {len(handles)}")

        # Venice AI (surplusintelligence route) uses OpenAI-compatible function schema.
        # The x_search tool is defined as a function call with these parameters.
        x_search_tool = {
            "type": "function",
            "function": {
                "name": "x_search",
                "description": "Search X/Twitter posts and user profiles",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "X search query (e.g. 'from:username since:2026-05-11 until:2026-05-12')"
                        },
                    },
                    "required": ["query"],
                },
            },
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Find all posts (tweets and retweets) from these X/Twitter handles "
                        f"between {from_date} and {to_date}: {', '.join(handles)}. "
                        f"Return ALL matching posts as a raw JSON array. No commentary or markdown."
                    ),
                },
            ],
            "tools": [x_search_tool],
            "tool_choice": {"type": "function", "function": {"name": "x_search"}},
            "temperature": 0.0,
            "stream": False,
        }

        try:
            response = await self._client.post(self._chat_url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[Antseed] HTTP {e.response.status_code}: {e.response.text[:300]}")
            return SearchResult(error=f"HTTP {e.response.status_code}")
        except httpx.ConnectError:
            logger.error(
                f"[Antseed] Cannot connect to {self._proxy_url}. "
                "Is 'antseed buyer start' running?"
            )
            return SearchResult(error="antseed proxy unreachable")
        except httpx.RequestError as e:
            logger.error(f"[Antseed] Request failed: {e}")
            return SearchResult(error=str(e))

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> SearchResult:
        usage_raw = data.get("usage", {})
        choices = data.get("choices", [])
        content = ""
        tweets = []

        if not choices:
            return SearchResult(
                tweets=[],
                usage=TokenUsage(
                    input_tokens=usage_raw.get("prompt_tokens", 0),
                    output_tokens=usage_raw.get("completion_tokens", 0),
                    cached_tokens=(
                        usage_raw.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    ),
                ),
            )

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Try 1: parse JSON from content (model generates tweet array directly)
        tweets = self._parse_tweets_json(content)

        # Try 2: extract from tool_call result (Venice x_search invocation)
        if not tweets:
            tool_calls = message.get("tool_calls", [])
            for tc in tool_calls:
                func = tc.get("function", {})
                if func.get("name") == "x_search":
                    raw_args = func.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        # x_search result may be in 'results', 'tweets', 'data', or the args itself
                        results = (
                            args.get("results")
                            or args.get("tweets")
                            or args.get("data")
                            or []
                        )
                        if isinstance(results, list):
                            tweets = results
                        elif isinstance(args, list):
                            # x_search returned the array directly as arguments
                            tweets = args
                    except (json.JSONDecodeError, TypeError):
                        pass

        # Try 3: if content is empty but we have tool calls, the model may be asking
        # the tool to run — check if there's a second message with the result
        # (Venice returns tool call + content in one response for x_search)
        if not tweets and not content:
            # Last resort: look for any JSON array in the raw response
            raw = json.dumps(data)
            start = raw.find("[")
            end = raw.rfind("]")
            if start >= 0 and end > start:
                try:
                    potential = json.loads(raw[start:end + 1])
                    if isinstance(potential, list) and len(potential) > 0:
                        tweets = potential
                except json.JSONDecodeError:
                    pass

        return SearchResult(
            tweets=tweets,
            usage=TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens", 0),
                output_tokens=usage_raw.get("completion_tokens", 0),
                cached_tokens=(
                    usage_raw.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                ),
            ),
        )

    @staticmethod
    def _parse_tweets_json(content: str) -> list[dict]:
        if not content:
            return []
        cleaned = content.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            nl = cleaned.find("\n")
            if nl > 0:
                cleaned = cleaned[nl + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for key in ("tweets", "results", "data"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
        except json.JSONDecodeError:
            pass
        # Find JSON array boundaries
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        return []

    async def close(self):
        await self._client.aclose()
