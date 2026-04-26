"""Semantic enricher — LLM-powered semantic categorization for unstructured events.

Handles tweets and event dicts.
Uses keyword fallback when LLM is unavailable.
Caches results per-tweet for 7 days.
"""

import logging
from typing import Optional

from processors.categorizer import CATEGORY_KEYWORDS, SUBCATEGORY_MAP
from processors.llm_client import LLMClient, LLMError
from processors.llm_cache import LLMCache
from config.loader import get_env

logger = logging.getLogger(__name__)

# Category list for the prompt (ordered by severity for LLM reasoning)
CATEGORY_ORDER = [
    "RISK_ALERT",
    "REGULATORY",
    "FINANCIAL",
    "PARTNERSHIP",
    "TECH_EVENT",
    "VISIBILITY",
    "NOISE",
    "NEWS",
]


def _build_prompt(
    text: str,
    chain: str,
    author: str,
    role: str,
    is_retweet: bool,
    original_author: str,
    quoted_text: str,
    thread_context: str = "",
) -> str:
    """Build the deterministic semantic categorization prompt."""

    # Subcategory map snippet for the prompt
    subcat_lines = []
    for cat in CATEGORY_ORDER:
        if cat in SUBCATEGORY_MAP:
            subcats = ", ".join(SUBCATEGORY_MAP[cat].keys())
            subcat_lines.append(f"  - {cat}: {subcats}")

    subcat_block = "\n".join(subcat_lines)

    thread_block = f"\nThread context:\n{thread_context}" if thread_context else ""

    prompt = f"""You are an expert crypto-industry analyst. Given a tweet, classify it into exactly one category and subcategory.

Categories (ordered by priority):
{chr(10).join(f"  - {cat}" for cat in CATEGORY_ORDER)}

Subcategories per category:
{subcat_block}

Rules:
1. Categorize by SEMANTIC CONTENT, not keyword presence.
2. A "wen mainnet" reply to a mainnet announcement is VISIBILITY, not TECH_EVENT.
3. A retweet of official news inherits the original's category.
4. Funding announcements with amounts >= $1M receive FINANCIAL.
5. "Audit complete" without findings → TECH_EVENT. "Audit finding" → RISK_ALERT.
6. Engagement bait, price predictions, memes → NOISE.
7. Only return the specified JSON. No extra text.
8. If chain-agnostic (mentions no specific chain), set primary_mentions to [].

Input:
Chain: {chain}
Author: {author} ({role})
Is retweet: {is_retweet}
Original author: {original_author if original_author else "N/A"}
Quoted text: {quoted_text if quoted_text else "N/A"}
Text: {text}{thread_block}

Output format (STRICT JSON — no markdown fences, no extra text):
{{
  "category": "<CATEGORY>",
  "subcategory": "<subcategory>",
  "confidence": <0.0-1.0>,
  "reasoning": "<1 sentence explaining the classification>",
  "is_noise": <true/false>,
  "primary_mentions": [<list of chain names mentioned, or []>]
}}"""
    return prompt


