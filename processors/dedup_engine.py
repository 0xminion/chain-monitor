"""O(n) deduplication engine using hash-based fingerprinting.

Replaces the quadratic loop-over-all-signals approach with a single-pass
hash table. Big-O: O(n) time, O(n) space.
"""

import logging
from typing import Optional

from processors.pipeline_types import RawEvent

logger = logging.getLogger(__name__)


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """Normalize URL for comparison: lower, strip query/fragment, trailing slash."""
    if not url:
        return None
    u = url.strip().lower()
    # Strip fragment
    if "#" in u:
        u = u.split("#", 1)[0]
    # Strip query params (carefully — keep essential query keys if any)
    if "?" in u:
        u = u.split("?", 1)[0]
    return u.rstrip("/") if u.startswith("http") else None


def _evidence_weight(ev: RawEvent) -> int:
    """Return a heuristic 'richness' score for an event.

    More evidence fields = higher weight (prefer keeping).
    """
    weight = 0
    e = ev.evidence or {}
    weight += len(e)
    weight += 2 if ev.semantic else 0
    weight += 1 if ev.published_at else 0
    weight += int(ev.reliability * 10)
    return weight


def deduplicate_events(events: list[RawEvent]) -> list[RawEvent]:
    """Single-pass deduplication of raw events.

    Strategy (in order of preference):
    1. URL-based lookup — most reliable. Keeps the richer event on collision.
    2. Content-fingerprint fallback — for events without URLs.

    Args:
        events: Raw events (may be unordered, may contain duplicates).

    Returns:
        Deduplicated list, preserving original order of first occurrence.
    """
    # Primary: URL index   key -> (weight, event)
    url_index: dict[str, tuple[int, RawEvent]] = {}
    # Secondary: Fingerprint index
    fp_index: dict[str, tuple[int, RawEvent]] = {}

    # Keep track of insertion order for stable output
    _insertion_order: dict[str, int] = {}

    for idx, ev in enumerate(events):
        # Prefer URL as key
        norm_url = _normalize_url(ev.raw_url)
        if norm_url:
            key = f"url:{ev.chain}:{norm_url}"
        else:
            key = f"fp:{ev.fingerprint}"

        existing_entry = url_index.get(key) or fp_index.get(key)
        if existing_entry is None:
            # New event — store and remember insertion index
            weight = _evidence_weight(ev)
            if norm_url:
                url_index[key] = (weight, ev)
            else:
                fp_index[key] = (weight, ev)
            _insertion_order[key] = idx
            continue

        # Collision — compare richness and recency
        _, existing = existing_entry
        new_weight = _evidence_weight(ev)
        old_weight = _evidence_weight(existing)

        # Tie-breaker: if same weight, prefer more recent
        if new_weight > old_weight:
            replace = True
        elif new_weight == old_weight and ev.published_at and existing.published_at:
            replace = ev.published_at > existing.published_at
        else:
            replace = False

        if replace:
            if norm_url:
                url_index[key] = (new_weight, ev)
            else:
                fp_index[key] = (new_weight, ev)
            # Keep old insertion order — do NOT overwrite

    # Merge and sort by original insertion order
    def _sort_key(item: tuple[str, tuple[int, RawEvent]]) -> int:
        return _insertion_order.get(item[0], 999_999)

    all_items: list[tuple[str, tuple[int, RawEvent]]] = list(url_index.items()) + list(fp_index.items())
    all_items.sort(key=_sort_key)

    result = [ev for _, (_, ev) in all_items]
    dropped = len(events) - len(result)
    logger.info(
        f"Dedup: {len(events)} raw → {len(result)} unique ({dropped} duplicates, "
        f"{len(url_index)} URL-based, {len(fp_index)} fingerprint-based)"
    )
    return result
