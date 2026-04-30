"""Tests for summary engine.

v2.0: Agent-native — deterministic formatting, no LLM.
"""

import pytest

from processors.pipeline_types import ChainDigest
from processors.summary_engine import synthesize_digest


class TestSummaryEngine:

    @pytest.mark.asyncio
    async def test_empty_digests(self):
        result = await synthesize_digest([])
        assert "📊 Chain Monitor" in result
        assert "Quiet day" in result

    @pytest.mark.asyncio
    async def test_digest_with_high_priority_chain(self):
        digests = [
            ChainDigest("solana", 1, "majors", "Solana upgrade", priority_score=8, dominant_topic="Mainnet v2"),
            ChainDigest("ethereum", 1, "majors", "Eth quiet", priority_score=2, dominant_topic="Nothing major"),
        ]
        result = await synthesize_digest(digests)
        assert "📊 Chain Monitor" in result
        assert "Solana" in result or "solana" in result
        assert "ethereum" in result or "Ethereum" in result
        assert "👀 Watch" in result

    @pytest.mark.asyncio
    async def test_digest_with_health_footer(self):
        digests = [
            ChainDigest("solana", 1, "majors", "Solana upgrade", priority_score=8, dominant_topic="Mainnet v2"),
        ]
        health = {
            "defillama": {"status": "healthy"},
            "twitter": {"status": "down", "last_error": "login wall"},
        }
        result = await synthesize_digest(digests, source_health=health)
        assert "⚠️ Source health" in result
        assert "1/2 healthy" in result
