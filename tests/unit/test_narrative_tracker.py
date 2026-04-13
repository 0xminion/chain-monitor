"""Tests for NarrativeTracker."""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

from processors.narrative_tracker import NarrativeTracker
from processors.signal import Signal


@pytest.fixture
def tracker(tmp_path, monkeypatch, mock_config):
    """Create a tracker with temp storage."""
    import processors.narrative_tracker as nt_mod
    monkeypatch.setattr(nt_mod, "NARRATIVE_DIR", tmp_path / "narratives")
    return NarrativeTracker()


def _make_signal(chain="ethereum", description="test", trader_context=""):
    return Signal(
        id=Signal.generate_id(chain, "TECH_EVENT", description),
        chain=chain,
        category="TECH_EVENT",
        description=description,
        trader_context=trader_context,
        impact=2,
        urgency=1,
        priority_score=2,
    )


class TestClassifySignal:
    """Test signal classification by keywords."""

    def test_ai_narrative(self, tracker):
        sig = _make_signal(description="New AI agent framework launched")
        narratives = tracker.classify_signal(sig)
        assert "ai_agents" in narratives

    def test_defi_narrative(self, tracker):
        sig = _make_signal(description="New lending protocol launched with yield farming")
        narratives = tracker.classify_signal(sig)
        assert "defi" in narratives

    def test_l2_narrative(self, tracker):
        sig = _make_signal(description="New rollup sequencer bridge deployed")
        narratives = tracker.classify_signal(sig)
        assert "l2_infrastructure" in narratives

    def test_multiple_narratives(self, tracker):
        sig = _make_signal(description="AI agent for DeFi yield optimization using LLM")
        narratives = tracker.classify_signal(sig)
        assert "ai_agents" in narratives
        assert "defi" in narratives

    def test_no_match_uncategorized(self, tracker):
        sig = _make_signal(description="Something completely unrelated happened")
        narratives = tracker.classify_signal(sig)
        assert narratives == ["uncategorized"]

    def test_trader_context_also_searched(self, tracker):
        sig = _make_signal(
            description="Event happened",
            trader_context="Watch for AI agent integrations with liquidity pools"
        )
        narratives = tracker.classify_signal(sig)
        assert "ai_agents" in narratives or "defi" in narratives


class TestRecordSignal:
    """Test signal recording."""

    def test_record_increments_count(self, tracker):
        sig = _make_signal(description="AI agent framework update")
        tracker.record_signal(sig)
        week_key = tracker._get_week_key()
        assert tracker.weekly_counts[week_key].get("ai_agents", 0) == 1

    def test_record_multiple_signals(self, tracker):
        sig1 = _make_signal(description="AI agent update 1")
        sig2 = _make_signal(description="AI agent update 2")
        tracker.record_signal(sig1)
        tracker.record_signal(sig2)
        week_key = tracker._get_week_key()
        assert tracker.weekly_counts[week_key].get("ai_agents", 0) == 2


class TestVelocity:
    """Test velocity calculation."""

    def test_velocity_empty(self, tracker):
        velocity = tracker.get_velocity()
        assert velocity == {}

    def test_velocity_new_narrative(self, tracker):
        # Manually set up weekly counts
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)
        prior_week = tracker._get_week_key(now - timedelta(weeks=1))

        tracker.weekly_counts[current_week] = defaultdict(int, {"ai_agents": 5})
        tracker.weekly_counts[prior_week] = defaultdict(int, {"ai_agents": 0})

        velocity = tracker.get_velocity()
        assert "ai_agents" in velocity
        assert velocity["ai_agents"]["current"] == 5
        assert velocity["ai_agents"]["trend"] == "\U0001f4c8 accelerating"

    def test_velocity_accelerating(self, tracker):
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)

        tracker.weekly_counts[current_week] = defaultdict(int, {"defi": 10})
        # Prior 3 weeks average = 2, so 10 is 400% increase
        for i in range(1, 4):
            wk = tracker._get_week_key(now - timedelta(weeks=i))
            tracker.weekly_counts[wk] = defaultdict(int, {"defi": 2})

        velocity = tracker.get_velocity()
        assert velocity["defi"]["pct_change"] > 50
        assert "accelerating" in velocity["defi"]["trend"]

    def test_velocity_fading(self, tracker):
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)

        tracker.weekly_counts[current_week] = defaultdict(int, {"defi": 1})
        for i in range(1, 4):
            wk = tracker._get_week_key(now - timedelta(weeks=i))
            tracker.weekly_counts[wk] = defaultdict(int, {"defi": 10})

        velocity = tracker.get_velocity()
        assert velocity["defi"]["pct_change"] < -30
        assert "fading" in velocity["defi"]["trend"]

    def test_velocity_steady(self, tracker):
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)

        tracker.weekly_counts[current_week] = defaultdict(int, {"defi": 5})
        for i in range(1, 4):
            wk = tracker._get_week_key(now - timedelta(weeks=i))
            tracker.weekly_counts[wk] = defaultdict(int, {"defi": 5})

        velocity = tracker.get_velocity()
        assert "steady" in velocity["defi"]["trend"]


