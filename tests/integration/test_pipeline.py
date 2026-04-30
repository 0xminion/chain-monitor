"""Integration test for full signal pipeline (agent-native).

Categorization is now agent-native and requires a checkpoint.
These tests focus on scoring, reinforcement, and downstream analysis
using pre-categorized events (as if the agent had already categorized them).
"""

import pytest

from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.signal import Signal
from main import _should_send


@pytest.fixture
def pipeline_components(tmp_path, monkeypatch, mock_config):
    """Set up pipeline components that run after agent categorization."""
    import processors.reinforcement as rein_mod
    monkeypatch.setattr(rein_mod, "STORAGE_DIR", tmp_path / "events")

    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    return {
        "scorer": scorer,
        "reinforcer": reinforcer,
    }


def _make_categorized_event(chain, description, category, subcategory, source, reliability, evidence=None, value=None):
    """Helper to create a pre-categorized event dict (as agent would produce)."""
    ev = {
        "chain": chain,
        "description": description,
        "category": category,
        "subcategory": subcategory,
        "source": source,
        "reliability": reliability,
        "evidence": evidence or {},
        "semantic": {
            "category": category,
            "subcategory": subcategory,
            "confidence": 0.85,
            "reasoning": f"Agent categorized as {category}/{subcategory}",
            "is_noise": False,
            "primary_mentions": [chain],
        },
    }
    if value is not None:
        ev["value"] = value
    return ev


class TestFullPipeline:
    """Test end-to-end signal flow with pre-categorized events."""

    def test_categorized_to_score_flow(self, pipeline_components):
        """Pre-categorized event → scorer → Signal."""
        scorer = pipeline_components["scorer"]

        cat_event = _make_categorized_event(
            "ethereum", "Ethereum TVL crosses $65B milestone",
            "FINANCIAL", "tvl_milestone", "DefiLlama", 0.9,
            evidence={"metric": "tvl_milestone", "tvl": 65_000_000_000},
        )

        signal = scorer.score(cat_event)
        assert signal.chain == "ethereum"
        assert signal.category == "FINANCIAL"
        assert signal.impact == 4  # tvl_milestone = 4
        assert signal.priority_score == signal.impact * signal.urgency

    def test_full_pipeline_with_reinforcement(self, pipeline_components):
        """Pre-categorized events → scorer → reinforcer."""
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        # First event
        cat1 = _make_categorized_event(
            "ethereum", "Ethereum mainnet upgrade Pectra goes live",
            "TECH_EVENT", "upgrade", "GitHub", 0.95,
            evidence={"metric": "new_release"},
        )
        sig1 = scorer.score(cat1)
        result1, action1 = reinforcer.process(sig1)
        assert action1 == "created"

        # Similar event (should reinforce)
        cat2 = _make_categorized_event(
            "ethereum", "Ethereum mainnet upgrade Pectra goes live now",
            "TECH_EVENT", "upgrade", "RSS", 0.7,
            evidence={"metric": "rss_post"},
        )
        sig2 = scorer.score(cat2)
        result2, action2 = reinforcer.process(sig2)
        assert action2 == "reinforced"
        assert result2.source_count == 2

        # Different chain event (should create new)
        cat3 = _make_categorized_event(
            "solana", "Solana TVL surges 35% in 7 days",
            "FINANCIAL", "tvl_spike", "DefiLlama", 0.85,
            evidence={"metric": "tvl_7d_change", "pct_change": 35},
        )
        sig3 = scorer.score(cat3)
        result3, action3 = reinforcer.process(sig3)
        assert action3 == "created"

        # Verify signals exist in reinforcer storage
        all_signals = list(reinforcer.signals.values())
        assert len(all_signals) >= 2  # ethereum (reinforced) + solana (created)
        chains = {s.chain for s in all_signals}
        assert "ethereum" in chains
        assert "solana" in chains

    def test_risk_alert_high_priority(self, pipeline_components):
        """Hack event should produce high-priority signal."""
        scorer = pipeline_components["scorer"]

        cat = _make_categorized_event(
            "ethereum", "Hack drained $15M from bridge protocol",
            "RISK_ALERT", "hack", "DefiLlama", 0.95,
            evidence={"amount": 15_000_000},
            value=15_000_000,
        )

        signal = scorer.score(cat)
        assert signal.impact == 5  # hack >$10M = 5
        assert signal.urgency == 3  # hack urgency = 3
        assert signal.priority_score == 15

    def test_regulatory_enforcement_urgent(self, pipeline_components):
        """Enforcement action should be high impact + high urgency."""
        scorer = pipeline_components["scorer"]

        cat = _make_categorized_event(
            "hyperliquid", "SEC enforcement action filed against protocol",
            "REGULATORY", "enforcement", "RSS", 0.8,
        )
        signal = scorer.score(cat)
        assert signal.impact == 5  # hyperliquid regulatory override
        assert signal.urgency == 3  # enforcement urgency = 3
        assert signal.priority_score == 15

    def test_digest_should_send(self, pipeline_components):
        """Verify _should_send logic with real signals."""
        scorer = pipeline_components["scorer"]

        events = [
            _make_categorized_event("ethereum", "TVL crosses milestone", "FINANCIAL", "tvl_milestone", "DL", 0.9),
            _make_categorized_event("solana", "Funding raised $50M", "FINANCIAL", "funding_round", "RSS", 0.7),
            _make_categorized_event("arbitrum", "New upgrade released", "TECH_EVENT", "upgrade", "GH", 0.9),
        ]

        from processors.pipeline_types import ChainDigest
        digests = []
        for evt in events:
            s = scorer.score(evt)
            # Build a minimal ChainDigest for _should_send
            digests.append(ChainDigest(
                chain=s.chain,
                chain_tier=1,
                chain_category="L1",
                summary="",
                key_events=[],
                priority_score=s.priority_score,
                dominant_topic="",
                sources_seen=1,
                event_count=1,
                confidence=0.8,
            ))

        result = _should_send(digests)
        assert result is True

    def test_echo_detection_in_pipeline(self, pipeline_components):
        """Repeated similar events should be detected as echoes."""
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        cat = _make_categorized_event(
            "ethereum", "Vitalik speaking at conference keynote event",
            "VISIBILITY", "keynote", "RSS", 0.6,
        )

        # Process 3 times to build up source_count
        for _ in range(3):
            s = scorer.score(cat)
            reinforcer.process(s)

        # 4th time should be echo
        s = scorer.score(cat)
        _, action = reinforcer.process(s)
        assert action == "echo"


class TestAgentCategorizerCheckpoint:
    """Verify that EventCategorizer now requires agent checkpoint."""

    def test_categorizer_raises_on_direct_call(self):
        from processors.categorizer import EventCategorizer
        cat = EventCategorizer()
        with pytest.raises(RuntimeError, match="agent-native"):
            cat.categorize({"description": "test event"})
