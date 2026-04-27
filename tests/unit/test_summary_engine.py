"""Tests for summary engine."""

import pytest
from unittest.mock import MagicMock

from processors.pipeline_types import ChainDigest
from processors.summary_engine import synthesize_digest
from processors.llm_client import LLMError


class TestSummaryEngine:

    @pytest.mark.asyncio
    async def test_empty_digests(self):
        result = await synthesize_digest([])
        assert "📊 Chain Monitor" in result
        assert "Quiet day" in result

    @pytest.mark.asyncio
    async def test_fallback_digest_no_llm(self):
        """When LLM is disabled, produce structured fallback."""
        import os
        os.environ["LLM_DIGEST_ENABLED"] = "false"
        digests = [
            ChainDigest("solana", 1, "majors", "Solana upgrade", priority_score=8, dominant_topic="Mainnet v2"),
            ChainDigest("ethereum", 1, "majors", "Eth quiet", priority_score=2, dominant_topic="Nothing major"),
        ]
        result = await synthesize_digest(digests)
        assert "📊 Chain Monitor" in result
        assert "Solana" in result or "solana" in result

    @pytest.mark.asyncio
    async def test_llm_prose_for_high_priority(self):
        """When LLM works and chains have priority ≥5, prose digest is produced."""
        client = MagicMock()
        client.generate.return_value = (
            "📊 Chain Monitor — Apr 27, 2026\n\n"
            "🧠 Today's theme\nSolana is the main story.\n\n"
            "**SOLANA (Score: 8)**\nMajor upgrade releasing that improves throughput.\n\n"
            "👀 Watch\nFollow ETH Dencun timeline."
        )

        digests = [
            ChainDigest("solana", 1, "majors", "Solana upgrade", priority_score=8, dominant_topic="Mainnet v2"),
        ]
        result = await synthesize_digest(digests, client=client)
        assert "Solana" in result
        assert "👀 Watch" in result

    @pytest.mark.asyncio
    async def test_llm_failure_uses_fallback(self):
        """LLM error should fall back to structured output."""
        client = MagicMock()
        client.generate.side_effect = LLMError("timeout")

        digests = [
            ChainDigest("solana", 1, "majors", "Upgrade", priority_score=8, dominant_topic="Mainnet v2"),
        ]
        result = await synthesize_digest(digests, client=client)
        assert "📊 Chain Monitor" in result
