"""Tests for Signal data model."""

import pytest
from datetime import datetime, timezone

from processors.signal import Signal, ActivityEntry


class TestSignalCreation:
    """Test signal creation with defaults."""

    def test_create_minimal_signal(self):
        sig = Signal(
            id="test-123",
            chain="ethereum",
            category="TECH_EVENT",
            description="Test event",
        )
        assert sig.chain == "ethereum"
        assert sig.category == "TECH_EVENT"
        assert sig.description == "Test event"
        assert sig.impact == 1
        assert sig.urgency == 1
        assert sig.source_count == 1
        assert sig.composite_confidence == 0.0
        assert sig.has_official_source is False
        assert sig.secondary_tags == []
        assert sig.activity == []

    def test_post_init_sets_detected_at(self):
        sig = Signal(id="x", chain="eth", category="TECH", description="d")
        assert sig.detected_at != ""
        # Should be valid ISO format
        datetime.fromisoformat(sig.detected_at)

    def test_post_init_sets_reinforced_at(self):
        sig = Signal(id="x", chain="eth", category="TECH", description="d")
        assert sig.reinforced_at == sig.detected_at

    def test_post_init_generates_id_when_empty(self):
        sig = Signal(id="", chain="ethereum", category="TECH_EVENT", description="test")
        assert sig.id != ""
        assert len(sig.id) == 16

    def test_post_init_priority_score(self):
        sig = Signal(id="x", chain="e", category="T", description="d", impact=3, urgency=2, priority_score=0)
        # priority_score=0 should be preserved (legitimate score), not recalculated
        assert sig.priority_score == 0
        # When None, it auto-calculates
        sig2 = Signal(id="x", chain="e", category="T", description="d", impact=3, urgency=2, priority_score=None)
        assert sig2.priority_score == 6

    def test_signal_with_all_fields(self):
        sig = Signal(
            id="full",
            chain="solana",
            category="FINANCIAL",
            description="Full signal",
            trader_context="Watch SOL price",
            impact=4,
            urgency=2,
            priority_score=8,
            detected_at="2026-01-01T00:00:00+00:00",
            source_count=3,
            composite_confidence=0.85,
            has_official_source=True,
            secondary_tags=["defi"],
        )
        assert sig.priority_score == 8
        assert sig.has_official_source is True
        assert "defi" in sig.secondary_tags


class TestGenerateId:
    """Test generate_id determinism."""

    def test_deterministic(self):
        id1 = Signal.generate_id("ethereum", "TECH_EVENT", "upgrade v1")
        id2 = Signal.generate_id("ethereum", "TECH_EVENT", "upgrade v1")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = Signal.generate_id("ethereum", "TECH_EVENT", "upgrade v1")
        id2 = Signal.generate_id("solana", "TECH_EVENT", "upgrade v1")
        id3 = Signal.generate_id("ethereum", "FINANCIAL", "upgrade v1")
        id4 = Signal.generate_id("ethereum", "TECH_EVENT", "different desc")
        assert id1 != id2
        assert id1 != id3
        assert id1 != id4

    def test_id_is_16_chars(self):
        result = Signal.generate_id("chain", "CAT", "desc")
        assert len(result) == 16

    def test_truncates_description_at_100(self):
        short_desc = "a" * 50
        long_desc = "a" * 100 + "EXTRA"
        id1 = Signal.generate_id("c", "cat", short_desc)
        id2 = Signal.generate_id("c", "cat", long_desc)
        # 100-char prefix should produce different id than 50-char
        # but first 100 of long_desc is all 'a' * 100
        id3 = Signal.generate_id("c", "cat", "a" * 100)
        assert id2 == id3


