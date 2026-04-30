"""Unit tests for LLM client and cache, and semantic enricher.

These tests mock the Ollama HTTP endpoint to avoid real LLM calls.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from processors.llm_client import LLMClient, LLMError, LLMResponseError, LLMTimeoutError
from processors.llm_cache import LLMCache, _cache_path, _is_expired, _make_key
from processors.semantic_enricher import SemanticEnricher, _validate_enrichment


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """Return a mocked requests session."""
    with patch("processors.llm_client.requests.Session") as mock_cls:
        yield mock_cls


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Override cache dir to a temp path."""
    with patch("processors.llm_cache.CACHE_DIR", tmp_path):
        yield tmp_path


# ──────────────────────────────────────────────────────────────────────────
# LLMClient tests
# ──────────────────────────────────────────────────────────────────────────

class TestLLMClientInit:
    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_MODEL", "minimax-m2.7:cloud")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gemma4:31b-cloud")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.1")
        monkeypatch.setenv("LLM_TIMEOUT", "60")

        client = LLMClient.from_env()
        assert client.provider == "ollama"
        assert client.model == "minimax-m2.7:cloud"
        assert client.fallback_model == "gemma4:31b-cloud"
        assert client.temperature == 0.1
        assert client.timeout == 60.0

    def test_explicit_params_override_env(self):
        client = LLMClient(
            provider="custom",
            model="custom-model",
            fallback_model="custom-fallback",
            temperature=0.5,
            timeout=10,
        )
        assert client.provider == "custom"
        assert client.model == "custom-model"
        assert client.timeout == 10.0


class TestLLMClientGenerate:
    def test_ollama_success(self, mock_session):
        mock_post = MagicMock()
        mock_post.return_value.json.return_value = {"response": " pong "}
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.status_code = 200
        mock_session.return_value.post = mock_post

        client = LLMClient(
            provider="ollama",
            model="minimax-m2.7:cloud",
            max_retries=0,
        )
        response = client.generate("Say pong")
        assert response == "pong"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "minimax-m2.7:cloud"
        assert call_args[1]["json"]["prompt"] == "Say pong"
        assert call_args[1]["json"]["options"]["temperature"] == 0.1

    def test_ollama_empty_response(self, mock_session):
        mock_post = MagicMock()
        mock_post.return_value.json.return_value = {"response": "   "}
        mock_post.return_value.raise_for_status = MagicMock()
        mock_session.return_value.post = mock_post

        client = LLMClient(provider="ollama", model="test", fallback_model="test", max_retries=0)
        with pytest.raises(LLMError, match="empty"):
            client.generate("test")

    def test_ollama_timeout(self, mock_session):
        import requests

        mock_post = MagicMock()
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        mock_session.return_value.post = mock_post

        client = LLMClient(provider="ollama", model="test", fallback_model="test", timeout=1, max_retries=0)
        with pytest.raises(LLMError):
            client.generate("test")

    def test_ollama_connection_error_falls_back(self, mock_session):
        import requests

        mock_post = MagicMock()
        # First call fails with ConnectionError, second succeeds
        def side_effect(*args, **kwargs):
            model = kwargs.get("json", {}).get("model", "")
            if model == "primary":
                raise requests.exceptions.ConnectionError("refused")
            resp = MagicMock()
            resp.json.return_value = {"response": "fallback-ok"}
            resp.raise_for_status = MagicMock()
            return resp

        mock_post.side_effect = side_effect
        mock_session.return_value.post = mock_post

        client = LLMClient(
            provider="ollama",
            model="primary",
            fallback_model="fallback-model",
            max_retries=0,
        )
        response = client.generate("test")
        assert "fallback-ok" in response
        assert mock_post.call_count == 2

    def test_generate_json(self, mock_session):
        result = {"category": "TECH_EVENT", "confidence": 0.95}
        mock_post = MagicMock()
        mock_post.return_value.json.return_value = {"response": json.dumps(result)}
        mock_post.return_value.raise_for_status = MagicMock()
        mock_session.return_value.post = mock_post

        client = LLMClient(provider="ollama", model="test", max_retries=0)
        assert client.generate_json("test") == result

    def test_generate_json_wrapped_in_fences(self, mock_session):
        result = {"category": "TECH_EVENT"}
        mock_post = MagicMock()
        raw = "```json\n" + json.dumps(result) + "\n```"
        mock_post.return_value.json.return_value = {"response": raw}
        mock_post.return_value.raise_for_status = MagicMock()
        mock_session.return_value.post = mock_post

        client = LLMClient(provider="ollama", model="test", max_retries=0)
        assert client.generate_json("test") == result

    def test_generate_json_invalid_json(self, mock_session):
        mock_post = MagicMock()
        mock_post.return_value.json.return_value = {"response": "not-json"}
        mock_post.return_value.raise_for_status = MagicMock()
        mock_session.return_value.post = mock_post

        client = LLMClient(provider="ollama", model="test", max_retries=0)
        with pytest.raises(LLMResponseError, match="JSON"):
            client.generate_json("test")


