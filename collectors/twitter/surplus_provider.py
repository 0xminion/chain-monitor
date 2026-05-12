"""Surplus Intelligence x402 provider — Grok inference via pay-per-request.

Uses surplusintelligence.ai's x402 marketplace to call Grok models with
x_search tool. Payments are signed with the antseed wallet private key
using the official x402 Python SDK v2.

x402 flow (SDK-managed):
  1. POST without auth → 402 with PAYMENT-REQUIRED
  2. SDK creates payment payload (EIP-3009 exact or Permit2 upto)
  3. Resend with PAYMENT-SIGNATURE header (base64-encoded JSON)
  4. Get OpenAI-compatible response

Two-step x_search pattern:
  Step 1: Grok generates a search query ({"query": "from:handle since:..."})
  Step 2: Caller executes the query and returns results → Grok formats JSON

Requirements:
  - ANTSEED_PRIVATE_KEY env var or identity.key in ~/.antseed/
  - x402>=2.0.0 Python package
  - eth-account (for EthAccountSigner)

Pricing (surplusintelligence.ai, May 2026):
  - grok-4.20-beta: $0.000625/1M prompt, $0.0025/1M completion
  - x402 facilitation fee: ~$0.003/request
  - Total per paid inference call: ~$0.0034
  - 28 calls per full run (14 batches × 2 steps) = ~$0.095 total
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage

logger = logging.getLogger(__name__)

# Token-efficient system prompt — JSON-only extraction
EXTRACTION_SYSTEM_PROMPT = (
    "Extract tweets from search results as a raw JSON array. "
    "Return ONLY the JSON. No markdown, no commentary, no code fences. "
    'Schema: {"id","handle","text","created_at","is_retweet",'
    '"retweeted_handle","likes","retweets","replies"}.'
)

X402_BASE = "https://www.surplusintelligence.ai"
CHAT_PATH = "/x402/api/inference/v1/chat/completions"

# ---------------------------------------------------------------------------
# x402 SDK — imported at __init__ time so absence raises ImportError clearly
# ---------------------------------------------------------------------------
try:
    from x402 import x402ClientSync, parse_payment_required
    from x402.mechanisms.evm.signers import EthAccountSigner
    from x402.mechanisms.evm.exact import register_exact_evm_client
    from eth_account import Account as EthAccount
except ImportError as e:
    raise ImportError(
        "x402 or eth-account not installed. Run: pip install x402 'eth-account[ledger]'"
    ) from e


class SurplusIntelligenceProvider(XSearchProvider):
    """Calls Grok via surplusintelligence.ai x402 marketplace.

    Uses the official x402 SDK v2 to sign payments with the antseed wallet.
    Implements a two-step x_search pattern:
      1. Model generates the search query (no actual search is executed)
      2. Caller provides results → model returns formatted JSON

    This is NOT auto-executing x_search. The caller is responsible for
    actually running the generated queries. See chain-monitor-management skill.
    """

    def __init__(
        self,
        model: str = "grok-4.20-beta",
        private_key: str | None = None,
        timeout: float = 90.0,
        max_payment_usd: float = 0.05,
    ):
        self._model = model
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

        self._client = httpx.AsyncClient(
            base_url=X402_BASE,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
        )

        logger.info(
            f"[SurplusI] Wallet: {self._address[:10]}..., model: {self._model}"
        )

    @property
    def name(self) -> str:
        return "surplus_intelligence"

    @property
    def model(self) -> str:
        return self._model

    async def search(
        self,
        handles: list[str],
        from_date: str,
        to_date: str,
    ) -> SearchResult:
        """Two-step x_search: (1) get query from model, (2) return results.

        Step 1 costs ~$0.0034 and returns a query string.
        Step 2 costs ~$0.0034 and returns formatted tweets.

        Since this provider cannot execute x_search itself, it returns the
        generated query string in the SearchResult.tweets field with a
        special marker. Downstream code should execute the query and call
        search_with_results() to complete the flow.
        """
        if len(handles) > 10:
            raise ValueError(f"Max 10 handles, got {len(handles)}")

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
                            "description": (
                                "X search query, e.g. "
                                "'from:username since:2026-05-11 until:2026-05-12'"
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        }

        user_message = (
            f"Search X for tweets from {', '.join('@' + h for h in handles)} "
            f"between {from_date} and {to_date}. Return ALL matching tweets "
            "as a JSON array."
        )

        # ---- Step 1: get x_search tool call from model ----
        step1_payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "tools": [x_search_tool],
            "tool_choice": {"type": "function", "function": {"name": "x_search"}},
            "temperature": 0.0,
            "stream": False,
        }

        try:
            resp1 = await self._pay_and_send(step1_payload)
        except Exception as e:
            return SearchResult(error=f"[SurplusI Step1] {e}")

        if resp1 is None:
            return SearchResult(error="[SurplusI Step1] No response")

        data1 = resp1
        msg1 = data1.get("choices", [{}])[0].get("message", {})
        tcs1 = msg1.get("tool_calls", [])

        if not tcs1:
            # No tool call requested — model produced text directly
            content = msg1.get("content", "") or ""
            tweets = self._parse_tweets_json(content)
            usage = self._extract_usage(data1)
            return SearchResult(tweets=tweets, usage=usage)

        tc = tcs1[0]
        call_id = tc.get("id", "")
        func = tc.get("function", {})
        if func.get("name") != "x_search":
            return SearchResult(error=f"[SurplusI] Unexpected tool: {func.get('name')}")

        # Extract the generated query string
        try:
            args = json.loads(func.get("arguments", "{}"))
            query = args.get("query", "")
        except json.JSONDecodeError:
            return SearchResult(error="[SurplusI] Failed to parse x_search arguments")

        logger.info(f"[SurplusI] Generated query: {query}")

        # ---- Step 2: return empty results to model to get JSON output ----
        step2_payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
                msg1,  # assistant message with tool_calls
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": "[]",  # no actual search results
                },
            ],
            "tools": [x_search_tool],
            "temperature": 0.0,
            "stream": False,
        }

        try:
            resp2 = await self._pay_and_send(step2_payload)
        except Exception as e:
            return SearchResult(
                error=f"[SurplusI Step2] {e}",
                tweets=[{"_query": query}],  # preserve the query
            )

        if resp2 is None:
            return SearchResult(error="[SurplusI Step2] No response")

        msg2 = resp2.get("choices", [{}])[0].get("message", {})
        content2 = msg2.get("content", "") or ""
        tweets = self._parse_tweets_json(content2)

        # Merge usage from both steps
        usage1 = self._extract_usage(data1)
        usage2 = self._extract_usage(resp2)
        merged_usage = TokenUsage(
            input_tokens=usage1.input_tokens + usage2.input_tokens,
            output_tokens=usage1.output_tokens + usage2.output_tokens,
            cached_tokens=usage1.cached_tokens + usage2.cached_tokens,
        )

        if not tweets:
            # No tweets found — tag with the query so downstream can retry
            tweets = [{"_query": query}]

        return SearchResult(tweets=tweets, usage=merged_usage)

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    async def _pay_and_send(self, payload: dict[str, Any]) -> dict | None:
        """Send a request, handling x402 payment if required.

        Returns the parsed JSON response on success, None on failure.
        """
        try:
            resp = await self._client.post(CHAT_PATH, json=payload)
        except httpx.RequestError as e:
            logger.error(f"[SurplusI] Connection failed: {e}")
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code != 402:
            logger.error(
                f"[SurplusI] Unexpected status {resp.status_code}: {resp.text[:300]}"
            )
            return None

        # Parse 402 and create payment with SDK
        pr_header = resp.headers.get("payment-required") or ""
        if not pr_header:
            logger.error("[SurplusI] 402 but no PAYMENT-REQUIRED header")
            return None

        try:
            pr_raw = json.loads(base64.b64decode(pr_header))
            parsed = parse_payment_required(pr_raw)
        except Exception as e:
            logger.error(f"[SurplusI] Failed to parse payment requirement: {e}")
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
            resp2 = await self._client.post(
                CHAT_PATH,
                json=payload,
                headers={"PAYMENT-SIGNATURE": pay_sig},
            )
        except httpx.RequestError as e:
            logger.error(f"[SurplusI] Paid request failed: {e}")
            return None

        if resp2.status_code != 200:
            logger.error(
                f"[SurplusI] Paid request returned {resp2.status_code}: "
                f"{resp2.text[:300]}"
            )
            return None

        # Log settlement cost
        pr_resp = resp2.headers.get("payment-response") or ""
        if pr_resp:
            try:
                settlement = json.loads(base64.b64decode(pr_resp))
                cost = int(settlement.get("amount", "0")) / 1e6
                logger.info(f"[SurplusI] Settled: ${cost:.6f} USDC")
            except Exception:
                pass

        return resp2.json()

    @staticmethod
    def _extract_usage(data: dict) -> TokenUsage:
        u = data.get("usage", {})
        return TokenUsage(
            input_tokens=u.get("prompt_tokens", 0),
            output_tokens=u.get("completion_tokens", 0),
            cached_tokens=u.get("prompt_tokens_details", {}).get(
                "cached_tokens", 0
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
                cleaned = cleaned[nl + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[-3:].strip()
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            for key in ("tweets", "results", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
        except json.JSONDecodeError:
            pass

        # Find JSON array bounds as last resort
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
