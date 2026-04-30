"""Semantic enricher — deterministic keyword-based categorization for tweets.

No LLM calls. Uses the same keyword dictionaries as EventCategorizer.
Caches results per-tweet for 7 days.
"""

import logging
from typing import Optional

from processors.categorizer import (
    CATEGORY_KEYWORDS,
    SUBCATEGORY_MAP,
    TWITTER_NOISE_PHRASES,
    TWITTER_HIGH_VALUE_INDICATORS,
    _detect_subcategory_keyword,
)
from processors.llm_cache import LLMCache

logger = logging.getLogger(__name__)


def _keyword_enrich_tweets(tweets: list[dict]) -> list[dict]:
    """Apply deterministic keyword-based semantic enrichment to tweets."""
    enriched = []
    for t in tweets:
        text = t.get("text", "").lower()
        chain = t.get("chain", "unknown")
        tweet_copy = dict(t)

        # 1. Check noise first
        is_noise, noise_reason = _is_twitter_noise(text)
        if is_noise:
            tweet_copy["semantic"] = {
                "category": "NOISE",
                "subcategory": noise_reason,
                "confidence": 0.7,
                "reasoning": f"Noise filter: {noise_reason}",
                "is_noise": True,
                "primary_mentions": [chain] if chain != "unknown" else [],
            }
            enriched.append(tweet_copy)
            continue

        # 2. Keyword-based category detection
        category = "NEWS"
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                category = cat
                break

        # 3. Subcategory detection
        subcat = _detect_subcategory_keyword(text, category)

        tweet_copy["semantic"] = {
            "category": category,
            "subcategory": subcat,
            "confidence": 0.6,
            "reasoning": f"Keyword match: {category}/{subcat}",
            "is_noise": False,
            "primary_mentions": [chain] if chain != "unknown" else [],
        }
        enriched.append(tweet_copy)
    return enriched


def _is_twitter_noise(text: str) -> tuple[bool, str]:
    """Check if a tweet is low-value noise. Returns (is_noise, reason)."""
    t = text.lower()

    for phrase in TWITTER_NOISE_PHRASES:
        if phrase in t:
            return True, f"noise_phrase:{phrase.strip()}"

    if len(t) < 30 and ("🚀" in t or "🔥" in t or "💰" in t):
        return True, "short_emoji_bait"

    if len(t) < 60:
        has_indicator = any(hv in t for hv in TWITTER_HIGH_VALUE_INDICATORS)
        if not has_indicator:
            return True, "short_no_substance"

    return False, ""


def _validate_enrichment(result: dict) -> tuple[bool, dict]:
    """Validate enrichment result. Returns (is_valid, sanitized_result)."""
    required = {"category", "subcategory", "confidence", "reasoning", "is_noise"}
    if not required.issubset(result.keys()):
        missing = required - result.keys()
        logger.warning(f"Semantic enrichment missing keys: {missing}")
        return False, {}

    category = result.get("category", "")
    valid_categories = set(CATEGORY_KEYWORDS.keys()) | {"NEWS", "NOISE", "PRICE_NOISE"}
    if category not in valid_categories:
        logger.warning(f"Unknown category: {category}")
        return False, {}

    try:
        confidence = float(result.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    is_noise = bool(result.get("is_noise", False))
    primary_mentions = result.get("primary_mentions", [])
    if not isinstance(primary_mentions, list):
        primary_mentions = []

    sanitized = {
        "category": category,
        "subcategory": result.get("subcategory", "general"),
        "confidence": confidence,
        "reasoning": str(result.get("reasoning", "")),
        "is_noise": is_noise,
        "primary_mentions": primary_mentions,
    }
    return True, sanitized


class SemanticEnricher:
    """Deterministic semantic categorization for tweets. No LLM calls."""

    def __init__(self, cache: Optional[LLMCache] = None):
        self.cache = cache or LLMCache()

    def enrich_tweets(self, tweets: list[dict]) -> list[dict]:
        """Batch enrichment for scraped tweet dicts — deterministic keyword-based."""
        enriched = []
        for t in tweets:
            text = t.get("text", "").strip()
            author = t.get("account_handle", "")
            is_retweet = t.get("is_retweet", False)
            quoted_text = t.get("quoted_text", "")
            chain = t.get("chain", "unknown")

            cached = self.cache.get(
                chain=chain, text=text, author=author,
                is_retweet=is_retweet, quoted_text=quoted_text,
            )
            if cached:
                t_copy = dict(t)
                t_copy["semantic"] = cached
                enriched.append(t_copy)
                continue

            # Deterministic keyword enrichment
            result = _keyword_enrich_tweets([t])[0]
            sem = result.get("semantic")
            if sem:
                is_valid, sanitized = _validate_enrichment(sem)
                if is_valid:
                    t_copy = dict(t)
                    t_copy["semantic"] = sanitized
                    self.cache.set(
                        chain=chain, text=text, author=author,
                        is_retweet=is_retweet, quoted_text=quoted_text,
                        result=sanitized,
                    )
                    enriched.append(t_copy)
                    continue

            enriched.append(dict(t))

        enriched_count = sum(1 for t in enriched if "semantic" in t)
        logger.info(f"[semantic] Enriched {enriched_count}/{len(tweets)} tweets (deterministic)")
        return enriched

    def enrich(self, event: dict) -> dict:
        """Enrich a single event dict (backward compat for pipeline events)."""
        source = event.get("source", "") or event.get("source_name", "")
        text = event.get("description", "").strip()

        if not text or "twitter" not in source.lower():
            return event

        chain = event.get("chain", "unknown")
        evidence = event.get("evidence", {}) or {}
        author = evidence.get("author", "")
        is_retweet = evidence.get("is_retweet", False)
        quoted_text = evidence.get("quoted_text", "")

        cached = self.cache.get(
            chain=chain, text=text, author=author,
            is_retweet=is_retweet, quoted_text=quoted_text,
        )
        if cached:
            event = dict(event)
            event["semantic"] = cached
            return event

        # Deterministic keyword enrichment
        result = _keyword_enrich_tweets([{"text": text, "chain": chain}])[0]
        sem = result.get("semantic")
        if sem:
            is_valid, sanitized = _validate_enrichment(sem)
            if is_valid:
                event = dict(event)
                event["semantic"] = sanitized
                self.cache.set(
                    chain=chain, text=text, author=author,
                    is_retweet=is_retweet, quoted_text=quoted_text,
                    result=sanitized,
                )

        return event

    def get_health(self) -> dict:
        """Return health status for observability."""
        return {
            "llm_available": False,
            "failures": 0,
            "provider": "deterministic",
            "model": "keyword-only",
        }
