"""Tests for SignalReinforcer."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from processors.reinforcement import SignalReinforcer, _extract_evidence_url, _clean_description
from processors.signal import Signal


class TestExtractEvidenceUrl:
    """Test URL extraction from signal activity."""

    def test_extracts_link(self):
        activity = [{"evidence": {"link": "https://example.com/article"}}]
        assert _extract_evidence_url(activity) == "https://example.com/article"

    def test_strips_query_params(self):
        activity = [{"evidence": {"link": "https://example.com/article?utm_source=x"}}]
        assert _extract_evidence_url(activity) == "https://example.com/article"

    def test_returns_none_when_no_url(self):
        activity = [{"evidence": {"title": "No URL here"}}]
        assert _extract_evidence_url(activity) is None

    def test_returns_none_for_empty_activity(self):
        assert _extract_evidence_url([]) is None


class TestCleanDescription:
    """Test description cleaning for comparison."""

    def test_strips_source_prefix(self):
        assert _clean_description("[CoinDesk] Bitcoin rises") == "bitcoin rises"

    def test_lowercases(self):
        assert _clean_description("ETHEREUM UPGRADE") == "ethereum upgrade"


class TestSignalReinforcer:
    """Test deduplication and reinforcement logic."""

    @pytest.fixture
    def reinforcer(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "processors.reinforcement.STORAGE_DIR", tmp_path / "events"
        )
        monkeypatch.setattr(
            "processors.reinforcement._LOCK_PATH", tmp_path / "events" / ".reinforcer.lock"
        )
        return SignalReinforcer()

    def _make_signal(self, chain="ethereum", category="TECH_EVENT", description="test", url=None):
        sig = Signal(
            id=Signal.generate_id(chain, category, description),
            chain=chain,
            category=category,
            description=description,
            impact=2,
            urgency=1,
            priority_score=2,
        )
        if url:
            sig.add_activity("test", 0.8, {"link": url})
        else:
            sig.add_activity("test", 0.8, description)
        return sig

    def test_created_for_new_signal(self, reinforcer):
        sig = self._make_signal(description="New upgrade")
        result, action = reinforcer.process(sig)
        assert action == "created"
        assert result.id == sig.id

    def test_reinforced_for_similar_signal(self, reinforcer):
        sig1 = self._make_signal(description="Ethereum mainnet upgrade live")
        reinforcer.process(sig1)

        sig2 = self._make_signal(description="Ethereum mainnet upgrade goes live")
        result, action = reinforcer.process(sig2)
        assert action == "reinforced"
        assert result.source_count == 2

    def test_echo_for_high_source_count(self, reinforcer):
        sig1 = self._make_signal(description="Ethereum mainnet upgrade live")
        reinforcer.process(sig1)

        # Reinforce twice more with very similar descriptions
        for i in range(2):
            s = self._make_signal(description="Ethereum mainnet upgrade live")
            reinforcer.process(s)

        # 4th time should be echo (source_count >= 3 + high similarity)
        sig4 = self._make_signal(description="Ethereum mainnet upgrade live")
        result, action = reinforcer.process(sig4)
        assert action == "echo"

    def test_url_match_cross_description(self, reinforcer):
        sig1 = self._make_signal(description="Article A", url="https://example.com/news/1")
        reinforcer.process(sig1)

        sig2 = self._make_signal(description="Different description", url="https://example.com/news/1")
        result, action = reinforcer.process(sig2)
        assert action == "reinforced"

    def test_no_match_across_chains(self, reinforcer):
        sig1 = self._make_signal(chain="ethereum", description="Upgrade live")
        reinforcer.process(sig1)

        sig2 = self._make_signal(chain="solana", description="Upgrade live")
        result, action = reinforcer.process(sig2)
        assert action == "created"

    def test_persists_to_disk(self, reinforcer, tmp_path):
        sig = self._make_signal(description="Persisted signal")
        reinforcer.process(sig)

        path = tmp_path / "events" / f"{sig.id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["description"] == "Persisted signal"

    def test_loads_from_disk(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "processors.reinforcement.STORAGE_DIR", tmp_path / "events"
        )
        monkeypatch.setattr(
            "processors.reinforcement._LOCK_PATH", tmp_path / "events" / ".reinforcer.lock"
        )
        (tmp_path / "events").mkdir(parents=True, exist_ok=True)

        sig = Signal(
            id="abc123",
            chain="ethereum",
            category="TECH_EVENT",
            description="Loaded from disk",
            impact=2,
            urgency=1,
            priority_score=2,
        )
        sig.add_activity("test", 0.8, "evidence")
        path = tmp_path / "events" / "abc123.json"
        path.write_text(json.dumps(sig.to_dict()))

        reinforcer = SignalReinforcer()
        assert "abc123" in reinforcer.signals
        assert reinforcer.signals["abc123"].description == "Loaded from disk"

    def test_cleanup_old(self, reinforcer):
        sig = self._make_signal(description="Old signal")
        # Manually set detected_at to 200 days ago
        sig.detected_at = "2025-10-01T00:00:00+00:00"
        reinforcer.process(sig)

        reinforcer.cleanup_old(retention_days=90)
        assert sig.id not in reinforcer.signals
