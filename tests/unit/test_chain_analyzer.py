"""Tests for per-chain deterministic analyzer."""

import pytest

from processors.pipeline_types import ChainDigest
from processors.chain_analyzer import analyze_chain, analyze_all_chains
from processors.signal import Signal


def _make_signal(chain="solana", category="TECH_EVENT", description="test", priority_score=5, rel=0.8, activity=None):
    sig = Signal(
        id=Signal.generate_id(chain, category, description),
        chain=chain,
        category=category,
        description=description,
        impact=3,
        urgency=2,
        priority_score=priority_score,
    )
    if activity:
        for a in activity:
            sig.add_activity(a["source"], a.get("reliability", rel), a.get("evidence", description))
    else:
        sig.add_activity("rss", rel, description)
    return sig


class TestChainAnalyzer:

    @pytest.mark.asyncio
    async def test_analyze_chain_with_signals(self):
        signals = [
            _make_signal("solana", "TECH_EVENT", "Solana v2 released", priority_score=8, rel=0.8),
            _make_signal("solana", "TECH_EVENT", "Solana v2 on GitHub", priority_score=6, rel=0.9),
        ]

        digest = await analyze_chain("solana", signals)
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "solana"
        assert digest.priority_score > 0
        assert digest.dominant_topic == "Tech Event"
        assert len(digest.key_events) == 2
        assert digest.key_events[0]["category"] == "TECH_EVENT"
        assert digest.event_count == 2
        assert digest.sources_seen == 1  # both from "rss"

    @pytest.mark.asyncio
    async def test_analyze_chain_empty_signals(self):
        """Empty signals should produce a quiet digest, not crash."""
        digest = await analyze_chain("solana", [])
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "solana"
        assert digest.priority_score == 0
        assert digest.dominant_topic == "Quiet"
        assert digest.event_count == 0

    @pytest.mark.asyncio
    async def test_analyze_chain_source_diversity_bonus(self):
        """More independent sources should boost priority score."""
        signals = [
            _make_signal("solana", "PARTNERSHIP", "Partner A", priority_score=5, rel=0.9,
                         activity=[{"source": "Twitter", "reliability": 0.9, "evidence": "tweet"}]),
            _make_signal("solana", "PARTNERSHIP", "Partner B", priority_score=4, rel=0.8,
                         activity=[{"source": "RSS", "reliability": 0.8, "evidence": "blog"}]),
            _make_signal("solana", "PARTNERSHIP", "Partner C", priority_score=3, rel=0.7,
                         activity=[{"source": "GitHub", "reliability": 0.7, "evidence": "repo"}]),
        ]
        digest = await analyze_chain("solana", signals)
        # Top score is 5, +2 bonus for 3 sources (sources_seen - 1) = 7
        assert digest.priority_score == 7
        assert digest.sources_seen == 3

    @pytest.mark.asyncio
    async def test_analyze_all_chains_includes_empty(self):
        """Chains with no signals should still appear in output."""
        signals_by_chain = {
            "solana": [_make_signal("solana", "TECH_EVENT", "Upgrade", priority_score=5)],
        }
        digests = await analyze_all_chains(signals_by_chain)
        chains = {d.chain for d in digests}
        assert "solana" in chains
        # Should include all configured chains (even empty ones)
        assert len(digests) >= len(signals_by_chain)
