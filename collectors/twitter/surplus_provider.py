"""Surplus Intelligence x402 provider — Grok inference via pay-per-request.

Uses surplusintelligence.ai's x402 marketplace to call Grok models with
x_search tool. Payments are signed with the antseed wallet private key.

x402 flow:
  1. POST without auth → 402 with PAYMENT-REQUIRED
  2. Sign payment (EIP-3009 exact or Permit2 upto)
  3. Resend with PAYMENT-SIGNATURE header
  4. Get OpenAI-compatible response

Requirements:
  - ANTSEED_PRIVATE_KEY env var or identity.key in ~/.antseed/
  - USDC balance on Base (0x215E...E3)

Pricing (surplusintelligence.ai, May 2026):
  - grok-4.20-beta: $0.000625/1M prompt, $0.0025/1M completion
  - x402 facilitation fee: ~$0.003/request
  - Total per call: ~$0.0033
  - 14 batches × $0.0033 = ~$0.046 total
"""

import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from eth_account import Account

from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage

logger = logging.getLogger(__name__)

# Token-efficient system prompt — JSON-only extraction
EXTRACTION_SYSTEM_PROMPT = (
    "Extract tweets from search results as a raw JSON array. "
    "Return ONLY the JSON. No markdown, no commentary, no code fences. "
    'Schema per tweet: {'
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

# EIP-3009 exact scheme typed data (for signing x402 exact payments)
EIP3009_TYPES = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "TransferWithAuthorization": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
        ],
    },
    "domain": {
        "name": "USD Coin",
        "version": "2",
    },
    "primaryType": "TransferWithAuthorization",
}

X402_BASE = "https://www.surplusintelligence.ai"
CHAT_PATH = "/x402/api/inference/v1/chat/completions"


