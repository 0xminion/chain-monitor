"""Tests for SignalReinforcer."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from processors.signal import Signal
from processors.reinforcement import SignalReinforcer


@pytest.fixture
def reinforcer(tmp_path, monkeypatch, mock_config):
    """Create a reinforcer with a temp storage dir."""
    import processors.reinforcement as rein_mod
    monkeypatch.setattr(rein_mod, "STORAGE_DIR", tmp_path / "events")
    return SignalReinforcer()


def _make_signal(chain="ethereum", category="TECH_EVENT", description="test event", source="test", reliability=0.8):
    sig = Signal(
        id=Signal.generate_id(chain, category, description),
        chain=chain,
        category=category,
        description=description,
        impact=2,
        urgency=1,
        priority_score=2,
    )
    sig.add_activity(source, reliability, description)
    return sig


class TestNewSignalCreation:
    """Test creating new signals."""

    def test_new_signal_returns_created(self, reinforcer):
        sig = _make_signal()
        result, action = reinforcer.process(sig)
        assert action == "created"
        assert result.id == sig.id

    def test_new_signal_stored(self, reinforcer):
        sig = _make_signal(chain="solana", description="unique event")
        reinforcer.process(sig)
        assert sig.id in reinforcer.signals

    def test_new_signal_saved_to_disk(self, reinforcer, tmp_path, monkeypatch):
        import processors.reinforcement as rein_mod
        storage = tmp_path / "events"
        monkeypatch.setattr(rein_mod, "STORAGE_DIR", storage)
        r = SignalReinforcer()
        sig = _make_signal(chain="bitcoin", description="new save test")
        r.process(sig)
        assert (storage / f"{sig.id}.json").exists()


class TestReinforcement:
    """Test signal reinforcement (same chain + category + similar description)."""

    def test_similar_signal_reinforced(self, reinforcer):
        sig1 = _make_signal(chain="ethereum", category="TECH_EVENT", description="Ethereum mainnet upgrade scheduled for next week")
        sig2 = _make_signal(chain="ethereum", category="TECH_EVENT", description="Ethereum mainnet upgrade planned for next week")
        reinforcer.process(sig1)
        result, action = reinforcer.process(sig2)
        assert action == "reinforced"
        assert result.source_count == 2

    def test_different_chain_not_reinforced(self, reinforcer):
        sig1 = _make_signal(chain="ethereum", description="upgrade event")
        sig2 = _make_signal(chain="solana", description="upgrade event")
        reinforcer.process(sig1)
        _, action = reinforcer.process(sig2)
        assert action == "created"

    def test_different_category_not_reinforced(self, reinforcer):
        sig1 = _make_signal(chain="ethereum", category="TECH_EVENT", description="upgrade event")
        sig2 = _make_signal(chain="ethereum", category="FINANCIAL", description="upgrade event")
        reinforcer.process(sig1)
        _, action = reinforcer.process(sig2)
        assert action == "created"

    def test_reinforcement_adds_activity(self, reinforcer):
        sig1 = _make_signal(chain="ethereum", description="Ethereum upgrade Pectra live")
        sig2 = _make_signal(chain="ethereum", description="Ethereum upgrade Pectra live now")
        reinforcer.process(sig1)
        result, _ = reinforcer.process(sig2)
        assert result.source_count == 2

    def test_reinforcement_updates_trader_context(self, reinforcer):
        sig1 = _make_signal(chain="ethereum", description="Ethereum upgrade Pectra live")
        sig1.trader_context = ""
        sig2 = _make_signal(chain="ethereum", description="Ethereum upgrade Pectra live now")
        sig2.trader_context = "Watch gas fees"
        reinforcer.process(sig1)
        result, _ = reinforcer.process(sig2)
        assert result.trader_context == "Watch gas fees"


class TestEchoDetection:
    """Test echo detection."""

    def test_echo_detected_for_repeated_conference(self, reinforcer):
        # First, create and reinforce to get source_count >= 3
        desc = "Vitalik speaking at conference event"
        sig1 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        reinforcer.process(sig1)

        # Reinforce twice more to get source_count to 3
        sig2 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        reinforcer.process(sig2)
        sig3 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        result, action = reinforcer.process(sig3)
        assert result.source_count == 3

        # Now an echo (highly similar + conference keyword)
        sig4 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        _, action = reinforcer.process(sig4)
        assert action == "echo"

    def test_not_echo_with_low_source_count(self, reinforcer):
        desc = "conference talk happening"
        sig1 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        reinforcer.process(sig1)
        sig2 = _make_signal(chain="ethereum", category="VISIBILITY", description=desc)
        _, action = reinforcer.process(sig2)
        # source_count only 2, so not an echo
        assert action == "reinforced"


class TestTextSimilarity:
    """Test Jaccard text similarity."""

    def test_identical_texts(self, reinforcer):
        assert reinforcer._text_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self, reinforcer):
        assert reinforcer._text_similarity("abc def", "xyz uvw") == 0.0

    def test_partial_overlap(self, reinforcer):
        sim = reinforcer._text_similarity("ethereum upgrade scheduled", "ethereum upgrade planned")
        # words: {ethereum, upgrade, scheduled} vs {ethereum, upgrade, planned}
        # intersection=2, union=4, sim=0.5
        assert sim == pytest.approx(0.5)

    def test_empty_string(self, reinforcer):
        assert reinforcer._text_similarity("", "hello") == 0.0
        assert reinforcer._text_similarity("hello", "") == 0.0
        assert reinforcer._text_similarity("", "") == 0.0

    def test_case_insensitive(self, reinforcer):
        assert reinforcer._text_similarity("Hello World", "hello world") == 1.0


class TestCleanupOld:
    """Test cleanup_old."""

    def test_cleanup_removes_old_signals(self, reinforcer):
        old_sig = _make_signal(chain="ethereum", description="old event")
        # Backdate the signal
        old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        old_sig.detected_at = old_date
        reinforcer.process(old_sig)

        new_sig = _make_signal(chain="solana", description="new event")
        reinforcer.process(new_sig)

        reinforcer.cleanup_old(retention_days=180)
        assert old_sig.id not in reinforcer.signals
        assert new_sig.id in reinforcer.signals

    def test_cleanup_keeps_recent_signals(self, reinforcer):
        sig = _make_signal(chain="ethereum", description="recent event")
        reinforcer.process(sig)
        reinforcer.cleanup_old(retention_days=180)
        assert sig.id in reinforcer.signals


class TestGetSignals:
    """Test get_signals_by_chain and get_high_priority."""

    def test_get_signals_by_chain(self, reinforcer):
        s1 = _make_signal(chain="ethereum", description="eth event 1")
        s2 = _make_signal(chain="solana", description="sol event 1")
        s3 = _make_signal(chain="ethereum", description="eth event 2")
        reinforcer.process(s1)
        reinforcer.process(s2)
        reinforcer.process(s3)
        eth_signals = reinforcer.get_signals_by_chain("ethereum")
        assert len(eth_signals) == 2

    def test_get_high_priority(self, reinforcer):
        s1 = _make_signal(chain="ethereum", description="low priority")
        s1.priority_score = 3
        s2 = _make_signal(chain="ethereum", description="high priority")
        s2.priority_score = 10
        s3 = _make_signal(chain="ethereum", description="medium priority")
        s3.priority_score = 8
        reinforcer.process(s1)
        reinforcer.process(s2)
        reinforcer.process(s3)
        high = reinforcer.get_high_priority(min_score=8)
        assert len(high) == 2
        assert high[0].priority_score >= high[1].priority_score
