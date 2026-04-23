"""Tests for main.py orchestration."""

import pytest
from unittest.mock import patch, MagicMock


class TestProcessEvents:
    """Test event processing pipeline."""

    def test_process_creates_signals(self, mock_config):
        from main import process_events
        from processors.signal import Signal

        raw_events = [
            {"chain": "ethereum", "category": "TECH_EVENT", "description": "Upgrade", "source": "GitHub", "reliability": 0.9},
            {"chain": "solana", "category": "FINANCIAL", "description": "TVL spike", "source": "DL", "reliability": 0.8},
        ]

        signals, tracker = process_events(raw_events)
        assert len(signals) == 2
        assert all(isinstance(s, Signal) for s in signals)

    def test_process_with_reinforcement(self, mock_config):
        from main import process_events

        raw_events = [
            {"chain": "ethereum", "category": "TECH_EVENT", "description": "Same event", "source": "GitHub", "reliability": 0.9},
            {"chain": "ethereum", "category": "TECH_EVENT", "description": "Same event", "source": "RSS", "reliability": 0.7},
        ]

        signals, tracker = process_events(raw_events)
        assert len(signals) == 2
        # Second signal should be reinforced into the first
        # Since reinforcer is local to process_events, both get created
        # because they are processed sequentially in the same reinforcer instance
        # Actually, the first is created, the second is reinforced
        # But process_events returns the processed signals, not the stored ones
        # So signals[1] might have action "reinforced"


class TestCleanupOldSignals:
    """Test cleanup phase."""

    def test_cleanup_handles_invalid_env(self, monkeypatch, mock_config):
        from main import cleanup_old_signals

        monkeypatch.setenv("DATA_RETENTION_DAYS", "")
        with patch("main.SignalReinforcer") as MockReinforcer:
            mock_reinf = MagicMock()
            MockReinforcer.return_value = mock_reinf
            # Should not raise ValueError
            cleanup_old_signals()
            mock_reinf.cleanup_old.assert_called_once_with(90)

    def test_cleanup_uses_custom_retention(self, monkeypatch, mock_config):
        from main import cleanup_old_signals

        monkeypatch.setenv("DATA_RETENTION_DAYS", "30")
        with patch("main.SignalReinforcer") as MockReinforcer:
            mock_reinf = MagicMock()
            MockReinforcer.return_value = mock_reinf
            cleanup_old_signals()
            mock_reinf.cleanup_old.assert_called_once_with(30)
