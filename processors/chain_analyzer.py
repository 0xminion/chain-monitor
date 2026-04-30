"""Per-chain semantic analyzer — agent-native heuristic synthesis.

For each chain, batches all collected events and uses deterministic heuristics to:
  1. Merge related signals into coherent observations
  2. Classify each observation
  3. Assign chain-level priority score
  4. Generate narrative summary explaining WHY things matter

Fully agent-native: no LLM calls, no external API keys needed.
"""

import asyncio
import logging
from typing import Optional

from processors.pipeline_types import RawEvent, ChainDigest
from config.loader import get_chain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity weight table (used for scoring)
# ---------------------------------------------------------------------------

CATEGORY_PRIORITY = {
    "RISK_ALERT": 15,
    "REGULATORY": 12,
    "FINANCIAL": 10,
    "PARTNERSHIP": 7,
    "TECH_EVENT": 6,
    "VISIBILITY": 3,
    "NEWS": 1,
    "NOISE": 0,
}

SUBCATEGORY_PRIORITY = {
    "hack": 15,
    "exploit": 15,
    "critical_bug": 14,
    "outage": 13,
    "enforcement": 13,
    "license": 10,
    "tvl_spike": 9,
    "tvl_milestone": 8,
    "funding_round": 9,
    "airdrop": 7,
    "tge": 7,
    "mainnet_launch": 6,
    "upgrade": 5,
    "audit": 5,
    "release": 4,
    "integration": 6,
    "collaboration": 6,
    "keynote": 3,
    "ama": 3,
    "hire": 3,
    "podcast": 2,
    "general": 1,
}

_TRADING_NOISE_KEYS = [
    "price prediction", "price target", "price analysis",
    "technical analysis", "bullish", "bearish", "to the moon",
]

# ---------------------------------------------------------------------------
# Heuristic analysis
# ---------------------------------------------------------------------------

def _is_trading_noise(text: str) -> bool:
    """True if the event description sounds like trading noise rather than news."""
    t = text.lower()
    return any(k in t for k in _TRADING_NOISE_KEYS)


def _event_priority(ev: RawEvent) -> float:
    """Compute a single-event priority score (0–15)."""
    cat_score = CATEGORY_PRIORITY.get(ev.category, 1)
    subcat_score = SUBCATEGORY_PRIORITY.get(ev.subcategory, cat_score)
    # Blend subcategory into category score if available
    score = max(cat_score, subcat_score)
    # Scale by reliability
    score *= ev.reliability
    # Small penalty for trading noise
    if _is_trading_noise(ev.description):
        score *= 0.3
    return score


def _merge_similar_events(events: list[RawEvent]) -> list[dict]:
    """Merge events that describe the same thing across sources.

    Two events are merged when they share:
      - same subcategory
      - OR a significant amount of overlapping trigrams
    """
    merged: list[dict] = []
    seen: set[int] = set()

    def _trigrams(ev: RawEvent) -> set[str]:
        words = ev.description.lower().split()
        return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}

    for i, ev in enumerate(events):
        if i in seen:
            continue
        group = [ev]
        tgi = _trigrams(ev)
        for j in range(i + 1, len(events)):
            if j in seen:
                continue
            evj = events[j]
            # Merge on same subcategory OR >=2 trigrams overlap
            if ev.subcategory == evj.subcategory and ev.subcategory != "general":
                group.append(evj)
                seen.add(j)
            else:
                tgj = _trigrams(evj)
                if len(tgi & tgj) >= 2:
                    group.append(evj)
                    seen.add(j)

        # Build merged key event
        best = max(group, key=lambda e: e.reliability)
        sources = sorted(set(e.source for e in group if e.source))
        priority = _event_priority(best)

        # Extract best URL from the group
        url = ""
        for e in group:
            if e.raw_url and isinstance(e.raw_url, str) and e.raw_url.startswith("http"):
                url = e.raw_url
                break

        # Create a concise topic from the best event
        topic = best.description[:80] if best.description else "Activity"

        # Build detail
        detail = best.description[:200] if best.description else "No description"

        # Build why_it_matters from category
        why_map = {
            "RISK_ALERT": "Could impact token prices or user funds. Monitor for official patch.",
            "REGULATORY": "Regulatory developments often move markets and affect protocol viability.",
            "FINANCIAL": "Capital flow signals often precede price action.",
            "PARTNERSHIP": "Real integrations drive adoption and usually correlate with price.",
            "TECH_EVENT": "Technical milestones can unlock new use cases and attract builders.",
            "VISIBILITY": "Community engagement and team changes affect long-term trust.",
        }
        why = why_map.get(best.category, "Worth monitoring for ecosystem momentum.")

        merged.append({
            "topic": topic,
            "category": best.category,
            "sources": sources,
            "priority": _clamp_priority(int(priority)),
            "confidence": round(min(1.0, 0.5 + 0.15 * len(sources) + 0.1 * best.reliability), 2),
            "detail": detail,
            "why_it_matters": why,
            "url": url,
            # internal bookkeeping not serialized
            "_best_rel": best.reliability,
        })

        seen.add(i)

    # Sort by priority desc
    merged.sort(key=lambda x: -x.get("priority", 0))
    return merged


