"""Unit tests for LLM cache and deterministic semantic enricher.

No real LLM calls. All enrichment is keyword-based deterministic.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from processors.llm_cache import LLMCache, _cache_path, _is_expired, _make_key
from processors.semantic_enricher import (
    SemanticEnricher,
    _validate_enrichment,
    _keyword_enrich_tweets,
    _is_twitter_noise,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Override cache dir to a temp path."""
    with patch("processors.llm_cache.CACHE_DIR", tmp_path):
        yield tmp_path


# ──────────────────────────────────────────────────────────────
# LLMCache tests
# ──────────────────────────────────────────────────────────────

class TestLLMCache:
    def test_get_miss(self, temp_cache_dir):
        cache = LLMCache()
        assert cache.get("ethereum", "test tweet", "user", False, "") is None

    def test_set_and_get(self, temp_cache_dir):
        cache = LLMCache()
        result = {
            "category": "TECH_EVENT",
            "subcategory": "upgrade",
            "confidence": 0.95,
            "reasoning": "Mainnet upgrade",
            "is_noise": False,
        }
        cache.set("ethereum", "test tweet", "user", False, "", result)

        cached = cache.get("ethereum", "test tweet", "user", False, "")
        assert cached is not None
        assert cached["category"] == "TECH_EVENT"
        assert cached["confidence"] == 0.95

    def test_cache_identity_by_all_fields(self, temp_cache_dir):
        cache = LLMCache()
        cache.set("eth", "text", "user", False, "", {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.5, "reasoning": "x", "is_noise": False})
        # Same text but different author → miss
        assert cache.get("eth", "text", "other", False, "") is None
        # Same text but retweet → miss
        assert cache.get("eth", "text", "user", True, "") is None

    def test_cache_expiration(self, temp_cache_dir, monkeypatch):
        cache = LLMCache(ttl_hours=0)  # Zero TTL = immediate expiration
        cache.set("eth", "text", "user", False, "", {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.5, "reasoning": "x", "is_noise": False})
        assert cache.get("eth", "text", "user", False, "") is None

    def test_cache_missing_required_keys(self, temp_cache_dir):
        cache = LLMCache()
        # Missing subcategory
        cache.set("eth", "text", "user", False, "", {"category": "TECH_EVENT", "confidence": 0.5, "reasoning": "x", "is_noise": False})
        assert cache.get("eth", "text", "user", False, "") is None

    def test_clear_expired(self, temp_cache_dir):
        cache = LLMCache(ttl_hours=0)
        cache.set("eth", "text", "user", False, "", {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.5, "reasoning": "x", "is_noise": False})
        removed = cache.clear_expired()
        assert removed == 1
        assert cache.get_stats()["total_entries"] == 0

    def test_stats(self, temp_cache_dir):
        cache = LLMCache()
        stats = cache.get_stats()
        assert "total_entries" in stats
        assert "ttl_hours" in stats


# ──────────────────────────────────────────────────────────────
# SemanticEnricher tests (deterministic, no LLM)
# ──────────────────────────────────────────────────────────────

class TestValidateEnrichment:
    def test_valid(self):
        result = {
            "category": "TECH_EVENT",
            "subcategory": "upgrade",
            "confidence": 0.95,
            "reasoning": "reason",
            "is_noise": False,
        }
        valid, sanitized = _validate_enrichment(result)
        assert valid is True
        assert sanitized["category"] == "TECH_EVENT"
        assert sanitized["confidence"] == 0.95
        assert sanitized["is_noise"] is False

    def test_invalid_category(self):
        result = {
            "category": "INVALID",
            "subcategory": "upgrade",
            "confidence": 0.95,
            "reasoning": "reason",
            "is_noise": False,
        }
        valid, _ = _validate_enrichment(result)
        assert valid is False

    def test_clamped_confidence(self):
        result = {
            "category": "NEWS",
            "subcategory": "general",
            "confidence": 1.5,
            "reasoning": "reason",
            "is_noise": False,
        }
        valid, sanitized = _validate_enrichment(result)
        assert valid is True
        assert sanitized["confidence"] == 1.0

    def test_missing_keys(self):
        result = {"category": "NEWS", "confidence": 0.5}
        valid, _ = _validate_enrichment(result)
        assert valid is False


class TestKeywordEnrichTweets:
    def test_hack_tweet(self):
        tweets = [{"text": "Bridge hack drained $15M from protocol", "chain": "ethereum"}]
        enriched = _keyword_enrich_tweets(tweets)
        assert enriched[0]["semantic"]["category"] == "RISK_ALERT"
        assert "hack" in enriched[0]["semantic"]["subcategory"]

    def test_partnership_tweet(self):
        tweets = [{"text": "Thrilled to announce our partnership with Polygon for L2 scaling deployment", "chain": "base"}]
        enriched = _keyword_enrich_tweets(tweets)
        assert enriched[0]["semantic"]["category"] == "PARTNERSHIP"

    def test_noise_tweet(self):
        tweets = [{"text": "gm everyone! wagmi 🚀", "chain": "solana"}]
        enriched = _keyword_enrich_tweets(tweets)
        assert enriched[0]["semantic"]["category"] == "NOISE"
        assert enriched[0]["semantic"]["is_noise"] is True

    def test_tech_event_tweet(self):
        tweets = [{"text": "Mainnet upgrade goes live tomorrow with EIP-4844", "chain": "ethereum"}]
        enriched = _keyword_enrich_tweets(tweets)
        assert enriched[0]["semantic"]["category"] == "TECH_EVENT"


class TestSemanticEnricherUnit:
    """SemanticEnricher tests — deterministic, no LLM."""

    @pytest.fixture
    def enricher(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        return SemanticEnricher(cache=mock_cache)

    def test_enrich_non_twitter_event(self, enricher):
        event = {"source": "rss", "description": "hello world"}
        result = enricher.enrich(event)
        assert "semantic" not in result

    def test_enrich_twitter_with_keyword_result(self, enricher):
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "Mainnet Dencun upgrade is going live tomorrow!",
            "evidence": {"author": "ethereum", "role": "official", "is_retweet": False},
        }
        result = enricher.enrich(event)
        assert "semantic" in result
        assert result["semantic"]["category"] == "TECH_EVENT"
        enricher.cache.set.assert_called_once()

    def test_enrich_cache_hit(self, enricher):
        cached = {
            "category": "VISIBILITY",
            "subcategory": "ama",
            "confidence": 0.80,
            "reasoning": "AMA",
            "is_noise": False,
        }
        enricher.cache.get.return_value = cached
        event = {
            "source": "twitter",
            "chain": "solana",
            "description": "AMA tomorrow",
            "evidence": {"author": "solana"},
        }
        result = enricher.enrich(event)
        assert result["semantic"] == cached
        enricher.cache.set.assert_not_called()

    def test_enrich_tweets_batch(self, enricher):
        tweets = [
            {"chain": "eth", "text": "upgrade live", "account_handle": "eth"},
            {"chain": "sol", "text": "partnership announced", "account_handle": "sol"},
        ]
        enriched = enricher.enrich_tweets(tweets)
        assert len(enriched) == 2
        assert "semantic" in enriched[0]
        assert "semantic" in enriched[1]
        assert enricher.cache.set.call_count == 2

    def test_health(self, enricher):
        h = enricher.get_health()
        assert h["llm_available"] is False
        assert h["failures"] == 0
        assert h["provider"] == "deterministic"
