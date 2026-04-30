"""Tests for per-chain semantic analyzer.

v2.0: Agent-native — all tests run without any LLM mocking.
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
        assert digest.priority_score >= 2   # at least one event with rel 0.8
        assert digest.dominant_topic is not None
        assert len(digest.key_events) >= 1
        assert digest.key_events[0]["category"] == "TECH_EVENT"

    @pytest.mark.asyncio
    async def test_analyze_chain_empty_events(self):
        digest = await analyze_chain("solana", [], client=None)
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "solana"
        assert digest.priority_score == 0
        assert "no signals" in digest.summary.lower() or "quiet" in digest.summary.lower()

    @pytest.mark.asyncio
    async def test_analyze_chain_priority_scoring(self):
        events = [
            RawEvent("ethereum", "RISK_ALERT", "hack", "Major bridge hack", "rss", 0.95),
        ]
        digest = await analyze_chain("ethereum", events, client=None)
        assert isinstance(digest, ChainDigest)
        assert digest.chain == "ethereum"
        assert digest.priority_score >= 10  # RISK_ALERT = 15 * 0.95

    @pytest.mark.asyncio
    async def test_analyze_chain_multiple_events_merged(self):
        events = [
            RawEvent("bitcoin", "PARTNERSHIP", "integration", "Visa integrates Bitcoin", "rss", 0.9),
            RawEvent("bitcoin", "PARTNERSHIP", "integration", "Bitcoin Visa partnership confirmed", "twitter", 0.85),
        ]
        digest = await analyze_chain("bitcoin", events, client=None)
        assert isinstance(digest, ChainDigest)
        # Merged events should produce fewer key_events than input events
        assert len(digest.key_events) <= len(events)

    @pytest.mark.asyncio
    async def test_analyze_chain_trading_noise_low_priority(self):
        events = [
            RawEvent("solana", "FINANCIAL", "general", "Price prediction: SOL to $500", "tradingview", 0.7),
        ]
        digest = await analyze_chain("solana", events, client=None)
        # Trading noise gets a penalty, score should be lower
        assert isinstance(digest, ChainDigest)
        assert digest.priority_score < 5
