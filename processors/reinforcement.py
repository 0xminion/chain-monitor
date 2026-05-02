"""Signal reinforcer — deduplicates via reinforcement model."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from filelock import FileLock

from processors.signal import Signal

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage" / "events"
_LOCK_PATH = STORAGE_DIR / ".reinforcer.lock"


def _clean_description(desc: str) -> str:
    """Strip [Source Name] prefix for comparison."""
    if desc.startswith("["):
        idx = desc.find("]")
        if idx >= 0:
            return desc[idx + 1:].strip().lower()
    return desc.strip().lower()


def _extract_evidence_url(activity: list) -> Optional[str]:
    """Extract URL from signal evidence for dedup comparison."""
    if not activity:
        return None
    evidence = activity[0].get("evidence", {})
    if not isinstance(evidence, dict):
        return None
    for key in ("url", "tweet_url", "html_url", "pr_url", "link", "feed_url"):
        url = evidence.get(key, "")
        if url and url.startswith("http"):
            # Normalize: strip query params and trailing slashes
            url = url.split("?")[0].rstrip("/")
            return url.lower()
    return None


class SignalReinforcer:
    """Manages signal deduplication and reinforcement."""

    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.signals: dict[str, Signal] = {}
        self._url_index: dict[str, str] = {}  # url -> signal_id
        self._load_existing()

    def _load_existing(self):
        """Load existing signals from storage."""
        with FileLock(str(_LOCK_PATH)):
            for path in STORAGE_DIR.glob("*.json"):
                try:
                    with open(path) as f:
                        data = json.load(f)
                    signal = Signal(**data)
                    self.signals[signal.id] = signal
                    # Build URL index
                    url = _extract_evidence_url(signal.activity)
                    if url:
                        self._url_index[url] = signal.id
                except Exception as e:
                    logger.warning(f"Failed to load signal from {path}: {e}")

    def process(self, new_signal: Signal) -> tuple[Signal, str]:
        """Process a new signal. Returns (signal, action) where action is 'created', 'reinforced', or 'echo'."""
        existing = self._find_match(new_signal)

        if existing is None:
            self.signals[new_signal.id] = new_signal
            # Index URL
            url = _extract_evidence_url(new_signal.activity)
            if url:
                self._url_index[url] = new_signal.id
            self._save_signal(new_signal)
            return new_signal, "created"

        if self._is_echo(new_signal, existing):
            return existing, "echo"

        existing.add_activity(
            source=new_signal.activity[0]["source"] if new_signal.activity else "unknown",
            reliability=new_signal.activity[0]["reliability"] if new_signal.activity else 0.7,
            evidence=new_signal.activity[0]["evidence"] if new_signal.activity else new_signal.description,
        )

        # Always update trader_context to the latest (better reasoning on re-runs)
        if new_signal.trader_context:
            existing.trader_context = new_signal.trader_context

        self._save_signal(existing)
        return existing, "reinforced"

    def _find_match(self, new_signal: Signal) -> Optional[Signal]:
        """Find matching existing signal via URL or text similarity."""
        # 1. URL-based match (fastest, most accurate)
        new_url = _extract_evidence_url(new_signal.activity)
        if new_url and new_url in self._url_index:
            existing_id = self._url_index[new_url]
            existing = self.signals.get(existing_id)
            if existing and existing.chain == new_signal.chain:
                logger.info(f"URL match: '{existing.description[:50]}' = '{new_signal.description[:50]}'")
                return existing

        # 2. Text similarity match (using cleaned descriptions)
        for existing in self.signals.values():
            if existing.chain != new_signal.chain:
                continue
            if existing.category != new_signal.category:
                continue
            similarity = self._text_similarity(existing.description, new_signal.description)
            if similarity >= 0.6:
                logger.info(f"Match found: '{existing.description[:50]}' ~ '{new_signal.description[:50]}' (sim={similarity:.2f})")
                return existing
        return None

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using cleaned word overlap (Jaccard)."""
        clean1 = _clean_description(text1)
        clean2 = _clean_description(text2)
        words1 = set(re.findall(r'\w+', clean1))
        words2 = set(re.findall(r'\w+', clean2))
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _is_echo(self, new_signal: Signal, existing: Signal) -> bool:
        """Detect if new signal is an echo (re-announcement of known event)."""
        if existing.source_count >= 3 and self._text_similarity(existing.description, new_signal.description) >= 0.85:
            return True
        # URL echo: same URL, already has 2+ sources
        new_url = _extract_evidence_url(new_signal.activity)
        if new_url and new_url in self._url_index and existing.source_count >= 2:
            return True
        return False

    def _save_signal(self, signal: Signal):
        """Save signal to storage."""
        with FileLock(str(_LOCK_PATH)):
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
            signal = self.signals.pop(sig_id, None)
            # Remove from URL index
            if signal:
                url = _extract_evidence_url(signal.activity)
                if url and url in self._url_index:
                    del self._url_index[url]
            path = STORAGE_DIR / f"{sig_id}.json"
            if path.exists():
                path.unlink()
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} signals older than {retention_days} days")
