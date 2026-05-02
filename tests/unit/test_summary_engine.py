"""Tests for summary engine (agent-native prompt builder)."""

import os
import pytest

from processors.pipeline_types import ChainDigest
from processors.summary_engine import synthesize_digest, _build_daily_prompt


class TestSummaryEngine:

    @pytest.mark.asyncio
    async def test_empty_digests(self):
        result = await synthesize_digest([])
        assert "📊 Chain Monitor" in result
        assert "Quiet day" in result

    @pytest.mark.asyncio
    async def test_builds_agent_prompt(self):
        """When digests exist, synthesize_digest saves a prompt and returns placeholder."""
        digests = [
            ChainDigest("solana", 1, "majors", "", priority_score=8, dominant_topic="Mainnet v2",
                        key_events=[{"topic": "v2 release", "category": "TECH_EVENT", "priority": 8,
                                     "confidence": 0.9, "detail": "Solana v2 tagged", "why_it_matters": "Perf gains",
                                     "url": "https://x.com/solana/status/123", "sources": ["Twitter"]}]),
            ChainDigest("ethereum", 1, "majors", "", priority_score=2, dominant_topic="Quiet",
                        key_events=[]),
        ]
        result = await synthesize_digest(digests)
        assert "🤖 Agent synthesis required" in result
        assert "daily_prompt_" in result
        # Verify prompt was actually saved
        assert os.path.exists(digests[0].key_events[0].get("url", "")) == False  # placeholder

    @pytest.mark.asyncio
    async def test_prompt_contains_chain_data(self):
        """The saved prompt should contain chain names, scores, and event details."""
        digests = [
            ChainDigest("solana", 1, "majors", "", priority_score=8, dominant_topic="Mainnet v2",
                        key_events=[{"topic": "v2 release", "category": "TECH_EVENT", "priority": 8,
                                     "confidence": 0.9, "detail": "Solana v2 tagged", "why_it_matters": "Perf gains",
                                     "url": "https://x.com/solana/status/123", "sources": ["Twitter"]}]),
        ]
        prompt = _build_daily_prompt(digests, date_str="Apr 29, 2026")
        assert "SOLANA" in prompt
        assert "Score: 8" in prompt
        assert "v2 release" in prompt
        assert "https://x.com/solana/status/123" in prompt
        assert "Daily Digest Agent Prompt" in prompt

    @pytest.mark.asyncio
    async def test_prompt_with_health(self):
        digests = [
            ChainDigest("solana", 1, "majors", "", priority_score=5, dominant_topic="Upgrade"),
        ]
        health = {"defillama": {"status": "healthy"}, "twitter": {"status": "down"}}
        prompt = _build_daily_prompt(digests, source_health=health, date_str="Apr 29, 2026")
        assert "Collectors:" in prompt
        assert "down" in prompt
