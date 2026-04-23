"""Tests for DailyDigestFormatter."""

import pytest
from output.daily_digest import DailyDigestFormatter
from processors.signal import Signal


@pytest.fixture
def formatter(mock_config):
    return DailyDigestFormatter()


def _make_signal(chain="ethereum", category="TECH_EVENT", description="test", impact=2, urgency=1, trader_context=""):
    sig = Signal(
        id=Signal.generate_id(chain, category, description),
        chain=chain,
        category=category,
        description=description,
        impact=impact,
        urgency=urgency,
        priority_score=impact * urgency,
        trader_context=trader_context,
    )
    sig.add_activity("test", 0.8, description)
    return sig


class TestFormatNoSignals:
    """Test format with no signals."""

    def test_empty_signals(self, formatter):
        result = formatter.format([])
        assert "No high-priority events. Quiet day." in result
        assert "Chain Monitor" in result

    def test_no_signals_has_date(self, formatter):
        result = formatter.format([])
        # Should have date in header
        assert "2026" in result


class TestFormatWithSignals:
    """Test format with various priority signals."""

    def test_critical_section(self, formatter):
        sig = _make_signal(chain="ethereum", impact=5, urgency=3, description="Critical hack")
        result = formatter.format([sig])
        assert "Critical" in result
        assert "Score \u22658" in result

    def test_high_section(self, formatter):
        sig = _make_signal(chain="ethereum", impact=3, urgency=2, description="High event")
        result = formatter.format([sig])
        assert "High" in result
        assert "Score 5-7" in result

    def test_notable_section(self, formatter):
        sig = _make_signal(chain="ethereum", impact=2, urgency=2, description="Notable event")
        result = formatter.format([sig])
        assert "Medium" in result
        assert "Score 3-4" in result

    def test_sorted_by_priority(self, formatter):
        s1 = _make_signal(chain="ethereum", impact=4, urgency=2, description="Lower priority")
        s2 = _make_signal(chain="solana", impact=5, urgency=3, description="Higher priority")
        result = formatter.format([s1, s2])
        # Critical (s2) should appear before High (s1)
        assert result.index("Higher priority") < result.index("Lower priority")

    def test_signal_content_in_output(self, formatter):
        sig = _make_signal(chain="ethereum", impact=4, urgency=2, description="TVL milestone crossed")
        result = formatter.format([sig])
        assert "Ethereum" in result
        assert "TVL milestone crossed" in result


class TestShouldSend:
    """Test should_send logic."""

    def test_should_send_with_3_events_ge_6(self, formatter):
        signals = [
            _make_signal(impact=3, urgency=2),  # priority=6
            _make_signal(impact=3, urgency=2),  # priority=6
            _make_signal(impact=3, urgency=2),  # priority=6
        ]
        assert formatter.should_send(signals) is True

    def test_should_not_send_with_2_events(self, formatter):
        signals = [
            _make_signal(impact=3, urgency=2),  # priority=6
            _make_signal(impact=3, urgency=2),  # priority=6
        ]
        assert formatter.should_send(signals) is False

    def test_should_not_send_with_low_priority(self, formatter):
        signals = [
            _make_signal(impact=2, urgency=1),  # priority=2
            _make_signal(impact=2, urgency=1),  # priority=2
            _make_signal(impact=2, urgency=1),  # priority=2
        ]
        assert formatter.should_send(signals) is False

    def test_should_send_with_mixed_priorities(self, formatter):
        signals = [
            _make_signal(impact=4, urgency=2),  # priority=8 >= 6
            _make_signal(impact=5, urgency=3),  # priority=15 >= 6
            _make_signal(impact=3, urgency=2),  # priority=6 >= 6
        ]
        assert formatter.should_send(signals) is True

    def test_empty_signals(self, formatter):
        assert formatter.should_send([]) is False


class TestThemeDetection:
    """Test theme detection."""

    def test_tech_theme(self, formatter):
        signals = [
            _make_signal(category="TECH_EVENT", description="upgrade 1"),
            _make_signal(category="TECH_EVENT", description="upgrade 2"),
            _make_signal(category="FINANCIAL", description="tvl event"),
        ]
        result = formatter.format(signals)
        assert "upgrade" in result.lower()

    def test_financial_theme(self, formatter):
        signals = [
            _make_signal(category="REGULATORY", impact=4, urgency=2, description="regulatory action 1"),
            _make_signal(category="REGULATORY", impact=4, urgency=2, description="regulatory action 2"),
            _make_signal(category="TECH_EVENT", description="upgrade"),
        ]
        result = formatter.format(signals)
        assert "Regulatory" in result or "action" in result.lower()

    def test_risk_theme(self, formatter):
        signals = [
            _make_signal(category="RISK_ALERT", impact=4, urgency=2, description="hack 1"),
            _make_signal(category="RISK_ALERT", impact=4, urgency=2, description="hack 2"),
        ]
        result = formatter.format(signals)
        assert "Security" in result or "RISK_ALERT" in result

    def test_no_theme_with_no_signals(self, formatter):
        result = formatter.format([])
        assert "TODAY'S THEME" not in result


class TestHealthFormatting:
    """Test source health formatting."""

    def test_health_all_healthy(self, formatter):
        health = {
            "defillama": {"source_name": "DefiLlama", "status": "healthy", "failures_24h": 0},
            "coingecko": {"source_name": "CoinGecko", "status": "healthy", "failures_24h": 0},
        }
        result = formatter.format([], source_health=health)
        assert "Source health" in result
        assert "2/2 healthy" in result

    def test_health_with_degraded(self, formatter):
        health = {
            "defillama": {"source_name": "DefiLlama", "status": "healthy", "failures_24h": 0},
            "coingecko": {"source_name": "CoinGecko", "status": "degraded", "failures_24h": 3},
        }
        result = formatter.format([], source_health=health)
        assert "1 degraded" in result

    def test_health_with_down(self, formatter):
        health = {
            "defillama": {"source_name": "DefiLlama", "status": "down", "failures_24h": 5},
        }
        result = formatter.format([], source_health=health)
        assert "1 down" in result

    def test_health_shows_issue_details(self, formatter):
        health = {
            "defillama": {"source_name": "DefiLlama", "status": "down", "failures_24h": 5},
        }
        result = formatter.format([], source_health=health)
        assert "defillama" in result.lower()
        assert "down" in result

    def test_no_health_section_when_none(self, formatter):
        result = formatter.format([])
        assert "Source health" not in result
