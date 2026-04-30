"""Tests for agent-native SemanticEnricher.

No LLM calls. No keyword matching. The agent provides all enrichment reasoning.
These tests verify task preparation, result application, and checkpoint mechanics.
"""

import json
import pytest
from pathlib import Path

from processors.semantic_enricher import SemanticEnricher


@pytest.fixture
def enricher():
    return SemanticEnricher()


@pytest.fixture
def sample_tweets():
    return [
        {
            "chain": "ethereum",
            "text": "Mainnet upgrade goes live tomorrow",
            "account_handle": "@ethereum",
            "account_role": "official",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 1200,
            "retweets": 450,
            "url": "https://x.com/ethereum/status/123",
        },
        {
            "chain": "solana",
            "text": "gm frens, wen lambo? 🚀🚀🚀",
            "account_handle": "@solana_memes",
            "account_role": "contributor",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 12,
            "retweets": 3,
            "url": "https://x.com/solana_memes/status/456",
        },
    ]


class TestAgentTaskPreparation:
    """Test that prepare_agent_task creates valid checkpoint files for tweets."""

    def test_task_file_created(self, enricher, sample_tweets, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = enricher.prepare_agent_task(sample_tweets)
        assert path.exists()
        assert path.suffix == ".json"
        assert "semantic_enrich_task_" in path.name

    def test_task_contains_tweets(self, enricher, sample_tweets, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = enricher.prepare_agent_task(sample_tweets)
        data = json.loads(path.read_text())
        assert data["task_type"] == "semantic_enrich"
        assert len(data["tweets"]) == 2
        assert data["tweets"][0]["id"] == 0
        assert data["tweets"][0]["chain"] == "ethereum"
        assert data["tweets"][0]["author"] == "@ethereum"
        assert data["tweets"][0]["likes"] == 1200

    def test_task_contains_instructions(self, enricher, sample_tweets, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = enricher.prepare_agent_task(sample_tweets)
        data = json.loads(path.read_text())
        assert "instructions" in data
        assert "RISK_ALERT" in data["instructions"]
        assert "output_format" in data


class TestApplyEnrichment:
    """Test that apply_enrichment correctly merges agent results into tweets."""

    def test_apply_single_enrichment(self, enricher, sample_tweets):
        agent_results = [
            {"id": 0, "category": "TECH_EVENT", "subcategory": "upgrade", "reasoning": "Mainnet upgrade", "is_noise": False, "primary_mentions": ["ethereum"]},
        ]
        enriched = enricher.apply_enrichment(sample_tweets[:1], agent_results)
        assert enriched[0]["semantic"]["category"] == "TECH_EVENT"
        assert enriched[0]["semantic"]["subcategory"] == "upgrade"
        assert enriched[0]["semantic"]["confidence"] == 0.85

    def test_apply_noise_enrichment(self, enricher, sample_tweets):
        agent_results = [
            {"id": 1, "category": "NOISE", "subcategory": "general", "reasoning": "Engagement bait", "is_noise": True, "primary_mentions": []},
        ]
        enriched = enricher.apply_enrichment(sample_tweets, agent_results)
        assert enriched[1]["semantic"]["category"] == "NOISE"
        assert enriched[1]["semantic"]["is_noise"] is True

    def test_missing_result_defaults(self, enricher, sample_tweets):
        agent_results = [
            {"id": 0, "category": "TECH_EVENT", "subcategory": "upgrade", "reasoning": "Upgrade", "is_noise": False, "primary_mentions": []},
            # Missing id 1
        ]
        enriched = enricher.apply_enrichment(sample_tweets, agent_results)
        assert enriched[0]["semantic"]["category"] == "TECH_EVENT"
        assert enriched[1]["semantic"]["category"] == "NEWS"
        assert enriched[1]["semantic"]["confidence"] == 0.0


class TestTryLoadResults:
    """Test loading agent enrichment output from disk."""

    def test_load_existing_output(self, enricher, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_OUTPUT_DIR", tmp_path / "agent_output")

        output_dir = tmp_path / "agent_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "semantic_enrich_output_20260430_120000.json"
        output_path.write_text(json.dumps({
            "task_type": "semantic_enrich",
            "task_id": "20260430_120000",
            "results": [
                {"id": 0, "category": "FINANCIAL", "subcategory": "funding_round", "reasoning": "$50M raised", "is_noise": False, "primary_mentions": []},
            ],
        }))

        results = enricher.try_load_results()
        assert results is not None
        assert len(results) == 1
        assert results[0]["category"] == "FINANCIAL"

    def test_load_no_output_returns_none(self, enricher, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_OUTPUT_DIR", tmp_path / "agent_output")

        results = enricher.try_load_results()
        assert results is None


class TestDeprecatedMethods:
    """Test that old automated enrichment APIs are disabled."""

    def test_enrich_tweets_raises_runtime_error(self, enricher):
        with pytest.raises(RuntimeError, match="agent-native"):
            enricher.enrich_tweets([{"text": "test"}])

    def test_enrich_raises_runtime_error(self, enricher):
        with pytest.raises(RuntimeError, match="agent-native"):
            enricher.enrich({"description": "test"})


class TestHealth:
    """Test health reporting."""

    def test_get_health(self, enricher):
        health = enricher.get_health()
        assert health["mode"] == "agent-native"
        assert health["requires_checkpoint"] is True
        assert health["available"] is True
