"""Per-chain semantic analyzer — LLM synthesis of what's happening per chain.

For each chain, batches all collected events and asks the LLM to:
  1. Merge related signals into coherent observations
  2. Classify each observation
  3. Assign chain-level priority score
  4. Generate narrative summary explaining WHY things matter

Parallelizes across all chains with a semaphore to respect rate limits.
"""

import asyncio
import logging
from typing import Optional

from processors.pipeline_types import RawEvent, ChainDigest
from processors.llm_client import LLMClient, LLMError
from config.loader import get_chain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_CHAIN_ANALYSIS_SYSTEM = """You are a senior crypto market intelligence analyst.
You synthesize raw signals across multiple data sources into coherent chain-level observations.
Be precise. Merge signals only when they clearly describe the same event or closely related events.
When in doubt, report separately.

For each key event, you MUST extract the best URL from the raw signals (tweet_url, url, html_url, etc.) and include it as 'url' in your JSON output.
"""

_CHAIN_ANALYSIS_PROMPT = """## Chain: {chain}
Tier: {tier} | Category: {category}

## Signals collected in past 24h ({event_count} total):
{signals_block}

## Instructions
Produce a JSON object with these keys:

1. **priority_score** (int 0-15): Overall importance for traders today. 0 = nothing notable, 15 = market-moving.
2. **dominant_topic** (string): One phrase summarizing the most important thing happening.
3. **confidence** (float 0.0-1.0): How certain you are in this assessment. Higher when multiple independent sources agree.
4. **summary** (string, 2-4 sentences): Narrative of what's happening and why it matters to traders. Be specific, not generic.
5. **key_events** (list): Each merged observation as an object with:
   - topic: concise title
   - category: one of TECH_EVENT, PARTNERSHIP, FINANCIAL, RISK_ALERT, REGULATORY, VISIBILITY, NOISE
   - sources: list of source names (e.g., ["GitHub", "RSS"])
   - priority: int 1-15
   - confidence: float 0.0-1.0
   - detail: 1 sentence what happened
   - why_it_matters: 1 sentence trader significance
   - url: the exact tweet/article URL from the signals, if available (check evidence.url, evidence.link, evidence.html_url, evidence.tweet_url, evidence.pr_url, evidence.feed_url - use ONLY the first one found, never make up URLs)

## Rules
- Merge signals only when they clearly reference the same event (e.g., GitHub release + blog post about same version = ONE event).
- If signals are independent (e.g., a hack + a partnership), report SEPARATE events.
- Use evidence-backed detail. Don't invent facts.
- 'why_it_matters' should mention timeline or downstream effect when possible.
- CRITICAL: For EACH key event, extract the best URL from the signal evidence (look for url, tweet_url, html_url fields) and include it as 'url'.

## Output: STRICT JSON. No markdown fences. No prose outside JSON.
"""

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


def _build_signals_block(events: list[RawEvent]) -> str:
    """Format events for the LLM prompt."""
    if not events:
        return "  (No signals today)"
    lines = []
    for ev in events:
        src = f"[{ev.source}]" if ev.source else "[unknown]"
        cat = f"{ev.category}/{ev.subcategory}"
        desc = ev.description[:180] if ev.description else "(no description)"
        url_hint = f" | URL: {ev.raw_url}" if ev.raw_url else ""
        lines.append(f"- {src} {cat}: {desc}{url_hint}")
    return "\n".join(lines)


def _chain_cfg_summary(chain: str) -> tuple[int, str]:
    """Get tier & category from chain config."""
    cfg = get_chain(chain) or {}
    return int(cfg.get("tier", 3)), str(cfg.get("category", "unknown"))


def _clamp_priority(val: int) -> int:
    return max(0, min(15, val))


