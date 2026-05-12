"""Surplus Intelligence Twitter API v2 provider — direct Twitter API via x402.

Calls the Twitter API v2 proxy at surplusintelligence.ai using the x402 payment
protocol. This is a DIRECT API call — no Grok model, no tool-calling, no hallucination.

x402 flow (SDK-managed):
  1. GET /x402/api/twitter/v2/tweets/search/recent?... → 402 PAYMENT-REQUIRED
  2. SDK creates payment payload (EIP-3009 exact)
  3. Resend with PAYMENT-SIGNATURE → HTTP 200 with real Twitter data
  4. Parse Twitter API v2 response into SearchResult

Pricing (Twitter API v2 via SurplusIntelligence, May 2026):
  - 5 units per request (confirmed from 402 challenge body)
  - Amount in 402: "27500" microUSDC = $0.0275 per batch of 10 handles
  - 14 batches for 138 accounts → ~$0.385 per full run
  - No token/streaming costs — direct API

Requirements:
  - ANTSEED_PRIVATE_KEY env var or ~/.antseed/identity.key
  - x402>=2.0.0 Python package
  - eth-account

Cost comparison:
  - Direct xAI x_search (XAI_API_KEY): $5/1K calls → $0.07 for 14 calls
  - SurplusIntelligence Twitter v2 proxy: $0.0275/call → $0.385 for 14 calls
  - SurplusIntelligence Grok 2-step (no real execution): $0.007/call → $0.095
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage

logger = logging.getLogger(__name__)

X402_BASE = "https://www.surplusintelligence.ai"
TWITTER_BASE = f"{X402_BASE}/x402/api/twitter/v2"
TWITTER_SEARCH_PATH = "/tweets/search/recent"

# Module-level constant (used in __init__ for httpx base_url)
TWITTER_API_BASE = f"{X402_BASE}/x402/api/twitter/v2"

# ---------------------------------------------------------------------------
# x402 SDK — same import as SurplusIntelligenceProvider
# ---------------------------------------------------------------------------

def _to_iso(date_str: str) -> str:
    """Convert YYYY-MM-DD to Twitter API v2 ISO8601 format with Z suffix."""
    return f"{date_str}T00:00:00Z"


try:
    from x402 import x402ClientSync, parse_payment_required
    from x402.mechanisms.evm.signers import EthAccountSigner
    from x402.mechanisms.evm.exact import register_exact_evm_client
    from eth_account import Account as EthAccount
except ImportError as e:
    raise ImportError(
        "x402 or eth-account not installed. Run: pip install x402 'eth-account[ledger]'"
    ) from e


class SurplusTwitterProvider(XSearchProvider):
    """Calls Twitter API v2 directly via surplusintelligence.ai x402 proxy.

    This is a real Twitter API call — real tweets, real data, no hallucination.
    The x402 protocol handles payment; the SDK manages EIP-3009 signing.

    Unlike SurplusIntelligenceProvider (Grok inference), this provider:
      - Uses HTTP GET (not POST chat/completions)
      - Calls the Twitter v2 proxy endpoint directly
      - Returns actual tweet objects from Twitter's API
      - Costs more per call but is the only option without XAI_API_KEY
    """

    def __init__(
        self,
        private_key: str | None = None,
        timeout: float = 30.0,
        max_payment_usd: float = 0.50,
    ):
        self._timeout = timeout
        self._max_payment_usd = max_payment_usd

        # Load wallet key
        if private_key:
            self._pk = private_key
        elif os.environ.get("ANTSEED_PRIVATE_KEY"):
            self._pk = os.environ["ANTSEED_PRIVATE_KEY"]
        else:
            identity_path = Path.home() / ".antseed" / "identity.key"
            if identity_path.exists():
                self._pk = identity_path.read_text().strip()
            else:
                raise ValueError(
                    "No private key found. Set ANTSEED_PRIVATE_KEY or "
                    "ensure ~/.antseed/identity.key exists."
                )

        account = EthAccount.from_key(self._pk)
        self._address = account.address

        # Build x402 SDK client and register EVM exact scheme
        self._x402 = x402ClientSync()
        signer = EthAccountSigner(account)
        register_exact_evm_client(self._x402, signer)

        TWITTER_SEARCH_PATH = "/tweets/search/recent"

        self._client = httpx.AsyncClient(
            base_url=TWITTER_API_BASE,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
        )

        logger.info(
            f"[SurplusTwitter] Wallet: {self._address[:10]}..., max_payment: ${max_payment_usd}"
        )

    @property
    def name(self) -> str:
        return "surplus_twitter"

    @property
    def model(self) -> str:
        return "twitter_api_v2"

    async def search(
        self,
        handles: list[str],
        from_date: str,
        to_date: str,
    ) -> SearchResult:
        """Call Twitter API v2 search for the given handles.

        Constructs a compound OR query from handles, calls the x402 proxied
        Twitter API, and parses the response.
        """
        if len(handles) > 10:
            raise ValueError(f"Max 10 handles, got {len(handles)}")

        # Build Twitter API v2 search query
        # Note: date filtering via start_time param only — Twitter recent search
        # does NOT support since:/until: operators. Do NOT add them here.
        handle_expressions = [f"from:{h}" for h in handles]
        query = f"({' OR '.join(handle_expressions)})"

        params = {
            "query": query,
            "max_results": max(10, len(handles) * 2),  # Twitter requires 10-100
            "start_time": _to_iso(from_date),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username,name",
        }

        logger.info(f"[SurplusTwitter] Query: {query}")

        resp_data = await self._pay_and_send("/tweets/search/recent", params)
        if resp_data is None:
            return SearchResult(error="[SurplusTwitter] No response from x402 proxy")

        tweets = self._parse_twitter_response(resp_data)
        usage = TokenUsage()  # Twitter API has no token accounting

        logger.info(f"[SurplusTwitter] Got {len(tweets)} tweets for {len(handles)} handles")
        return SearchResult(tweets=tweets, usage=usage)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _pay_and_send(self, path: str, params: dict[str, Any]) -> dict | None:
        """Send a GET request, handling x402 payment if required.

        Returns the parsed JSON response on success, None on failure.
        """
        try:
            resp = await self._client.get(path, params=params)
        except httpx.RequestError as e:
            logger.error(f"[SurplusTwitter] Connection failed: {e}")
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code != 402:
            logger.error(
                f"[SurplusTwitter] Unexpected status {resp.status_code}: {resp.text[:300]}"
            )
            return None

        # Parse 402 and create payment with SDK
        pr_header = resp.headers.get("payment-required") or ""
        if not pr_header:
            logger.error("[SurplusTwitter] 402 but no PAYMENT-REQUIRED header")
            return None

        try:
            pr_raw = json.loads(base64.b64decode(pr_header))
            parsed = parse_payment_required(pr_raw)
        except Exception as e:
            logger.error(f"[SurplusTwitter] Failed to parse payment requirement: {e}")
            return None

        # Check cost ceiling
        amount_micro_usdc = int(parsed.accepts[0].amount)
        amount_usd = amount_micro_usdc / 1_000_000
        if amount_usd > self._max_payment_usd:
            logger.error(
                f"[SurplusTwitter] Cost {amount_usd:.4f} exceeds max {self._max_payment_usd}"
            )
            return None

        # SDK creates correctly-formatted payment payload
        result = self._x402.create_payment_payload(
            payment_required=parsed,
            resource=parsed.resource,
            extensions=parsed.extensions,
        )

        d = result.model_dump() if hasattr(result, "model_dump") else vars(result)
        pay_sig = base64.b64encode(json.dumps(d).encode()).decode()

        try:
            resp2 = await self._client.get(
                path,
                params=params,
                headers={"PAYMENT-SIGNATURE": pay_sig},
            )
        except httpx.RequestError as e:
            logger.error(f"[SurplusTwitter] Paid request failed: {e}")
            return None

        if resp2.status_code != 200:
            logger.error(
                f"[SurplusTwitter] Paid request failed: {resp2.status_code} {resp2.text[:200]}"
            )
            return None

        return resp2.json()

    def _parse_twitter_response(self, data: dict) -> list[dict]:
        """Parse Twitter API v2 response into internal tweet format.

        Twitter API v2 shape:
          {
            "data": [...tweets],
            "includes": {"users": [...]},
            "meta": {"result_count": N}
          }

        Internal format (matches x_search output for downstream compat):
          {
            "id": str,
            "handle": str,
            "text": str,
            "created_at": str,
            "is_retweet": bool,
            "retweeted_handle": None,
            "likes": int,
            "retweets": int,
            "replies": int,
          }
        """
        tweets: list[dict] = []

        # Build author lookup from includes
        users_by_id: dict[str, dict] = {}
        for user in data.get("includes", {}).get("users", []):
            users_by_id[user.get("id", "")] = user

        for tweet in data.get("data", []):
            author_id = tweet.get("author_id", "")
            user = users_by_id.get(author_id, {})
            handle = user.get("username", author_id)

            metrics = tweet.get("public_metrics", {})
            text = tweet.get("text", "")

            # Detect retweets
            is_retweet = text.startswith("RT @")
            retweeted_handle = None
            if is_retweet:
                rt_match = text.split(" ", 2)
                if len(rt_match) >= 3:
                    retweeted_handle = rt_match[1].lstrip("@")

            tweets.append({
                "id": tweet.get("id", ""),
                "handle": handle,
                "text": text,
                "created_at": tweet.get("created_at", ""),
                "is_retweet": is_retweet,
                "retweeted_handle": retweeted_handle,
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
            })

        return tweets