def _validate_enrichment(result: dict) -> tuple[bool, dict]:
    """Validate LLM enrichment result. Returns (is_valid, sanitized_result)."""
    required = {"category", "subcategory", "confidence", "reasoning", "is_noise"}
    if not required.issubset(result.keys()):
        missing = required - result.keys()
        logger.warning(f"Semantic enrichment missing keys: {missing}")
        return False, {}

    # Validate category exists
    category = result.get("category", "")
    if category not in CATEGORY_ORDER:
        logger.warning(f"LLM returned unknown category: {category}")
        return False, {}

    # Validate subcategory
    subcategory = result.get("subcategory", "")
    valid_subcats = set(SUBCATEGORY_MAP.get(category, {}).keys()) | {"general"}
    if subcategory not in valid_subcats:
        logger.warning(f"LLM returned unknown subcategory '{subcategory}' for {category}")
        # Accept it but log — subcategories can be extended by the LLM

    # Clamp confidence
    try:
        confidence = float(result.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    # Normalize is_noise
    is_noise = bool(result.get("is_noise", False))

    # Normalize primary_mentions
    primary_mentions = result.get("primary_mentions", [])
    if not isinstance(primary_mentions, list):
        primary_mentions = []

    sanitized = {
        "category": category,
        "subcategory": subcategory,
        "confidence": confidence,
        "reasoning": str(result.get("reasoning", "")),
        "is_noise": is_noise,
        "primary_mentions": primary_mentions,
    }
    return True, sanitized


class SemanticEnricher:
    """Enrich raw events (especially tweets) with LLM semantic categorization."""

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        cache: Optional[LLMCache] = None,
        threshold_high: float = 0.75,
        threshold_low: float = 0.50,
    ):
        self.client = client or LLMClient.from_env()
        self.cache = cache or LLMCache()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self._llm_available = True
        self._failures = 0
        self._max_failures_before_disable = 3

    def enrich(self, event: dict) -> dict:
        """Enrich a single event dict.

        If the event source is twitter and text is available, runs LLM enrichment.
        Returns the event with 'semantic' key added (or unmodified on failure).
        """
        source = event.get("source", "") or event.get("source_name", "")
        text = event.get("description", "").strip()

        if not text or "twitter" not in source.lower():
            return event

        chain = event.get("chain", "unknown")
        evidence = event.get("evidence", {}) or {}
        author = evidence.get("author", "")
        role = evidence.get("role", "contributor")
        is_retweet = evidence.get("is_retweet", False)
        original_author = evidence.get("original_author", "")
        quoted_text = evidence.get("quoted_text", "")

        semantic = self._enrich_text(
            text=text,
            chain=chain,
            author=author,
            role=role,
            is_retweet=is_retweet,
            original_author=original_author,
            quoted_text=quoted_text,
        )

        if semantic:
            event = dict(event)  # shallow copy to avoid mutating caller's dict
            event["semantic"] = semantic

        return event

    def enrich_tweets(self, tweets: list[dict]) -> list[dict]:
        """Batch enrichment for scraped tweet dicts (from TwitterCollector).

        Returns list of tweet dicts with 'semantic' key added.
        """
        enriched = []
        for tweet in tweets:
            chain = tweet.get("chain", "unknown")
            text = tweet.get("text", "").strip()
            if not text:
                enriched.append(tweet)
                continue

            semantic = self._enrich_text(
                text=text,
                chain=chain,
                author=tweet.get("account_handle", ""),
                role=tweet.get("account_role", "contributor"),
                is_retweet=tweet.get("is_retweet", False),
                original_author=tweet.get("original_author", ""),
                quoted_text=tweet.get("quoted_text", ""),
                thread_context=tweet.get("thread_text", ""),
            )

            if semantic:
                tweet_copy = dict(tweet)
                tweet_copy["semantic"] = semantic
                enriched.append(tweet_copy)
            else:
                enriched.append(tweet)

        logger.info(f"[semantic] Enriched {sum(1 for t in enriched if 'semantic' in t)}/{len(tweets)} tweets")
        return enriched

    def _enrich_text(
        self,
        text: str,
        chain: str,
        author: str,
        role: str,
        is_retweet: bool,
        original_author: str,
        quoted_text: str,
        thread_context: str = "",
    ) -> Optional[dict]:
        """Core enrichment: check cache, call LLM, validate, store cache."""

        # Health gate: pause LLM calls if too many failures
        if not self._llm_available:
            logger.debug("LLM disabled due to repeated failures — skipping enrichment")
            return None

        # Check cache
        cached = self.cache.get(
            chain=chain,
            text=text,
            author=author,
            is_retweet=is_retweet,
            quoted_text=quoted_text,
        )
        if cached:
            return cached

        # Build and send prompt
        prompt = _build_prompt(
            text=text,
            chain=chain,
            author=author,
            role=role,
            is_retweet=is_retweet,
            original_author=original_author,
            quoted_text=quoted_text,
            thread_context=thread_context,
        )

        try:
            result = self.client.generate_json(prompt)
        except LLMError as e:
            self._failures += 1
            if self._failures >= self._max_failures_before_disable:
                self._llm_available = False
                logger.warning(
                    f"LLM disabled after {self._failures} consecutive failures"
                )
            logger.warning(f"Semantic enrichment LLM call failed: {e}")
            return None

        # Validate and sanitize
        is_valid, semantic = _validate_enrichment(result)
        if not is_valid:
            self._failures += 1
            logger.warning("Semantic enrichment produced invalid result")
            return None

        # Success — reset failure counter
        self._failures = max(0, self._failures - 1)

        # Cache and return
        self.cache.set(
            chain=chain,
            text=text,
            author=author,
            is_retweet=is_retweet,
            quoted_text=quoted_text,
            result=semantic,
        )
        return semantic

    def get_health(self) -> dict:
        """Return health status for observability."""
        return {
            "llm_available": self._llm_available,
            "failures": self._failures,
            "threshold_high": self.threshold_high,
            "threshold_low": self.threshold_low,
            "provider": self.client.provider,
            "model": self.client.model,
        }
