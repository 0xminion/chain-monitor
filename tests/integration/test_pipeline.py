"""Integration test for full signal pipeline — agent-native.

The running agent performs semantic classification, scoring, and synthesis.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer, AgentStubSignal
from processors.reinforcement import SignalReinforcer
from processors.signal import Signal
from output.daily_digest import DailyDigestFormatter


@pytest.fixture
def pipeline_components(tmp_path, monkeypatch, mock_config):
    import processors.reinforcement as rein_mod
    monkeypatch.setattr(rein_mod, "STORAGE_DIR", tmp_path / "events")

    return {
        "categorizer": EventCategorizer(),
        "scorer": SignalScorer(),
        "reinforcer": SignalReinforcer(),
        "formatter": DailyDigestFormatter(),
    }


class TestFullPipeline:
    def test_preserved_category(self, pipeline_components):
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        raw_event = {
            "chain": "ethereum",
            "category": "FINANCIAL",
            "description": "TVL crosses $65B",
            "source": "DefiLlama",
            "reliability": 0.9,
            "evidence": {"metric": "tvl_milestone"},
        }

        categorized = cat.categorize(raw_event)
        assert categorized["category"] == "FINANCIAL"

        signal = scorer.score(categorized)
        assert signal.chain == "ethereum"
        assert signal.category == "FINANCIAL"
        assert signal.impact == AgentStubSignal.default_impact
        assert signal.priority_score == AgentStubSignal.default_priority

    def test_reinforcement_same_description(self, pipeline_components):
        """Two events with the SAME description should trigger reinforcement."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        raw1 = {"chain": "ethereum", "category": "TECH_EVENT", "description": "Mainnet upgrade goes live", "source": "GitHub", "reliability": 0.95, "evidence": {}}
        cat1 = cat.categorize(dict(raw1))
        sig1 = scorer.score(cat1)
        result1, action1 = reinforcer.process(sig1)
        assert action1 == "created"

        # Same description, different source → should be reinforced
        raw2 = {"chain": "ethereum", "category": "TECH_EVENT", "description": "Mainnet upgrade goes live", "source": "RSS", "reliability": 0.7, "evidence": {}}
        cat2 = cat.categorize(dict(raw2))
        sig2 = scorer.score(cat2)
        result2, action2 = reinforcer.process(sig2)
        assert result2.source_count == 2

    def test_reinforcement_different_description(self, pipeline_components):
        """Different descriptions should create separate signals."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        raw1 = {"chain": "ethereum", "category": "TECH_EVENT", "description": "Upgrade live now", "source": "GitHub", "reliability": 0.95, "evidence": {}}
        cat1 = cat.categorize(dict(raw1))
        sig1 = scorer.score(cat1)
        result1, action1 = reinforcer.process(sig1)
        assert action1 == "created"

        raw2 = {"chain": "ethereum", "category": "TECH_EVENT", "description": "Mainnet upgrade complete", "source": "RSS", "reliability": 0.7, "evidence": {}}
        cat2 = cat.categorize(dict(raw2))
        sig2 = scorer.score(cat2)
        result2, action2 = reinforcer.process(sig2)
        assert action2 == "created"  # different description = new signal

    def test_risk_stub(self, pipeline_components):
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        raw = {"chain": "ethereum", "category": "RISK_ALERT", "description": "Hack", "source": "DL", "reliability": 0.95, "subcategory": "hack"}
        categorized = cat.categorize(raw)
        assert categorized["category"] == "RISK_ALERT"

        signal = scorer.score(categorized)
        assert signal.impact == AgentStubSignal.default_impact
        assert signal.priority_score == AgentStubSignal.default_priority

    def test_digest_deferred(self, pipeline_components):
        formatter = pipeline_components["formatter"]
        signals = [Signal(id="t", chain="eth", category="TECH_EVENT", description="Test", impact=3, urgency=2, priority_score=6)]
        for s in signals:
            s.add_activity("test", 0.8, "test")

        digest = formatter.format(signals)
        assert "Chain Monitor" in digest
        assert "agent" in digest.lower() or "deferred" in digest.lower()

    def test_should_send(self, pipeline_components):
        formatter = pipeline_components["formatter"]
        signals = [Signal(id="t", chain="eth", category="TECH_EVENT", description="Test", impact=1, urgency=1, priority_score=1, trader_context="")]
        assert formatter.should_send(signals) is True
