"""Tests for DailyDigestFormatter — agent-native.

The running agent produces the actual digest. This formatter returns stubs.
"""

import pytest
from output.daily_digest import DailyDigestFormatter
from processors.signal import Signal


@pytest.fixture
def formatter():
    return DailyDigestFormatter()


def _make_signal(chain="ethereum", category="TECH_EVENT", description="test", impact=3, urgency=2, trader_context=""):
    sig = Signal(
        id=Signal.generate_id(chain, category, description),
        chain=chain, category=category, description=description,
        impact=impact, urgency=urgency, priority_score=impact * urgency,
        trader_context=trader_context,
    )
    sig.add_activity("test", 0.8, description)
    return sig


class TestFormatStub:
    def test_no_signals(self, formatter):
        result = formatter.format([])
        assert "Chain Monitor" in result
        assert "agent" in result.lower() or "No signals" in result

    def test_with_signals(self, formatter):
        signals = [
            _make_signal("solana", "TECH_EVENT", "Upgrade", 3, 2),
            _make_signal("ethereum", "PARTNERSHIP", "Integration", 3, 2),
        ]
        result = formatter.format(signals)
        assert "Chain Monitor" in result
        assert "2 signal" in result or "agent" in result.lower()


class TestShouldSend:
    def test_should_send(self, formatter):
        signals = [_make_signal("eth", "TECH_EVENT", "T", 1, 1)]
        assert formatter.should_send(signals) is True  # agent-native: let agent decide
