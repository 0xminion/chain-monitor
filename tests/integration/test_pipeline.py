"""Integration test for full signal pipeline."""

import pytest

from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.signal import Signal
from main import _should_send


@pytest.fixture
def pipeline_components(tmp_path, monkeypatch, mock_config):
    """Set up all pipeline components."""
    import processors.reinforcement as rein_mod
    monkeypatch.setattr(rein_mod, "STORAGE_DIR", tmp_path / "events")

    categorizer = EventCategorizer()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    return {
        "categorizer": categorizer,
        "scorer": scorer,
        "reinforcer": reinforcer,
    }


class TestFullPipeline:
    """Test end-to-end signal flow."""

    def test_categorize_to_score_flow(self, pipeline_components):
        """Raw event → categorizer → scorer → Signal."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        raw_event = {
            "chain": "ethereum",
            "description": "Ethereum TVL crosses $65B milestone",
            "source": "DefiLlama",
            "reliability": 0.9,
            "evidence": {"metric": "tvl_milestone", "tvl": 65_000_000_000},
        }

        categorized = cat.categorize(raw_event)
        assert categorized["category"] == "FINANCIAL"
        assert categorized["subcategory"] == "tvl_milestone"

        signal = scorer.score(categorized)
        assert signal.chain == "ethereum"
        assert signal.category == "FINANCIAL"
        assert signal.impact == 4  # tvl_milestone = 4
        assert signal.priority_score == signal.impact * signal.urgency

    def test_full_pipeline_with_reinforcement(self, pipeline_components):
        """Raw events → categorizer → scorer → reinforcer."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        # First event
        raw1 = {
            "chain": "ethereum",
            "description": "Ethereum mainnet upgrade Pectra goes live",
            "source": "GitHub",
            "reliability": 0.95,
            "evidence": {"metric": "new_release"},
        }
        cat1 = cat.categorize(raw1)
        sig1 = scorer.score(cat1)
        result1, action1 = reinforcer.process(sig1)
        assert action1 == "created"

        # Similar event (should reinforce)
        raw2 = {
            "chain": "ethereum",
            "description": "Ethereum mainnet upgrade Pectra goes live now",
            "source": "RSS",
            "reliability": 0.7,
            "evidence": {"metric": "rss_post"},
        }
        cat2 = cat.categorize(raw2)
        sig2 = scorer.score(cat2)
        result2, action2 = reinforcer.process(sig2)
        assert action2 == "reinforced"
        assert result2.source_count == 2

        # Different chain event (should create new)
        raw3 = {
            "chain": "solana",
            "description": "Solana TVL surges 35% in 7 days",
            "source": "DefiLlama",
            "reliability": 0.85,
            "evidence": {"metric": "tvl_7d_change", "pct_change": 35},
        }
        cat3 = cat.categorize(raw3)
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
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        raw = {
            "chain": "ethereum",
            "description": "Hack drained $15M from bridge protocol",
            "source": "DefiLlama",
            "reliability": 0.95,
            "evidence": {"amount": 15_000_000},
            "value": 15_000_000,
        }
        categorized = cat.categorize(raw)
        assert categorized["category"] == "RISK_ALERT"
        assert categorized["subcategory"] == "hack"

        signal = scorer.score(categorized)
        assert signal.impact == 5  # hack >$10M = 5
        assert signal.urgency == 3  # hack urgency = 3
        assert signal.priority_score == 15

    def test_regulatory_enforcement_urgent(self, pipeline_components):
        """Enforcement action should be high impact + high urgency."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        raw = {
            "chain": "hyperliquid",
            "description": "SEC enforcement action filed against protocol",
            "source": "RSS",
            "reliability": 0.8,
            "evidence": {},
        }
        categorized = cat.categorize(raw)
        signal = scorer.score(categorized)
        assert signal.impact == 5  # hyperliquid regulatory override
        assert signal.urgency == 3  # enforcement urgency = 3
        assert signal.priority_score == 15

    def test_digest_should_send(self, pipeline_components):
        """Verify _should_send logic with real signals."""
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]

        events = [
            {"chain": "ethereum", "description": "TVL crosses milestone", "source": "DL", "reliability": 0.9, "evidence": {}},
            {"chain": "solana", "description": "Funding raised $50M", "source": "RSS", "reliability": 0.7, "evidence": {}},
            {"chain": "arbitrum", "description": "New upgrade released", "source": "GH", "reliability": 0.9, "evidence": {}},
        ]

        from processors.pipeline_types import ChainDigest
        digests = []
        for evt in events:
            c = cat.categorize(evt)
            s = scorer.score(c)
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
        cat = pipeline_components["categorizer"]
        scorer = pipeline_components["scorer"]
        reinforcer = pipeline_components["reinforcer"]

        raw = {
            "chain": "ethereum",
            "description": "Vitalik speaking at conference keynote event",
            "source": "RSS",
            "reliability": 0.6,
            "evidence": {},
        }

        # Process 3 times to build up source_count
        for _ in range(3):
            c = cat.categorize(dict(raw))
            s = scorer.score(c)
            reinforcer.process(s)

        # 4th time should be echo
        c = cat.categorize(dict(raw))
        s = scorer.score(c)
        _, action = reinforcer.process(s)
        assert action == "echo"