def _chain_priority_score(merged_events: list[dict], event_count: int, source_count: int) -> int:
    """Compute overall chain priority (0–15) from merged events."""
    if not merged_events:
        return 0
    # Base = highest priority event
    best = max(merged_events, key=lambda e: e.get("priority", 0))
    score = _clamp_priority(best.get("priority", 0))
    # Bonus for number of distinct events (up to +3)
    score += min(3, len(merged_events) // 3)
    # Bonus for multi-source confirmation (up to +2)
    score += min(2, max(0, source_count - 1))
    return _clamp_priority(score)


def _dominant_topic(merged_events: list[dict]) -> str:
    """Pick the dominant topic from merged events."""
    if not merged_events:
        return "Quiet"
    top = merged_events[0]
    return top["topic"][:100] if top["topic"] else "Activity"


def _generate_summary(merged_events: list[dict], chain: str) -> str:
    """Create a 2–4 sentence narrative summary."""
    if not merged_events:
        return "No significant activity detected today."

    sentences = []
    # First 2–3 key events as sentences
    for ev in merged_events[:3]:
        detail = ev["detail"][:150]
        why = ev["why_it_matters"][:120]
        if detail and why:
            sentences.append(f"{_chain_name(chain)}: {detail}. {why}")
        else:
            sentences.append(f"{_chain_name(chain)}: {detail or 'Activity reported'}.")

    if len(sentences) > 2:
        return " ".join(sentences[:3]) + f" (+{len(merged_events) - 3} more events)"
    return " ".join(sentences)


def _chain_name(chain: str) -> str:
    """Capitalize chain name for display."""
    return chain.capitalize() if chain else "Chain"


def _clamp_priority(val: int) -> int:
    return max(0, min(15, val))


def _chain_cfg_summary(chain: str) -> tuple[int, str]:
    """Get tier & category from chain config."""
    cfg = get_chain(chain) or {}
    return int(cfg.get("tier", 3)), str(cfg.get("category", "unknown"))


_EMPTY_DIGEST_TEMPLATE = {
    "chain_tier": 3,
    "chain_category": "unknown",
    "summary": "No significant activity today.",
    "key_events": [],
    "priority_score": 0,
    "dominant_topic": "Quiet",
    "sources_seen": 0,
    "event_count": 0,
    "confidence": 0.0,
}


def _empty_digest(chain: str) -> ChainDigest:
    """Return a fresh empty-chain digest. Never reuse a global mutable."""
    tier, category = _chain_cfg_summary(chain)
    return ChainDigest(
        chain=chain,
        chain_tier=tier,
        chain_category=category,
        **_EMPTY_DIGEST_TEMPLATE,
    )


# ===========================================================================
# Public API
# ===========================================================================

async def analyze_chain(
    chain: str,
    events: list[RawEvent],
    client=None,
    max_events_in_prompt: int = 40,
) -> ChainDigest:
    """Analyze all events for a single chain via deterministic heuristics.

    Args:
        chain: Chain name.
        events: Raw events for this chain.
        client: Ignored (agent-native, no LLM required).
        max_events_in_prompt: Kept for backward compat, ignored.

    Returns:
        ChainDigest. Deterministic, no external calls.
    """
    if not events:
        tier, category = _chain_cfg_summary(chain)
        return ChainDigest(
            chain=chain,
            chain_tier=tier,
            chain_category=category,
            summary="No signals collected for this chain today.",
            priority_score=0,
            dominant_topic="Quiet",
            sources_seen=0,
            event_count=0,
            confidence=1.0,
        )

    tier, category = _chain_cfg_summary(chain)

    # Score and sort events
    scored = sorted(events, key=_event_priority, reverse=True)

    # Merge similar events
    merged = _merge_similar_events(scored)

    # Compute chain-level stats
    source_count = len(set(e.source for e in events if e.source))
    event_count = len(events)
    priority_score = _chain_priority_score(merged, event_count, source_count)
    dominant_topic = _dominant_topic(merged)
    summary = _generate_summary(merged, chain)

    # Confidence based on number of sources and top event confidence
    avg_conf = sum(e["_best_rel"] for e in merged) / len(merged) if merged else 0.0
    multi_source_bonus = min(0.3, (source_count - 1) * 0.1)
    confidence = round(min(1.0, avg_conf + multi_source_bonus), 2)

    return ChainDigest(
        chain=chain,
        chain_tier=tier,
        chain_category=category,
        summary=summary,
        key_events=merged,
        priority_score=priority_score,
        dominant_topic=dominant_topic,
        sources_seen=source_count,
        event_count=event_count,
        confidence=confidence,
    )


async def analyze_all_chains(
    events_by_chain: dict[str, list[RawEvent]],
    client=None,
    max_concurrent: int = 5,
) -> list[ChainDigest]:
    """Analyze all chains in parallel.

    Args:
        events_by_chain: {chain_name: [RawEvent, ...]}
        client: Ignored (agent-native).
        max_concurrent: Kept for backward compat, ignored.

    Returns:
        List of ChainDigest objects (one per chain, even if empty).
    """
    digests = []
    for chain, events in events_by_chain.items():
        digests.append(await analyze_chain(chain, events, client=client))
    return digests