class TestConvergence:
    """Test convergence detection."""

    def test_no_convergence(self, tracker):
        flags = tracker.get_convergence_flags()
        assert flags == []

    def test_convergence_detected(self, tracker):
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)

        # High acceleration triggers convergence
        tracker.weekly_counts[current_week] = defaultdict(int, {"ai_agents": 20})
        for i in range(1, 4):
            wk = tracker._get_week_key(now - timedelta(weeks=i))
            tracker.weekly_counts[wk] = defaultdict(int, {"ai_agents": 2})

        flags = tracker.get_convergence_flags()
        assert len(flags) > 0
        assert flags[0]["narrative"] == "ai_agents"

    def test_convergence_sorted_by_velocity(self, tracker):
        now = datetime.now(timezone.utc)
        current_week = tracker._get_week_key(now)

        tracker.weekly_counts[current_week] = defaultdict(int, {"ai_agents": 20, "defi": 30})
        for i in range(1, 4):
            wk = tracker._get_week_key(now - timedelta(weeks=i))
            tracker.weekly_counts[wk] = defaultdict(int, {"ai_agents": 2, "defi": 2})

        flags = tracker.get_convergence_flags()
        if len(flags) >= 2:
            assert flags[0]["velocity"] >= flags[1]["velocity"]


class TestScorecard:
    """Test scorecard generation."""

    def test_scorecard_empty(self, tracker):
        scorecard = tracker.get_scorecard()
        assert scorecard == {}

    def test_scorecard_with_data(self, tracker):
        now = datetime.now(timezone.utc)
        weeks = [tracker._get_week_key(now - timedelta(weeks=i)) for i in range(8)]

        tracker.weekly_counts[weeks[-1]] = defaultdict(int, {"ai_agents": 2})
        tracker.weekly_counts[weeks[0]] = defaultdict(int, {"ai_agents": 10})

        scorecard = tracker.get_scorecard()
        assert "ai_agents" in scorecard
        assert scorecard["ai_agents"]["current"] == 10
        assert scorecard["ai_agents"]["first_week"] == 2

    def test_scorecard_still_early(self, tracker):
        now = datetime.now(timezone.utc)
        weeks = [tracker._get_week_key(now - timedelta(weeks=i)) for i in range(8)]

        tracker.weekly_counts[weeks[-1]] = defaultdict(int, {"ai_agents": 2})
        tracker.weekly_counts[weeks[0]] = defaultdict(int, {"ai_agents": 10})

        scorecard = tracker.get_scorecard()
        assert scorecard["ai_agents"]["entry_signal"] == "\u2713 Still early"

    def test_scorecard_mainstream(self, tracker):
        now = datetime.now(timezone.utc)
        weeks = [tracker._get_week_key(now - timedelta(weeks=i)) for i in range(8)]

        tracker.weekly_counts[weeks[-1]] = defaultdict(int, {"defi": 5})
        tracker.weekly_counts[weeks[0]] = defaultdict(int, {"defi": 20})

        scorecard = tracker.get_scorecard()
        assert scorecard["defi"]["entry_signal"] == "Already mainstream"

    def test_scorecard_fading(self, tracker):
        now = datetime.now(timezone.utc)
        weeks = [tracker._get_week_key(now - timedelta(weeks=i)) for i in range(8)]

        tracker.weekly_counts[weeks[-1]] = defaultdict(int, {"l2_infrastructure": 10})
        tracker.weekly_counts[weeks[0]] = defaultdict(int, {"l2_infrastructure": 3})

        scorecard = tracker.get_scorecard()
        assert scorecard["l2_infrastructure"]["entry_signal"] == "Fading"
