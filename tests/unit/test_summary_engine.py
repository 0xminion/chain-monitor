"""Tests for summary engine — agent-native.

The running agent synthesizes the digest. This module returns stubs.
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
    async def test_digest_with_events(self):
        digests = [
            ChainDigest("solana", 1, "majors", "", priority_score=0, dominant_topic=""),
            ChainDigest("ethereum", 1, "majors", "", priority_score=0, dominant_topic=""),
        ]
        result = await synthesize_digest(digests)
        assert "📊 Chain Monitor" in result
        assert "Agent mode active" in result
        assert "Chains with data" in result

    @pytest.mark.asyncio
    async def test_digest_with_health(self):
        digests = [ChainDigest("solana", 1, "majors", "", priority_score=0, dominant_topic="")]
        health = {"defillama": {"status": "healthy"}, "twitter": {"status": "down"}}
        result = await synthesize_digest(digests, source_health=health)
        assert "⚠️ Source health" in result
