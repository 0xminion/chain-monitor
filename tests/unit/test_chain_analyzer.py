"""Tests for per-chain analyzer — agent-native.

The analyzer groups events by chain and returns raw, unmerged key_events.
The running agent performs merging, scoring, and synthesis.
"""

import pytest
from processors.pipeline_types import RawEvent, ChainDigest
from processors.chain_analyzer import analyze_chain


class TestChainAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_chain_with_events(self):
        events = [
            RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2 released", "rss", 0.8),
            RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2 on GitHub", "github", 0.9),
        ]
        digest = await analyze_chain("solana", events, client=None)
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "solana"
        assert digest.priority_score == 0             # agent assigns
        assert digest.dominant_topic == ""          # agent assigns
        assert len(digest.key_events) == 2           # raw, unmerged
        assert digest.key_events[0]["category"] == "TECH_EVENT"

    @pytest.mark.asyncio
    async def test_analyze_chain_empty_events(self):
        digest = await analyze_chain("solana", [], client=None)
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "solana"
        assert digest.priority_score == 0
        assert "no signals" in digest.summary.lower()

    @pytest.mark.asyncio
    async def test_key_events_keep_all(self):
        events = [
            RawEvent("ethereum", "RISK_ALERT", "hack", "Bridge hack", "rss", 0.95),
        ]
        digest = await analyze_chain("ethereum", events, client=None)
        assert len(digest.key_events) == 1
        assert digest.key_events[0]["detail"] == "Bridge hack"