def _parse_llm_chain_result(raw: dict, chain: str, events: list[RawEvent]) -> ChainDigest:
    """Sanitize and construct ChainDigest from LLM JSON response."""
    tier, category = _chain_cfg_summary(chain)

    key_events = raw.get("key_events") or []
    if not isinstance(key_events, list):
        key_events = []

    # Normalize key events
    normalized_events = []
    for idx, ke in enumerate(key_events[:20]):  # cap at 20
        if not isinstance(ke, dict):
            continue
        url = ""
        for key in ("url", "html_url", "pr_url", "link", "feed_url"):
            val = ke.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                url = val
                break
        normalized_events.append({
            "topic": str(ke.get("topic", f"Event {idx+1}")),
            "category": str(ke.get("category", "TECH_EVENT")).upper(),
            "sources": ke.get("sources", ["unknown"]),
            "priority": _clamp_priority(int(ke.get("priority") or 0)),
            "confidence": max(0.0, min(1.0, float(ke.get("confidence") or 0.0))),
            "detail": str(ke.get("detail", "")),
            "why_it_matters": str(ke.get("why_it_matters", "")),
            "url": url,
        })

    return ChainDigest(
        chain=chain,
        chain_tier=tier,
        chain_category=category,
        summary=str(raw.get("summary", "No summary available.")),
        key_events=normalized_events,
        priority_score=_clamp_priority(int(raw.get("priority_score") or 0)),
        dominant_topic=str(raw.get("dominant_topic", "")),
        sources_seen=len(set(e.source for e in events)),
        event_count=len(events),
        confidence=max(0.0, min(1.0, float(raw.get("confidence") or 0.0))),
    )


async def analyze_chain(
    chain: str,
    events: list[RawEvent],
    client: Optional[LLMClient] = None,
    max_events_in_prompt: int = 40,
) -> ChainDigest:
    """Analyze all events for a single chain via LLM.

    Args:
        chain: Chain name.
        events: Raw events for this chain.
        client: Optional LLMClient (creates from env if None).
        max_events_in_prompt: Cap events in prompt to fit context window.

    Returns:
        ChainDigest. Never returns None — falls back to empty digest on failure.
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
    client = client or LLMClient.from_env()

    # If too many events, retain highest-reliability subset
    if len(events) > max_events_in_prompt:
        events = sorted(events, key=lambda e: (-e.reliability, -len(e.evidence)))[:max_events_in_prompt]
        logger.info(f"[{chain}] Truncated to {max_events_in_prompt} events for LLM context")

    prompt = _CHAIN_ANALYSIS_PROMPT.format(
        chain=chain,
        tier=tier,
        category=category,
        event_count=len(events),
        signals_block=_build_signals_block(events),
    )

    try:
        result = await asyncio.to_thread(
            client.generate_json_with_retry, prompt, system_prompt=_CHAIN_ANALYSIS_SYSTEM
        )
    except LLMError as exc:
        logger.warning(f"[{chain}] Chain analysis LLM failed: {exc}")
        return ChainDigest(
            chain=chain,
            chain_tier=tier,
            chain_category=category,
            summary="LLM analysis unavailable — see raw signals.",
            key_events=[],
            priority_score=0,
            dominant_topic="Unavailable",
            sources_seen=0,
            event_count=len(events),
            confidence=0.0,
        )
    except Exception as exc:
        logger.error(f"[{chain}] Unexpected error in chain analysis: {exc}")
        return _empty_digest(chain)

    return _parse_llm_chain_result(result, chain, events)


async def analyze_all_chains(
    events_by_chain: dict[str, list[RawEvent]],
    client: Optional[LLMClient] = None,
    max_concurrent: int = 5,
) -> list[ChainDigest]:
    """Analyze all chains in parallel.

    Args:
        events_by_chain: {chain_name: [RawEvent, ...]}
        client: Shared LLMClient.
        max_concurrent: Max simultaneous LLM calls.

    Returns:
        List of ChainDigest objects (one per chain, even if empty).
    """
    client = client or LLMClient.from_env()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _analyze(chain: str, events: list[RawEvent]) -> ChainDigest:
        async with semaphore:
            return await analyze_chain(chain, events, client)

    tasks = [_analyze(c, evs) for c, evs in events_by_chain.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    digests: list[ChainDigest] = []
    failures = 0
    for chain, result in zip(events_by_chain.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"[{chain}] Chain analysis task crashed: {result}")
            failures += 1
            tier, category = _chain_cfg_summary(chain)
            digests.append(ChainDigest(
                chain=chain,
                chain_tier=tier,
                chain_category=category,
                summary="Analysis failed due to pipeline error.",
                key_events=[],
                priority_score=0,
                dominant_topic="Error",
                sources_seen=0,
                event_count=len(events_by_chain.get(chain, [])),
                confidence=0.0,
            ))
        else:
            digests.append(result)

    logger.info(
        f"Chain analysis complete: {len(digests)} chains, "
        f"{failures} failures"
    )
    return digests