class TestAddActivity:
    """Test add_activity and confidence recalculation."""

    def test_add_single_activity(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.add_activity("source1", 0.8, "evidence1")
        assert sig.source_count == 1
        assert len(sig.activity) == 1
        assert sig.activity[0]["source"] == "source1"
        assert sig.activity[0]["reliability"] == 0.8

    def test_add_multiple_activities(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.add_activity("s1", 0.8, "e1")
        sig.add_activity("s2", 0.9, "e2")
        assert sig.source_count == 2
        assert len(sig.activity) == 2

    def test_confidence_with_one_source(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.add_activity("s1", 0.8, "e1")
        # multiplier = 1.0 for single source
        assert sig.composite_confidence == pytest.approx(0.8)

    def test_confidence_with_two_sources(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.add_activity("s1", 0.7, "e1")
        sig.add_activity("s2", 0.8, "e2")
        # multiplier = 1.15 for 2 sources; max reliability = 0.8
        assert sig.composite_confidence == pytest.approx(min(0.95, 0.8 * 1.15))

    def test_confidence_with_three_sources(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.add_activity("s1", 0.7, "e1")
        sig.add_activity("s2", 0.8, "e2")
        sig.add_activity("s3", 0.6, "e3")
        # multiplier = 1.25 for 3+ sources; max reliability = 0.8
        assert sig.composite_confidence == pytest.approx(min(0.95, 0.8 * 1.25))

    def test_confidence_capped_at_095(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.has_official_source = True
        sig.add_activity("s1", 0.9, "e1")
        sig.add_activity("s2", 0.9, "e2")
        sig.add_activity("s3", 0.9, "e3")
        # 0.9 * 1.25 + 0.05 = 1.175 -> capped at 0.95
        assert sig.composite_confidence == 0.95

    def test_confidence_with_official_source(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        sig.has_official_source = True
        sig.add_activity("s1", 0.8, "e1")
        # multiplier = 1.0 + 0.05 = 1.05
        assert sig.composite_confidence == pytest.approx(min(0.95, 0.8 * 1.05))

    def test_reinforced_at_updates(self):
        sig = Signal(id="x", chain="e", category="T", description="d")
        original = sig.reinforced_at
        sig.add_activity("s1", 0.8, "e1")
        assert sig.reinforced_at != original


class TestPriorityScore:
    """Test priority_score calculation."""

    def test_priority_score_calculation(self):
        sig = Signal(id="x", chain="e", category="T", description="d", impact=3, urgency=2, priority_score=6)
        assert sig.priority_score == 6

    def test_priority_score_from_to_dict(self):
        sig = Signal(id="x", chain="e", category="T", description="d", impact=4, urgency=3, priority_score=12)
        d = sig.to_dict()
        assert d["priority_score"] == 12

    def test_priority_score_recalculated_in_to_dict(self):
        """to_dict always recomputes priority_score."""
        sig = Signal(id="x", chain="e", category="T", description="d", impact=5, urgency=3, priority_score=0)
        d = sig.to_dict()
        assert d["priority_score"] == 15


class TestToTelegram:
    """Test to_telegram formatting."""

    def test_basic_format(self, make_signal):
        sig = make_signal(chain="ethereum", category="TECH_EVENT", description="Test event", impact=2, urgency=1)
        text = sig.to_telegram()
        assert "Ethereum" in text
        assert "Test event" in text
        assert "TECH_EVENT" in text
        assert "Impact: 2" in text
        assert "MODERATE" in text

    def test_impact_labels(self, make_signal):
        labels = {1: "LOW", 2: "MODERATE", 3: "NOTABLE", 4: "HIGH", 5: "CRITICAL"}
        for impact, label in labels.items():
            sig = make_signal(impact=impact)
            text = sig.to_telegram()
            assert label in text

    def test_trader_context_included(self, make_signal):
        sig = make_signal(trader_context="Watch gas fees")
        text = sig.to_telegram()
        assert "So what: Watch gas fees" in text

    def test_trader_context_omitted_when_empty(self, make_signal):
        sig = make_signal(trader_context="")
        text = sig.to_telegram()
        assert "So what" not in text

    def test_reinforcement_indicator(self, make_signal):
        sig = make_signal()
        sig.add_activity("s2", 0.7, "e2")
        text = sig.to_telegram()
        assert "2x" in text

    def test_sources_listed(self, make_signal):
        sig = make_signal(source="GitHub")
        text = sig.to_telegram()
        assert "GitHub" in text
