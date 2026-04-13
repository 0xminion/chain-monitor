"""Signal reinforcer — deduplicates via reinforcement model."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from processors.signal import Signal

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage" / "events"


class SignalReinforcer:
    """Manages signal deduplication and reinforcement."""

    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.signals: dict[str, Signal] = {}
        self._load_existing()

    def _load_existing(self):
        """Load existing signals from storage."""
        for path in STORAGE_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                signal = Signal(**data)
                self.signals[signal.id] = signal
            except Exception as e:
                logger.warning(f"Failed to load signal from {path}: {e}")

    def process(self, new_signal: Signal) -> tuple[Signal, str]:
        """Process a new signal. Returns (signal, action) where action is 'created', 'reinforced', or 'echo'."""
        existing = self._find_match(new_signal)

        if existing is None:
            self.signals[new_signal.id] = new_signal
            self._save_signal(new_signal)
            return new_signal, "created"

        if self._is_echo(new_signal, existing):
            return existing, "echo"

        existing.add_activity(
            source=new_signal.activity[0]["source"] if new_signal.activity else "unknown",
            reliability=new_signal.activity[0]["reliability"] if new_signal.activity else 0.7,
            evidence=new_signal.activity[0]["evidence"] if new_signal.activity else new_signal.description,
        )

        if new_signal.trader_context and not existing.trader_context:
            existing.trader_context = new_signal.trader_context

        self._save_signal(existing)
        return existing, "reinforced"

    def _find_match(self, new_signal: Signal) -> Optional[Signal]:
        """Find matching existing signal via text similarity."""
        for existing in self.signals.values():
            if existing.chain != new_signal.chain:
                continue
            if existing.category != new_signal.category:
                continue
            similarity = self._text_similarity(existing.description, new_signal.description)
            if similarity >= 0.7:
                logger.info(f"Match found: '{existing.description[:50]}' ~ '{new_signal.description[:50]}' (sim={similarity:.2f})")
                return existing
        return None

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using word overlap."""
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)  # Jaccard similarity

    def _is_echo(self, new_signal: Signal, existing: Signal) -> bool:
        """Detect if new signal is an echo (re-announcement of known event)."""
        if existing.source_count >= 3 and self._text_similarity(existing.description, new_signal.description) >= 0.9:
            if "conference" in new_signal.description.lower() or "ama" in new_signal.description.lower():
                return True
        return False

    def _save_signal(self, signal: Signal):
        """Save signal to storage."""
        path = STORAGE_DIR / f"{signal.id}.json"
        with open(path, "w") as f:
            json.dump(signal.to_dict(), f, indent=2)

    def get_signals_by_chain(self, chain: str) -> list[Signal]:
        """Get all signals for a chain."""
        return [s for s in self.signals.values() if s.chain == chain]

    def get_high_priority(self, min_score: int = 8) -> list[Signal]:
        """Get signals above priority threshold."""
        return sorted(
            [s for s in self.signals.values() if s.priority_score >= min_score],
            key=lambda s: s.priority_score,
            reverse=True,
        )

    def cleanup_old(self, retention_days: int = 180):
        """Remove signals older than retention period."""
        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        to_remove = []
        for sig_id, signal in self.signals.items():
            try:
                ts = datetime.fromisoformat(signal.detected_at).timestamp()
                if ts < cutoff:
                    to_remove.append(sig_id)
            except (ValueError, TypeError):
                pass
        for sig_id in to_remove:
            del self.signals[sig_id]
            path = STORAGE_DIR / f"{sig_id}.json"
            if path.exists():
                path.unlink()
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} signals older than {retention_days} days")