# ──────────────────────────────────────────────────────────────────────────
# LLMCache tests
# ──────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────
# SemanticEnricher tests
# ──────────────────────────────────────────────────────────────────────────

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


class TestSemanticEnricherUnit:
    """SemanticEnricher tests with mocked LLMClient."""

    @pytest.fixture
    def enricher(self):
        mock_client = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        enricher = SemanticEnricher(client=mock_client, cache=mock_cache)
        return enricher

    def test_enrich_non_twitter_event(self, enricher):
        # Does not enrich non-Twitter events
        event = {"source": "rss", "description": "hello world"}
        result = enricher.enrich(event)
        assert "semantic" not in result
        enricher.client.generate_json.assert_not_called()

    def test_enrich_twitter_with_llm_result(self, enricher):
        enricher.client.generate_json.return_value = {
            "category": "TECH_EVENT",
            "subcategory": "upgrade",
            "confidence": 0.90,
            "reasoning": "Mainnet upgrade",
            "is_noise": False,
            "primary_mentions": ["ethereum"],
        }
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "Mainnet upgrade live tomorrow",
            "evidence": {
                "author": "ethereum",
                "role": "official",
                "is_retweet": False,
            },
        }
        result = enricher.enrich(event)
        assert "semantic" in result
        assert result["semantic"]["category"] == "TECH_EVENT"
        assert result["semantic"]["confidence"] == 0.90
        enricher.client.generate_json.assert_called_once()
        enricher.cache.set.assert_called_once()

    def test_enrich_llm_failure_falls_back(self, enricher):
        from processors.llm_client import LLMError
        enricher.client.generate_json.side_effect = LLMError("LLM down")
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "test",
            "evidence": {"author": "user"},
        }
        result = enricher.enrich(event)
        assert "semantic" not in result
        # Failure tracking
        assert enricher._failures == 1

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
        enricher.client.generate_json.assert_not_called()

    def test_enrich_tweets_batch(self, enricher):
        # Batch enrichment returns a LIST of results, one per tweet
        enricher.client.generate_json.return_value = [
            {
                "category": "TECH_EVENT",
                "subcategory": "upgrade",
                "confidence": 0.80,
                "reasoning": "test",
                "is_noise": False,
            },
            {
                "category": "PARTNERSHIP",
                "subcategory": "integration",
                "confidence": 0.75,
                "reasoning": "test",
                "is_noise": False,
            },
        ]
        tweets = [
            {"chain": "eth", "text": "upgrade live", "account_handle": "eth"},
            {"chain": "sol", "text": "partnership", "account_handle": "sol"},
        ]
        enriched = enricher.enrich_tweets(tweets)
        assert len(enriched) == 2
        assert "semantic" in enriched[0]
        assert enricher.cache.set.call_count == 2

    def test_enrich_llm_disabled_after_max_failures(self, enricher):
        from processors.llm_client import LLMError
        enricher.client.generate_json.side_effect = LLMError("LLM down")
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "test",
            "evidence": {"author": "user"},
        }
        # Exhaust failures to disable
        for _ in range(3):
            enricher.enrich(event)
        assert enricher._llm_available is False
        # Further calls should skip
        enricher.client.reset_mock()
        enricher.enrich(event)
        enricher.client.generate_json.assert_not_called()

    def test_health(self, enricher):
        # Set provider attribute on the mock to a real string
        enricher.client.provider = "ollama"
        h = enricher.get_health()
        assert h["llm_available"] is True
        assert h["failures"] == 0
        assert h["provider"] == "ollama"


@pytest.mark.skipif(
    os.environ.get("CHAIN_MONITOR_ENABLE_LLM_TESTS") != "1",
    reason="LLM integration tests disabled (set CHAIN_MONITOR_ENABLE_LLM_TESTS=1)",
)
class TestSemanticEnricherWithRealIntegration:
    """These tests use real Ollama and are conditionally skipped.

    Set CHAIN_MONITOR_ENABLE_LLM_TESTS=1 to run them.
    """

    def test_real_llm_call(self):
        """End-to-end enrichment with real Ollama."""
        from processors.llm_client import LLMClient
        from processors.llm_cache import LLMCache

        client = LLMClient(model="minimax-m2.7:cloud", timeout=15)
        cache = LLMCache()
        enricher = SemanticEnricher(client=client, cache=cache)
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "Mainnet Dencun upgrade is going live tomorrow!",
            "evidence": {"author": "ethereum", "role": "official", "is_retweet": False},
        }
        result = enricher.enrich(event)
        assert "semantic" in result
        assert result["semantic"]["category"] == "TECH_EVENT"
        assert result["semantic"]["confidence"] >= 0.5