class SurplusIntelligenceProvider(XSearchProvider):
    """Calls Grok via surplusintelligence.ai x402 marketplace.

    Signs payments with antseed wallet. Supports x_search tool forwarding.
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

        self._account = Account.from_key(self._pk)
        self._address = self._account.address

        self._client = httpx.AsyncClient(
            base_url=X402_BASE,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
        )

        logger.info(
            f"[SurplusI] Wallet: {self._address[:10]}..., "
            f"model: {self._model}"
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
        """One X Search call via surplusintelligence x402."""
        if len(handles) > 10:
            raise ValueError(f"Max 10 handles, got {len(handles)}")

        x_search_tool = {
            "type": "function",
            "function": {
                "name": "x_search",
                "description": "Search X/Twitter posts from specific handles",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "allowed_x_handles": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "from_date": {"type": "string"},
                        "to_date": {"type": "string"},
                    },
                    "required": ["allowed_x_handles", "from_date", "to_date"],
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
                        f"Search posts from these X handles within "
                        f"{from_date} to {to_date}: {', '.join(handles)}"
                    ),
                },
            ],
            "tools": [x_search_tool],
            "tool_choice": "auto",
            "temperature": 0.0,
            "stream": False,
        }

        try:
            # Step 1: get x402 challenge
            challenge_resp = await self._client.post(CHAT_PATH, json=payload)
        except httpx.RequestError as e:
            logger.error(f"[SurplusI] Connection failed: {e}")
            return SearchResult(error=f"Connection: {e}")

        if challenge_resp.status_code == 200:
            # No payment needed? Process directly
            data = challenge_resp.json()
            return self._parse_response(data)

        if challenge_resp.status_code != 402:
            logger.error(
                f"[SurplusI] Unexpected status {challenge_resp.status_code}: "
                f"{challenge_resp.text[:300]}"
            )
            return SearchResult(error=f"HTTP {challenge_resp.status_code}")

        # Step 2: parse payment challenge
        payment_req_b64 = (
            challenge_resp.headers.get("payment-required")
            or challenge_resp.headers.get("x-payment-required", "")
        )
        if not payment_req_b64:
            logger.error("[SurplusI] No PAYMENT-REQUIRED header")
            return SearchResult(error="Missing PAYMENT-REQUIRED header")

        try:
            payment_req = json.loads(base64.b64decode(payment_req_b64))
        except Exception as e:
            logger.error(f"[SurplusI] Failed to decode payment challenge: {e}")
            return SearchResult(error=f"Payment decode: {e}")

        accepts = payment_req.get("accepts", [])

        # Prefer upto (Permit2), fallback to exact (EIP-3009)
        upto = next((a for a in accepts if a.get("scheme") == "upto"), None)
        selected = upto or accepts[0] if accepts else None
        if not selected:
            return SearchResult(error="No payment scheme available")

        # Step 3: sign payment
        try:
            if selected.get("scheme") == "upto":
                payment_sig = self._sign_upto(selected)
            else:
                payment_sig = self._sign_exact(selected)
        except Exception as e:
            logger.error(f"[SurplusI] Payment signing failed: {e}")
            return SearchResult(error=f"Signing: {e}")

        # Step 4: retry with payment
        try:
            paid_resp = await self._client.post(
                CHAT_PATH,
                json=payload,
                headers={"PAYMENT-SIGNATURE": payment_sig},
            )
        except httpx.RequestError as e:
            logger.error(f"[SurplusI] Paid request failed: {e}")
            return SearchResult(error=f"Paid request: {e}")

        if paid_resp.status_code != 200:
            logger.error(
                f"[SurplusI] Paid request returned {paid_resp.status_code}: "
                f"{paid_resp.text[:300]}"
            )
            return SearchResult(error=f"Paid HTTP {paid_resp.status_code}")

        payment_resp_header = paid_resp.headers.get(
            "payment-response", ""
        )
        if payment_resp_header:
            try:
                settlement = json.loads(base64.b64decode(payment_resp_header))
                cost = int(settlement.get("amount", "0")) / 1_000_000
                logger.info(f"[SurplusI] Settled: ${cost:.6f} USDC")
            except Exception:
                pass

        return self._parse_response(paid_resp.json())

    def _sign_exact(self, requirement: dict) -> str:
        """Sign an EIP-3009 exact authorization for x402 v2."""
        amount = int(requirement.get("amount", "0"))
        asset = requirement.get("asset", "")
        pay_to = requirement.get("payTo", "")

        extra = requirement.get("extra", {})
        version = extra.get("version", "2")
        chain_id_str = requirement.get("network", "eip155:8453")
        chain_id = int(chain_id_str.split(":")[-1])

        import time
        now = int(time.time())
        nonce_raw = f"{self._address}:{now}:{amount}"
        nonce = "0x" + __import__("hashlib").sha256(nonce_raw.encode()).hexdigest()

        domain = {
            "name": "USD Coin",
            "version": version,
            "chainId": chain_id,
            "verifyingContract": asset,
        }
        message = {
            "from": self._address,
            "to": pay_to,
            "value": amount,
            "validAfter": 0,
            "validBefore": now + 3600,
            "nonce": nonce,
        }
        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        }
        full = {
            "types": types,
            "domain": domain,
            "primaryType": "TransferWithAuthorization",
            "message": message,
        }

        signed = Account.sign_typed_data(self._pk, full_message=full)
        sig_hex = "0x" + signed.signature.hex()

        # x402 v2 expects amounts as strings
        payload = {
            "scheme": "exact",
            "network": chain_id_str,
            "asset": asset,
            "amount": str(amount),
            "payTo": pay_to,
            "signature": sig_hex,
            "from": self._address,
            "nonce": nonce,
            "validAfter": "0",
            "validBefore": str(now + 3600),
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def _sign_upto(self, requirement: dict) -> str:
        """Sign a Permit2 upto authorization (Permit2 batch + transferFrom)."""
        # For upto, we sign the same EIP-3009 structure but mark it as upto scheme.
        # Permit2 proxy handles actual settlement.
        signed = self._sign_exact(requirement)
        payload = json.loads(base64.b64decode(signed))
        payload["scheme"] = "upto"
        return base64.b64encode(json.dumps(payload).encode()).decode()

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    def _parse_response(self, data: dict) -> SearchResult:
        usage_raw = data.get("usage", {})
        choices = data.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        tweets = self._parse_tweets_json(content)

        # Check for tool_calls in response
        if not tweets and choices:
            tool_calls = choices[0].get("message", {}).get("tool_calls", [])
            for tc in tool_calls:
                func = tc.get("function", {})
                if func.get("name") == "x_search":
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                        results = args.get("results", [])
                        if isinstance(results, list):
                            tweets = results
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
            for key in ("tweets", "results", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
        except json.JSONDecodeError:
            pass

        # Find JSON array bounds as fallback
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
