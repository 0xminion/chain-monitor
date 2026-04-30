"""Semantic enricher — agent-native keyword categorization for unstructured events.

v2.0: Fully agent-native. No external LLM calls. Uses deterministic keyword
matching for all categorization. Zero API keys required.

Caches results per-tweet for 7 days.
"""

import logging

from processors.categorizer import CATEGORY_KEYWORDS, SUBCATEGORY_MAP
from processors.llm_cache import LLMCache

logger = logging.getLogger(__name__)


def _keyword_fallback(tweets: list[dict]) -> list[dict]:
    """Apply keyword-based semantic enrichment. Pure Python, no LLM."""
    from processors.categorizer import _detect_subcategory_keyword
    enriched = []
    for t in tweets:
        text = t.get("text", "").lower()
        chain = t.get("chain", "unknown")
        tweet_copy = dict(t)
        category = "NEWS"
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                category = cat
                break
        subcat = _detect_subcategory_keyword(text, category)
        tweet_copy["semantic"] = {
            "category": category,
            "subcategory": subcat,
            "confidence": 0.4,
            "reasoning": "Agent-native keyword categorization",
            "is_noise": category == "NOISE",
            "primary_mentions": [chain] if chain != "unknown" else [],
        }
        enriched.append(tweet_copy)
    return enriched


class SemanticEnricher:
    """Enrich raw events (especially tweets) with keyword-based categorization.

    v2.0: Fully agent-native. All enrichment is done via deterministic keyword
    matching — no LLM calls, no external APIs, no tokens.
    """

    def __init__(
        self,
        client=None,
        cache=None,
        threshold_high: float = 0.75,
        threshold_low: float = 0.50,
    ):
        self.client = None  # disabled — agent native
        self.cache = cache or LLMCache()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self._llm_available = False  # never True
        self._failures = 0
        self._max_failures_before_disable = 3

    def enrich_tweets(self, tweets: list[dict], max_batch_size: int = 15, max_workers: int = 2) -> list[dict]:
        """Batch enrichment for scraped tweet dicts — keyword-only, zero LLM calls."""
        logger.info(f"[semantic] Agent-native keyword enrichment for {len(tweets)} tweets")
        return _keyword_fallback(tweets)

    def enrich(self, event: dict) -> dict:
        """Enrich a single event dict (backward compat)."""
        source = event.get("source", "") or event.get("source_name", "")
        text = event.get("description", "").strip()

        if not text or "twitter" not in source.lower():
            return event

        chain = event.get("chain", "unknown")
        category = "NEWS"
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in text.lower() for kw in kws):
                category = cat
                break

        from processors.categorizer import _detect_subcategory_keyword
        subcat = _detect_subcategory_keyword(text, category)

        event = dict(event)
        event["semantic"] = {
            "category": category,
            "subcategory": subcat,
            "confidence": 0.4,
            "reasoning": "Agent-native keyword categorization",
            "is_noise": category == "NOISE",
            "primary_mentions": [chain] if chain != "unknown" else [],
        }
        return event

    def get_health(self) -> dict:
        """Return health status for observability."""
        return {
            "llm_available": self._llm_available,
            "failures": self._failures,
            "threshold_high": self.threshold_high,
            "threshold_low": self.threshold_low,
            "provider": "agent-native",
            "model": "keyword-only",
        }
