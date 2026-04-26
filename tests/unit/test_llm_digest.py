"""Unit tests for LLM-powered digest generator."""

import json
from unittest.mock import MagicMock, patch

import pytest

from output.llm_digest_generator import LLMDigestGenerator, _build_digest_prompt, _sanitize_digest
from processors.signal import Signal


class TestBuildDigestPrompt:
    def test_prompt_includes_signals(self):
        signals = [
            Signal(id="a", chain="ethereum", category="TECH_EVENT", description="Mainnet upgrade", impact=4, urgency=2, priority_score=8),
            Signal(id="b", chain="solana", category="RISK_ALERT", description="Hack", impact=5, urgency=3, priority_score=15),
        ]
        prompt = _build_digest_prompt("Apr 26, 2025", signals, {}, {})
        assert "Mainnet upgrade" in prompt
        assert "Hack" in prompt
        assert "Critical" in prompt
        assert "Source Health:" in prompt

    def test_prompt_no_signals(self):
        prompt = _build_digest_prompt("Apr 26, 2025", [], {}, {})
        assert "No notable signals" in prompt


class TestSanitizeDigest:
    def test_strips_html_tags(self):
        raw = "<p>Hello</p>\n\n\n\n<b>World</b>"
        result = _sanitize_digest(raw)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "\n\n\n" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strips_code_fences(self):
        raw = "```\nhello\n```"
        result = _sanitize_digest(raw)
        assert "```" not in result
        assert "hello" in result

    def test_bare_url_linked(self):
        raw = "Check out https://example.com/page"
        result = _sanitize_digest(raw)
        assert "[link](https://example.com/page)" in result


class TestLLMDigestGeneratorMocked:
    def test_llm_success(self):
        mock_client = MagicMock()
        mock_client.generate.return_value = "📊 Chain Monitor — Apr 26\n\n🧠 Today's theme\nA key theme today."

        gen = LLMDigestGenerator(client=mock_client)
        mock_client.generate.assert_not_called()

        signals = [Signal(id="a", chain="eth", category="TECH_EVENT", description="upgrade", impact=4, urgency=2)]
        signals[0].add_activity("test", 0.9, {"url": "https://example.com"})

        result = gen.generate(signals, source_health={"defillama": {"status": "healthy"}})
        assert result is not None
        assert "🧠" in result
        mock_client.generate.assert_called_once()

    def test_llm_failure_returns_none(self):
        from processors.llm_client import LLMError
        mock_client = MagicMock()
        mock_client.generate.side_effect = LLMError("LLM down")

        gen = LLMDigestGenerator(client=mock_client)
        signals = [Signal(id="a", chain="eth", category="TECH_EVENT", description="upgrade", impact=4, urgency=2)]
        signals[0].add_activity("test", 0.9, {})

        result = gen.generate(signals)
        assert result is None
