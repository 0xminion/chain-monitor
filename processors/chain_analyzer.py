"""Per-chain analyzer — deterministic. Groups scored signals into ChainDigest.

No external LLM calls. The running agent reads ChainDigests and writes prose.
"""

import logging
from collections import Counter

from processors.pipeline_types import ChainDigest
from processors.signal import Signal
from config.loader import get_chain, get_active_chains

logger = logging.getLogger(__name__)


def _chain_cfg(chain: str) -> tuple[int, str]:
    cfg = get_chain(chain) or {}
    return int(cfg.get("tier", 3)), str(cfg.get("category", "unknown"))


async def analyze_chain(chain: str, signals: list[Signal]) -> ChainDigest:
    """Build a ChainDigest from scored signals using deterministic heuristics.

    Args:
        chain: Chain name.
        signals: Scored and reinforced signals for this chain.

    Returns:
        ChainDigest with real metrics and raw key-event data for the agent.
    """
    tier, category = _chain_cfg(chain)

    if not signals:
        return ChainDigest(
            chain=chain,
            chain_tier=tier,
            chain_category=category,
            summary="",
            key_events=[],
            priority_score=0,
            dominant_topic="Quiet",
            sources_seen=0,
            event_count=0,
            confidence=0.0,
        )

    # Sort by priority desc
    signals = sorted(signals, key=lambda s: -s.priority_score)

    event_count = len(signals)
    sources_seen = len(set(
        a.get("source", "unknown")
        for s in signals
        for a in (s.activity if isinstance(s.activity, list) else [])
    ))
    avg_reliability = (
        sum(
            (s.activity[0].get("reliability", 0.7) if s.activity and isinstance(s.activity[0], dict) else 0.7)
            for s in signals
        ) / len(signals) if signals else 0.0
    )

    # Priority score: top signal score + diversity bonus
    top_score = signals[0].priority_score if signals else 0
    source_bonus = min(3, max(0, sources_seen - 1))
    priority_score = min(15, top_score + source_bonus)

    # Dominant topic: most common category among priority ≥ 3 signals
    high_prio = [s for s in signals if s.priority_score >= 3]
    if high_prio:
        dominant_cat = Counter(s.category for s in high_prio).most_common(1)[0][0]
        dominant_topic = dominant_cat.replace("_", " ").title()
    else:
        dominant_topic = "General Activity"

    # Key events: top 5 signals with full metadata
    key_events = []
    for s in signals[:5]:
        # Search ALL activities for a URL, not just activity[0]
        url = ""
        for act in (s.activity if isinstance(s.activity, list) else []):
            if not isinstance(act, dict):
                continue
            evidence = act.get("evidence", "")
            if isinstance(evidence, dict):
                for key in ("url", "html_url", "pr_url", "link", "feed_url", "tweet_url"):
                    val = evidence.get(key)
                    if val and isinstance(val, str) and val.startswith("http"):
                        url = val
                        break
            elif isinstance(evidence, str) and evidence.startswith("http"):
                url = evidence
            if url:
                break
        if not url:
            # Fallback: try to regex a URL out of the description
            import re
            m = re.search(r"https?://[^\s\"]+", s.description)
            if m:
                url = m.group(0).rstrip(".,;:)")

        key_events.append({
            "topic": s.description[:120],
            "category": s.category,
            "sources": list(set(
                a.get("source", "unknown")
                for a in (s.activity if isinstance(s.activity, list) else [])
            )),
            "priority": s.priority_score,
            "confidence": round(s.composite_confidence, 2),
            "detail": s.description[:300],
            "why_it_matters": (s.trader_context or "")[:200],
            "url": url,
        })

    return ChainDigest(
        chain=chain,
        chain_tier=tier,
        chain_category=category,
        summary="",  # agent synthesizes
        key_events=key_events,
        priority_score=priority_score,
        dominant_topic=dominant_topic,
        sources_seen=sources_seen,
        event_count=event_count,
        confidence=round(avg_reliability, 2),
    )


async def analyze_all_chains(
    signals_by_chain: dict[str, list[Signal]],
    client=None,  # unused — kept for backward compat
    max_concurrent: int | None = None,
) -> list[ChainDigest]:
    """Analyze all chains deterministically.

    Args:
        signals_by_chain: {chain_name: [Signal, ...]}
        client: Ignored. Kept for API compat with old LLM-based callers.
        max_concurrent: Ignored. Kept for API compat.

    Returns:
        List of ChainDigest objects (one per configured chain, even if empty).
    """
    digests: list[ChainDigest] = []

    # Process chains that have signals
    for chain, sigs in signals_by_chain.items():
        digests.append(await analyze_chain(chain, sigs))

    # Ensure every configured chain has an entry (even empty)
    seen_chains = {d.chain for d in digests}
    for chain_name in get_active_chains():
        if chain_name not in seen_chains:
            digests.append(await analyze_chain(chain_name, []))

    logger.info(
        f"Chain analysis complete: {len(digests)} chains, "
        f"{sum(1 for d in digests if d.priority_score > 0)} with activity"
    )
    return digests
