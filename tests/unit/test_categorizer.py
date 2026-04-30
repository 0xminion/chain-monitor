"""Tests for agent-native EventCategorizer.

No keyword matching is tested here — the agent provides all categorization reasoning.
These tests verify task preparation, result application, and checkpoint mechanics.
"""

import json
import pytest
from pathlib import Path

from processors.categorizer import EventCategorizer


@pytest.fixture
def categorizer():
    return EventCategorizer()


@pytest.fixture
def sample_events():
    return [
        {"chain": "ethereum", "description": "Protocol hack drained $5M", "source": "RSS", "reliability": 0.9, "evidence": {}},
        {"chain": "polygon", "description": "Partnership announced with Chainlink", "source": "twitter", "reliability": 0.8, "evidence": {"author": "@polygon", "is_retweet": False}},
        {"chain": "solana", "description": "SEC issues wells notice", "source": "RSS", "reliability": 0.85, "evidence": {}},
    ]


class TestAgentTaskPreparation:
    """Test that prepare_agent_task creates valid checkpoint files."""

    def test_task_file_created(self, categorizer, sample_events, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = categorizer.prepare_agent_task(sample_events)
        assert path.exists()
        assert path.suffix == ".json"
        assert "categorize_task_" in path.name

    def test_task_contains_events(self, categorizer, sample_events, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = categorizer.prepare_agent_task(sample_events)
        data = json.loads(path.read_text())
        assert data["task_type"] == "categorize"
        assert "task_id" in data
        assert len(data["events"]) == 3
        assert data["events"][0]["id"] == 0
        assert data["events"][0]["chain"] == "ethereum"
        assert data["events"][1]["is_twitter"] is True

    def test_task_contains_instructions(self, categorizer, sample_events, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        path = categorizer.prepare_agent_task(sample_events)
        data = json.loads(path.read_text())
        assert "instructions" in data
        assert "RISK_ALERT" in data["instructions"]
        assert "output_format" in data

    def test_twitter_metadata_included(self, categorizer, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_INPUT_DIR", tmp_path / "agent_input")

        events = [
            {"chain": "polygon", "description": "Tweet text", "source": "twitter", "reliability": 0.8,
             "evidence": {"author": "@polygon", "role": "official", "is_retweet": True, "original_author": "@partner"}},
        ]
        path = categorizer.prepare_agent_task(events)
        data = json.loads(path.read_text())
        meta = data["events"][0]["twitter_metadata"]
        assert meta["author"] == "@polygon"
        assert meta["role"] == "official"
        assert meta["is_retweet"] is True
        assert meta["original_author"] == "@partner"


class TestApplyCategories:
    """Test that apply_categories correctly merges agent results into events."""

    def test_apply_single_category(self, categorizer, sample_events):
        agent_results = [
            {"id": 0, "category": "RISK_ALERT", "subcategory": "hack", "reasoning": "Security incident", "is_noise": False, "primary_mentions": ["ethereum"]},
        ]
        enriched = categorizer.apply_categories(sample_events[:1], agent_results)
        assert enriched[0]["category"] == "RISK_ALERT"
        assert enriched[0]["subcategory"] == "hack"
        assert enriched[0]["semantic"]["reasoning"] == "Security incident"
        assert enriched[0]["semantic"]["confidence"] == 0.85

    def test_apply_multiple_categories(self, categorizer, sample_events):
        agent_results = [
            {"id": 0, "category": "RISK_ALERT", "subcategory": "hack", "reasoning": "Hack", "is_noise": False, "primary_mentions": ["ethereum"]},
            {"id": 1, "category": "PARTNERSHIP", "subcategory": "collaboration", "reasoning": "Business dev", "is_noise": False, "primary_mentions": ["polygon"]},
            {"id": 2, "category": "REGULATORY", "subcategory": "enforcement", "reasoning": "SEC action", "is_noise": False, "primary_mentions": ["solana"]},
        ]
        enriched = categorizer.apply_categories(sample_events, agent_results)
        assert enriched[0]["category"] == "RISK_ALERT"
        assert enriched[1]["category"] == "PARTNERSHIP"
        assert enriched[2]["category"] == "REGULATORY"
        assert enriched[1]["semantic"]["subcategory"] == "collaboration"

    def test_missing_result_defaults_to_news(self, categorizer, sample_events):
        agent_results = [
            {"id": 0, "category": "RISK_ALERT", "subcategory": "hack", "reasoning": "Hack", "is_noise": False, "primary_mentions": []},
            # Missing id 1 and 2
        ]
        enriched = categorizer.apply_categories(sample_events, agent_results)
        assert enriched[0]["category"] == "RISK_ALERT"
        assert enriched[1]["category"] == "NEWS"
        assert enriched[2]["category"] == "NEWS"
        assert enriched[1]["semantic"]["confidence"] == 0.0

    def test_noise_flag_propagated(self, categorizer):
        events = [{"chain": "bitcoin", "description": "gm wagmi", "source": "twitter", "reliability": 0.5, "evidence": {}}]
        agent_results = [
            {"id": 0, "category": "NOISE", "subcategory": "general", "reasoning": "Low-value", "is_noise": True, "primary_mentions": []},
        ]
        enriched = categorizer.apply_categories(events, agent_results)
        assert enriched[0]["category"] == "NOISE"
        assert enriched[0]["semantic"]["is_noise"] is True


class TryLoadResults:
    """Test loading agent output from disk."""

    def test_load_existing_output(self, categorizer, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_OUTPUT_DIR", tmp_path / "agent_output")

        # Create a fake agent output file
        output_dir = tmp_path / "agent_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "categorize_output_20260430_120000.json"
        output_path.write_text(json.dumps({
            "task_type": "categorize",
            "task_id": "20260430_120000",
            "results": [
                {"id": 0, "category": "FINANCIAL", "subcategory": "tvl_milestone", "reasoning": "TVL hit $1B", "is_noise": False, "primary_mentions": []},
            ],
        }))

        results = categorizer.try_load_results()
        assert results is not None
        assert len(results) == 1
        assert results[0]["category"] == "FINANCIAL"

    def test_load_no_output_returns_none(self, categorizer, tmp_path, monkeypatch):
        from processors import agent_native as an
        monkeypatch.setattr(an, "AGENT_OUTPUT_DIR", tmp_path / "agent_output")

        results = categorizer.try_load_results()
        assert results is None


class TestDeprecatedCategorize:
    """Test that the old keyword API is disabled."""

    def test_categorize_raises_runtime_error(self, categorizer):
        with pytest.raises(RuntimeError, match="agent-native"):
            categorizer.categorize({"description": "something"})
