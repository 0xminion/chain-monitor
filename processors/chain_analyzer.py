"""Per-chain event grouper — agent-native.

Groups raw events by chain and emits a ChainDigest where key_events are the
raw, unmerged events. The running agent does the merging, summarization,
narrative synthesis, and priority scoring.

No heuristics merged here. The agent is the brain.
"""

import asyncio
import logging
from processors.pipeline_types import RawEvent, ChainDigest
from config.loader import get_chain

logger = logging.getLogger(__name__)


def _chain_cfg(chain: str) -> tuple[int, str]:
    cfg = get_chain(chain) or {}
    return int(cfg.get("tier", 3)), str(cfg.get("category", "unknown"))


async def analyze_chain(chain: str, events: list[RawEvent], client=None) -> ChainDigest:
    """Group events into a ChainDigest for agent review.

    key_events are the raw, unmerged events. The agent merges and scores them.
    summary, priority_score, and dominant_topic are stubs awaiting agent input.
    """
    tier, category = _chain_cfg(chain)

    if not events:
        return ChainDigest(
            chain=chain, chain_tier=tier, chain_category=category,
            summary="No signals collected.",
            key_events=[],
            priority_score=0, dominant_topic="Quiet",
            sources_seen=0, event_count=0, confidence=1.0,
        )

    source_count = len(set(e.source for e in events if e.source))
    event_count = len(events)

    # Build raw key_events from each event (agent merges + deduplicates)
    key_events = []
    for e in events:
        key_events.append({
            "topic": e.description[:120] if e.description else "Event",
            "category": e.category,
            "subcategory": e.subcategory,
            "source": e.source,
            "url": e.raw_url,
            "detail": e.description[:300],
            "reliability": e.reliability,
            "evidence": e.evidence,
            "published_at": e.published_at.isoformat() if e.published_at else None,
        })

    return ChainDigest(
        chain=chain, chain_tier=tier, chain_category=category,
        summary="",  # agent synthesizes this
        key_events=key_events,
        priority_score=0,  # agent assigns
        dominant_topic="",  # agent assigns
        sources_seen=source_count,
        event_count=event_count,
        confidence=0.0,  # agent assigns
    )


async def analyze_all_chains(events_by_chain: dict[str, list[RawEvent]], client=None, max_concurrent: int = 5) -> list[ChainDigest]:
    logger.info(f"[chain_analyzer] Processing {len(events_by_chain)} chains (agent-native)")
    digests = []
    for chain, events in events_by_chain.items():
        digests.append(await analyze_chain(chain, events, client))
    return digests
