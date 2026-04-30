"""Unit tests for LLM client and cache, and semantic enricher.

v2.0: Semantic enricher is agent-native — all enrichment uses keyword matching.
No LLM calls required for pipeline operation.
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
from processors.semantic_enricher import SemanticEnricher


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
# LLMClient tests (module still available for optional external integration)
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
        assert cache.get("eth", "text", "other", False, "") is None
        assert cache.get("eth", "text", "user", True, "") is None

    def test_cache_expiration(self, temp_cache_dir, monkeypatch):
        cache = LLMCache(ttl_hours=0)
        cache.set("eth", "text", "user", False, "", {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.5, "reasoning": "x", "is_noise": False})
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
# SemanticEnricher tests — agent-native keyword enrichment
# ──────────────────────────────────────────────────────────────────────────

class TestSemanticEnricherAgentNative:
    """SemanticEnricher tests for agent-native keyword enrichment."""

    @pytest.fixture
    def enricher(self):
        return SemanticEnricher()

    def test_enrich_non_twitter_event(self, enricher):
        event = {"source": "rss", "description": "hello world"}
        result = enricher.enrich(event)
        assert result == event  # unchanged for non-Twitter

    def test_enrich_twitter_keyword_match(self, enricher):
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
        assert result["semantic"]["subcategory"] == "upgrade"
        assert result["semantic"]["is_noise"] is False

    def test_enrich_twitter_hack_keyword(self, enricher):
        event = {
            "source": "twitter",
            "chain": "solana",
            "description": "Protocol hack drained $5M",
        }
        result = enricher.enrich(event)
        assert "semantic" in result
        assert result["semantic"]["category"] == "RISK_ALERT"
        assert result["semantic"]["subcategory"] == "hack"

    def test_enrich_tweets_batch_keyword_only(self, enricher):
        tweets = [
            {"chain": "eth", "text": "upgrade live", "account_handle": "eth"},
            {"chain": "sol", "text": "partnership announced", "account_handle": "sol"},
        ]
        enriched = enricher.enrich_tweets(tweets)
        assert len(enriched) == 2
        assert "semantic" in enriched[0]
        assert enriched[0]["semantic"]["category"] == "TECH_EVENT"
        assert enriched[1]["semantic"]["category"] == "PARTNERSHIP"

    def test_health_agent_native(self, enricher):
        h = enricher.get_health()
        assert h["llm_available"] is False
        assert h["provider"] == "agent-native"
        assert h["model"] == "keyword-only"
        assert h["failures"] == 0
