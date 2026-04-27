# Chain Monitor v2.0 — Refactor Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transform the chain-monitor pipeline from raw signal listing into per-chain semantic intelligence with parallel collection, O(n) deduplication, and LLM narrative synthesis. Deliver setup/doctor/management scripts and a reusable skill.

**Architecture:** 6-stage pipeline: `Collect(async) → Deduplicate(O(n)) → Categorize(keyword+LLM) → Score(rule-based) → Chain Summarize(27× LLM) → Digest Synthesize(1× LLM)`. Each stage produces well-defined intermediate data structures.

**Tech Stack:** Python 3.11, asyncio, aiohttp, Ollama/OpenRouter LLM, dataclasses, filelock.

---

## Task 1: Create Pipeline Data Types (`processors/pipeline_types.py`)

**Objective:** Define `RawEvent`, `ChainDigest`, and `PipelineContext` dataclasses used as contracts between all pipeline stages.

**Files:**
- Create: `processors/pipeline_types.py`

**Step 1: Write type definitions**

```python
"""Pipeline data types — contracts between all pipeline stages."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RawEvent:
    """A raw collected event before any processing."""
    chain: str
    category: str
    subcategory: str
    description: str
    source: str
    reliability: float
    evidence: dict = field(default_factory=dict)
    raw_url: Optional[str] = None
    published_at: Optional[datetime] = None
    semantic: Optional[dict] = None

    @property
    def fingerprint(self) -> str:
        """Deterministic content fingerprint for dedup."""
        import hashlib
        raw = f"{self.chain}:{self.category}:{self.raw_url or ''}:{self.description[:200]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]


@dataclass
class ChainDigest:
    """Per-chain LLM-synthesized summary."""
    chain: str
    chain_tier: int
    chain_category: str
    summary: str
    key_events: list[dict] = field(default_factory=list)
    priority_score: int = 0
    dominant_topic: str = ""
    sources_seen: int = 0
    event_count: int = 0
    confidence: float = 0.0


@dataclass
class PipelineContext:
    """Shared mutable context passed through pipeline stages."""
    raw_events: list[RawEvent] = field(default_factory=list)
    unique_events: list[RawEvent] = field(default_factory=list)
    signals: list = field(default_factory=list)
    chain_digests: list[ChainDigest] = field(default_factory=list)
    final_digest: str = ""
    health: dict = field(default_factory=dict)
    feed_health: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now().isoformat())
```

**Step 2: Verify**
```bash
python3 -c "from processors.pipeline_types import RawEvent, ChainDigest; print('OK')"
```
Expected: `OK`

---

## Task 2: Adapt collectors to emit RawEvent

**Objective:** Make all collectors return `RawEvent` instead of raw dicts, and add `raw_url` field for dedup fingerprinting.

**Files:**
- Modify: `collectors/base.py` — add `make_event()` helper and `raw_url` extraction
- Modify: `collectors/defillama.py`, `collectors/coingecko_collector.py`, `collectors/github_collector.py`, `collectors/rss_collector.py`, `collectors/twitter_collector.py`, `collectors/events_collector.py`, others if needed

**Step 1: Extend `collectors/base.py`**

Add to `BaseCollector`:
```python
from processors.pipeline_types import RawEvent

def make_event(
    self,
    chain: str,
    description: str,
    category: str,
    subcategory: str = "general",
    raw_url: Optional[str] = None,
    published_at: Optional[datetime] = None,
    evidence: dict = None,
    semantic: dict = None,
) -> RawEvent:
    return RawEvent(
        chain=chain,
        description=description,
        category=category,
        subcategory=subcategory,
        source=self.name,
        reliability=0.7,  # default; override per collector
        raw_url=raw_url,
        published_at=published_at,
        evidence=evidence or {},
        semantic=semantic,
    )
```

**Step 2: Adapt key collectors** (example with DefiLlama):

In `collectors/defillama.py`, change return from `list[dict]` to `list[RawEvent]`:
```python
# In collect() method, replace dict construction with:
event = self.make_event(
    chain=chain,
    category="FINANCIAL",
    subcategory=subcategory,
    description=desc,
    raw_url=url,
    evidence=evidence_dict,
)
events.append(event)
```

Do the same for other collectors. The minimal set for correctness: `defillama`, `coingecko_collector`, `github_collector`, `rss_collector`.

**Step 3: Run existing tests to verify no regressions**
```bash
cd ~/workspaces/default/chain-monitor
python3 -m pytest tests/ -q --ignore=tests/system/ -x
```
Expected: All pass (or failures only in test data shape expectations to be updated later)

---

## Task 3: Build parallel collector runner (`processors/parallel_runner.py`)

**Objective:** Orchestrate all collectors concurrently via `asyncio.gather()`.

**Files:**
- Create: `processors/parallel_runner.py`

**Step 1: Write runner**

```python
"""Parallel collector orchestration — run all collectors concurrently."""

import asyncio
import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor

from processors.pipeline_types import RawEvent, PipelineContext

logger = logging.getLogger(__name__)


async def _run_collector(collector, semaphore: asyncio.Semaphore) -> list[RawEvent]:
    """Run a single collector under a concurrency semaphore."""
    async with semaphore:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, collector.collect)


async def collect_all(
    collectors: list[Any],
    max_concurrent: int = 5,
) -> tuple[list[RawEvent], dict, dict]:
    """Run all collectors in parallel.

    Returns (events, health, feed_health).
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_run_collector(c, semaphore) for c in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    events: list[RawEvent] = []
    health: dict = {}
    feed_health: dict = {}

    for collector, result in zip(collectors, results):
        logger.info(f"Collector result: {collector.name}")
        if isinstance(result, Exception):
            logger.error(f"  {collector.name} failed: {result}")
            health[collector.name] = {"status": "down", "last_error": str(result)}
        else:
            events.extend(result)
            logger.info(f"  {collector.name}: {len(result)} events")
            health[collector.name] = collector.get_health()
        if hasattr(collector, "get_feed_health"):
            feed_health.update(collector.get_feed_health())

    return events, health, feed_health
```

**Step 2: Verify**
```bash
python3 -c "from processors.parallel_runner import collect_all; print('OK')"
```

---

## Task 4: Build O(n) dedup engine (`processors/dedup_engine.py`)

**Objective:** Deduplicate raw events in a single pass with no quadratic complexity.

**Step 1: Write dedup engine**

```python
"""O(n) deduplication engine using hash-based fingerprinting."""

import logging
from typing import Optional
from datetime import datetime, timezone

from processors.pipeline_types import RawEvent

logger = logging.getLogger(__name__)


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """Normalize URL for comparison (strip query, trailing slash, lower)."""
    if not url:
        return None
    u = url.strip().lower().split("?")[0].rstrip("/")
    return u if u.startswith("http") else None


def deduplicate_events(events: list[RawEvent]) -> list[RawEvent]:
    """Single-pass deduplication of raw events.

    Strategy:
    1. URL index — if two events share the same normalized URL + same chain, keep the one with more evidence.
    2. Fingerprint index — if URL not available, use content fingerprint (chain+category+description[:200]).
    3. Always keep the event with the most evidence fields populated.
    """
    seen: dict[str, RawEvent] = {}

    for ev in events:
        # Prefer URL-based key
        norm_url = _normalize_url(ev.raw_url)
        if norm_url:
            key = f"url:{ev.chain}:{norm_url}"
        else:
            key = f"fp:{ev.fingerprint}"

        existing = seen.get(key)
        if existing is None:
            seen[key] = ev
            continue

        # Keep the richer event
        existing_evidence_len = len(existing.evidence) if existing.evidence else 0
        new_evidence_len = len(ev.evidence) if ev.evidence else 0
        if new_evidence_len > existing_evidence_len:
            seen[key] = ev
        elif new_evidence_len == existing_evidence_len and ev.published_at and existing.published_at:
            if ev.published_at > existing.published_at:
                seen[key] = ev

    result = list(seen.values())
    logger.info(f"Dedup: {len(events)} raw → {len(result)} unique ({len(events)-len(result)} duplicates)")
    return result
```

**Step 2: Verify with unit test snippet**
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from processors.pipeline_types import RawEvent
from processors.dedup_engine import deduplicate_events

a = RawEvent(chain='solana', category='TECH_EVENT', subcategory='upgrade', description='Solana upgrade v2', source='rss', reliability=0.7, raw_url='https://example.com/a')
b = RawEvent(chain='solana', category='TECH_EVENT', subcategory='upgrade', description='Solana upgrade v2', source='twitter', reliability=0.8, raw_url='https://example.com/a')
c = RawEvent(chain='ethereum', category='TECH_EVENT', subcategory='upgrade', description='Eth upgrade', source='rss', reliability=0.7)

result = deduplicate_events([a,b,c])
assert len(result) == 2, f'Expected 2 unique got {len(result)}'
print('OK')
"
```

---

## Task 5: Build per-chain semantic analyzer (`processors/chain_analyzer.py`)

**Objective:** For each chain, batch all events, send to LLM for semantic synthesis, event classification, priority scoring, and narrative summary.

**Step 1: Write analyzer**

```python
"""Per-chain semantic analyzer — LLM synthesis of what's happening per chain."""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

from processors.pipeline_types import RawEvent, ChainDigest
from processors.llm_client import LLMClient
from config.loader import get_chain, get_baselines

logger = logging.getLogger(__name__)

CHAIN_ANALYSIS_PROMPT = """You are a senior crypto market analyst.

Given the following raw signals collected for {chain} in the past 24 hours, produce a structured analysis.

Signals:
{signals_block}

## Instructions
1. **Synthesize** — Merge related signals from different sources into coherent observations. High confidence only — if two signals mention the same event (e.g., a GitHub release and a tweet about it), merge them. If uncertain, report separately.
2. **Classify** — For each observation, assign one of: TECH_EVENT, PARTNERSHIP, FINANCIAL, RISK_ALERT, REGULATORY, VISIBILITY, NOISE.
3. **Score Priority** — Total priority for the chain (1-15 based on highest-impact observation, cross-reinforcement bonus).
4. **Dominant Topic** — One-phrase summary of what's most important for this chain today.
5. **Narrative** — 1-2 sentence summary of what is happening and why it matters.

## Output: STRICT JSON only, no markdown fences, no prose outside JSON.
{{
  "chain": "{chain}",
  "priority_score": <int 1-15>,
  "dominant_topic": "<one-phrase summary>",
  "confidence": <float 0.0-1.0>,
  "summary": "<2-3 sentence narrative paragraph. Explain WHY things matter, not just what happened.>",
  "key_events": [
    {{
      "topic": "<merged observation title>",
      "category": "<CATEGORY>",
      "sources": ["source1", "source2"],
      "priority": <1-15>,
      "confidence": <0.0-1.0>,
      "detail": "<1 sentence what happened>",
      "why_it_matters": "<1 sentence market/trader relevance>"
    }}
  ]
}}"""


def _build_signals_block(events: list[RawEvent]) -> str:
    lines = []
    for ev in events:
        lines.append(
            f"- [{ev.source}] {ev.category}/{ev.subcategory}: {ev.description[:200]}"
        )
    return "\n".join(lines) if lines else "  (No signals today)"


async def analyze_chain(
    chain: str,
    events: list[RawEvent],
    client: Optional[LLMClient] = None,
) -> Optional[ChainDigest]:
    """Analyze all events for a single chain via LLM.

    Returns ChainDigest or None on LLM failure.
    """
    if not events:
        return None

    chain_cfg = get_chain(chain) or {}
    client = client or LLMClient.from_env()

    # If too many events, keep highest-priority subset
    if len(events) > 30:
        # Sort by reliability and recency heuristics
        events = events[:30]
        logger.info(f"[{chain}] Truncated to 30 events for LLM context")

    prompt = CHAIN_ANALYSIS_PROMPT.format(
        chain=chain,
        signals_block=_build_signals_block(events),
    )

    try:
        result = client.generate_json(prompt)
    except Exception as e:
        logger.warning(f"[{chain}] Chain analysis LLM failed: {e}")
        return None

    # Build ChainDigest from result
    digest = ChainDigest(
        chain=chain,
        chain_tier=chain_cfg.get("tier", 3),
        chain_category=chain_cfg.get("category", "unknown"),
        summary=result.get("summary", "No summary available"),
        key_events=result.get("key_events", []),
        priority_score=result.get("priority_score", 0),
        dominant_topic=result.get("dominant_topic", ""),
        sources_seen=len(set(e.source for e in events)),
        event_count=len(events),
        confidence=result.get("confidence", 0.7),
    )

    return digest


async def analyze_all_chains(
    events_by_chain: dict[str, list[RawEvent]],
    client: Optional[LLMClient] = None,
    max_concurrent: int = 5,
) -> list[ChainDigest]:
    """Analyze all chains in parallel.

    Args:
        events_by_chain: dict mapping chain name → list of RawEvent
        client: LLMClient instance (shared)
        max_concurrent: Max parallel LLM calls (default 5 to avoid rate limits)

    Returns:
        List of ChainDigest objects.
    """
    client = client or LLMClient.from_env()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _analyze_one(chain: str, events: list[RawEvent]) -> Optional[ChainDigest]:
        async with semaphore:
            return await analyze_chain(chain, events, client)

    tasks = [_analyze_one(c, evs) for c, evs in events_by_chain.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    digests: list[ChainDigest] = []
    for chain, result in zip(events_by_chain.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"[{chain}] Chain analysis failed: {result}")
            continue
        if result is not None:
            digests.append(result)

    logger.info(f"Chain analysis complete: {len(digests)}/{len(events_by_chain)} chains succeeded")
    return digests
```

**Step 2: Verify**
```bash
python3 -c "from processors.chain_analyzer import analyze_chain, analyze_all_chains; print('OK')"
```

---

## Task 6: Build final summary engine (`processors/summary_engine.py`)

**Objective:** Take all ChainDigest objects (sorted by priority), synthesize into a final Telegram-ready digest. Use LLM prose for chains scoring ≥5, structured bullets for chains scoring <5.

**Step 1: Write engine**

```python
"""Summary engine — synthesize chain digests into final digest output."""

import logging
from typing import Optional
from datetime import datetime, timezone

from processors.pipeline_types import ChainDigest
from processors.llm_client import LLMClient

logger = logging.getLogger(__name__)

DIGEST_SYNTHESIS_PROMPT = """You are a senior crypto market analyst writing the daily Chain Monitor digest for Telegram.

Today's date: {date_str}

## Chain Digests (highest priority first):
{chain_block}

## Instructions
1. Write in Telegram Markdown (**bold** only, no # headers, no HTML).
2. **Start** with a 1-sentence theme for the day.
3. For chains with priority ≥ 5: write 2-3 sentences of prose synthesis. Explain what is happening and why it matters to traders.
4. For chains with priority < 5: use bullet format — • Chain: dominant_topic (score: X)
5. Group related chains under thematic headings if >1 chain shares a theme (e.g., "ZK Rollup Upgrades").
6. End with a 👀 Watch section: 2-3 upcoming items or follow-ups to monitor.
7. Total: 250-450 words.
8. Do NOT include raw URLs. Do NOT invent events.
9. If no chains have priority ≥3, say "Quiet day across monitored chains."

## Output: Telegram Markdown. No code fences."""


def _format_chain_for_digest(digest: ChainDigest, idx: int) -> str:
    key_events_str = "; ".join(
        f"{e.get('topic', 'event')} ({e.get('category', 'N/A')})"
        for e in digest.key_events[:3]
    )
    return (
        f"\n### {idx+1}. {digest.chain.upper()} (Priority: {digest.priority_score}, Confidence: {digest.confidence:.0%})\n"
        f"Topic: {digest.dominant_topic}\n"
        f"Summary: {digest.summary}\n"
        f"Key events: {key_events_str or 'None'}\n"
    )


async def synthesize_digest(
    digests: list[ChainDigest],
    source_health: Optional[dict] = None,
    source_health_detail: Optional[dict] = None,
    client: Optional[LLMClient] = None,
    date_str: Optional[str] = None,
) -> str:
    """Synthesize chain digests into final Telegram digest.

    Uses LLM for high-priority chains (≥5), structured bullets for low-priority.
    """
    if not digests:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        return f"📊 Chain Monitor — {now}\n\nQuiet day across monitored chains. No significant events detected."

    date_str = date_str or datetime.now(timezone.utc).strftime("%b %d, %Y")
    client = client or LLMClient.from_env()

    # Sort by priority desc
    digests = sorted(digests, key=lambda d: -d.priority_score)
    high_priority = [d for d in digests if d.priority_score >= 5]
    low_priority = [d for d in digests if d.priority_score < 5]

    # Build chain block
    chain_lines = []
    for i, d in enumerate(high_priority):
        chain_lines.append(_format_chain_for_digest(d, i))

    for i, d in enumerate(low_priority):
        chain_lines.append(
            f"\n### {len(high_priority)+i+1}. {d.chain.upper()} (Priority: {d.priority_score})\n"
            f"• {d.dominant_topic or 'No notable activity'}\n"
        )

    chain_block = "".join(chain_lines)

    prompt = DIGEST_SYNTHESIS_PROMPT.format(
        date_str=date_str,
        chain_block=chain_block,
    )

    try:
        raw = client.generate(prompt)
    except Exception as e:
        logger.error(f"Digest synthesis LLM failed: {e}, falling back to structured format")
        return _fallback_digest(digests, date_str)

    # Header check
    if "📊 Chain Monitor" not in raw:
        raw = f"📊 Chain Monitor — {date_str}\n\n" + raw

    # Append source health footer
    if source_health:
        raw += "\n" + _format_health_footer(source_health, source_health_detail)

    return raw.strip()


def _fallback_digest(digests: list[ChainDigest], date_str: str) -> str:
    """Fallback when LLM fails — produce structured digest."""
    lines = [f"📊 Chain Monitor — {date_str}", ""]
    for d in sorted(digests, key=lambda x: -x.priority_score):
        lines.append(f"• {d.chain.upper()}: {d.dominant_topic or 'Activity'} (score {d.priority_score})")
    return "\n".join(lines)


def _format_health_footer(health: dict, detail: dict = None) -> str:
    """Format source health as Telegram footer."""
    lines = ["", "⚠️ Source health"]
    healthy = sum(1 for h in health.values() if h.get("status", "").lower() == "healthy")
    total = len(health)
    lines.append(f"  Collectors: {healthy}/{total} healthy")
    return "\n".join(lines)
```

**Step 2: Verify**
```bash
python3 -c "from processors.summary_engine import synthesize_digest; print('OK')"
```

---

## Task 7: Rewrite `main.py` with 6-stage pipeline

**Objective:** Replace the sequential collection + per-event processing loop with the new async pipeline.

**Step 1: Replace `main.py`**

```python
"""Chain Monitor v2 — Main entry point.

6-stage pipeline:
  1. Parallel collect
  2. Deduplicate
  3. Categorize + Semantic enrich
  4. Score (rule-based)
  5. Per-chain LLM analyze (27 parallel)
  6. Final digest synthesize
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.loader import get_active_chains, get_env
from processors.pipeline_types import PipelineContext, RawEvent
from processors.parallel_runner import collect_all
from processors.dedup_engine import deduplicate_events
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.chain_analyzer import analyze_all_chains
from processors.summary_engine import synthesize_digest
from processors.llm_client import LLMClient
from output.telegram_sender import TelegramSender

# Import collectors
from collectors.defillama import DefiLlamaCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.github_collector import GitHubCollector
from collectors.rss_collector import RSSCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector
from collectors.twitter_collector import TwitterCollector

logging.basicConfig(
    level=get_env("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chain-monitor")


async def run_pipeline() -> PipelineContext:
    """Run the full 6-stage pipeline."""
    ctx = PipelineContext()
    now = datetime.now(timezone.utc)
    logger.info(f"Pipeline starting at {now.isoformat()}")

    # ── Stage 1: Parallel Collect ──────────────────────────────
    collectors = [
        DefiLlamaCollector(),
        CoinGeckoCollector(),
        GitHubCollector(),
        RSSCollector(),
        TwitterCollector(standalone_mode=False),
        RegulatoryCollector(),
        RiskAlertCollector(),
        TradingViewCollector(),
        EventsCollector(),
        HackathonOutcomesCollector(),
    ]

    ctx.raw_events, ctx.health, ctx.feed_health = await collect_all(collectors)
    logger.info(f"Stage 1 complete: {len(ctx.raw_events)} raw events")

    # ── Stage 2: Deduplicate ──────────────────────────────────
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    logger.info(f"Stage 2 complete: {len(ctx.unique_events)} unique events")

    # ── Stage 3: Categorize + Semantic Enrich ──────────────────
    categorizer = EventCategorizer()
    # Batch categorization — single pass over unique events
    enriched_events = []
    for ev in ctx.unique_events:
        ev_dict = ev.__dict__.copy()
        categorized = categorizer.categorize(ev_dict)
        ev.category = categorized.get("category", ev.category)
        ev.subcategory = categorized.get("subcategory", ev.subcategory)
        ev.semantic = categorized.get("semantic")
        enriched_events.append(ev)
    ctx.unique_events = enriched_events
    logger.info("Stage 3 complete: categorization done")

    # ── Stage 4: Score ────────────────────────────────────────
    scorer = SignalScorer()
    signals = []
    for ev in ctx.unique_events:
        # Convert RawEvent to dict for scorer backward-compat
        ev_dict = ev.__dict__.copy()
        try:
            signal = scorer.score(ev_dict)
            signals.append(signal)
        except Exception as e:
            logger.warning(f"Scoring failed for {ev.chain}: {e}")
    ctx.signals = signals
    high_prio = sum(1 for s in signals if s.priority_score >= 8)
    logger.info(f"Stage 4 complete: {len(signals)} signals, {high_prio} high priority")

    # ── Stage 5: Per-chain LLM analyze ────────────────────────
    # Group signals by chain (use signal event evidence for grouping)
    events_by_chain: dict[str, list[RawEvent]] = {}
    for ev in ctx.unique_events:
        events_by_chain.setdefault(ev.chain, []).append(ev)
    # Ensure all active chains have an entry (even empty)
    for chain_name in get_active_chains():
        events_by_chain.setdefault(chain_name, [])

    chain_digests = await analyze_all_chains(events_by_chain)
    ctx.chain_digests = chain_digests
    logger.info(f"Stage 5 complete: {len(chain_digests)} chain digests")

    # ── Stage 6: Final digest synthesize ───────────────────────
    ctx.final_digest = await synthesize_digest(
        ctx.chain_digests,
        source_health=ctx.health,
        source_health_detail=ctx.feed_health,
    )
    logger.info("Stage 6 complete: digest synthesized")

    return ctx


async def main():
    """Main entry — run pipeline and send digest."""
    ctx = await run_pipeline()

    # Send
    sender = TelegramSender()
    success = await sender.send(ctx.final_digest)
    logger.info(f"Digest sent: {success}")

    # Save run log
    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_events": len(ctx.raw_events),
        "unique_events": len(ctx.unique_events),
        "signals": len(ctx.signals),
        "chain_digests": len(ctx.chain_digests),
        "digest_sent": success,
    }
    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2)

    logger.info("Pipeline complete")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Verify import**
```bash
python3 -c "import main; print('OK')"
```
Expected: `OK` (if all dependencies exist)

---

## Task 8: Interactive setup script (`scripts/setup.py`)

**Objective:** Python-based interactive setup wizard. Prompts for LLM provider, model, API keys, Telegram settings. Writes `.env` and validates LLM connectivity.

**Files:**
- Create: `scripts/setup.py`

**Step 1: Write setup wizard**

```python
#!/usr/bin/env python3
"""Interactive setup wizard for Chain Monitor.

Run: python3 scripts/setup.py
"""

import os
import sys
from pathlib import Path
from getpass import getpass

def prompt(msg: str, default: str = "") -> str:
    full = f"{msg} [{default}]: " if default else f"{msg}: "
    val = input(full).strip()
    return val or default


def main():
    print("🔧 Chain Monitor Setup Wizard")
    print("=" * 50)

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        overwrite = prompt(".env already exists. Overwrite?", "n").lower().startswith("y")
        if not overwrite:
            print("Setup cancelled.")
            return

    # LLM Provider
    print("\n1. LLM Configuration")
    provider = prompt("  LLM Provider (ollama / openrouter / openai)", "ollama")
    if provider == "ollama":
        model = prompt("  Primary model", "minimax-m2.7:cloud")
        fallback = prompt("  Fallback model", "gemma4:31b-cloud")
        ollama_host = prompt("  Ollama host", "http://localhost:11434")
    else:
        model = prompt("  API model name")
        fallback = prompt("  Fallback model name (optional)", "")
        ollama_host = ""
        api_key = getpass("  API key: ")

    # LLM digest
    print("\n2. Digest Generation")
    digest_model = prompt("  Digest synthesis model", "glm-5.1:cloud")

    # APIs
    print("\n3. Data Source APIs")
    cryptorank = getpass("  CryptoRank API key (optional): ")
    coingecko = getpass("  CoinGecko API key (optional): ")
    youtube = getpass("  YouTube Data API key (optional): ")
    github = getpass("  GitHub token (optional): ")

    # Telegram
    print("\n4. Telegram Delivery")
    tg_token = getpass("  Telegram bot token: ")
    tg_chat = prompt("  Telegram chat ID")

    # Build .env
    lines = [
        "# Chain Monitor — Environment Variables",
        "# Generated by scripts/setup.py",
        "",
        f"LLM_PROVIDER={provider}",
        f"LLM_MODEL={model}",
        f"LLM_FALLBACK_MODEL={fallback}",
        f"OLLAMA_HOST={ollama_host}",
        "LLM_DIGEST_ENABLED=true",
        f"LLM_DIGEST_MODEL={digest_model}",
        "LLM_DIGEST_TEMPERATURE=0.4",
        "LLM_DIGEST_MAX_TOKENS=1500",
        "LLM_DIGEST_TIMEOUT=45",
        "",
    ]
    if api_key:
        lines.append(f"OPENROUTER_API_KEY={api_key}")
    if cryptorank:
        lines.append(f"CRYPTORANK_API_KEY={cryptorank}")
    if coingecko:
        lines.append(f"COINGECKO_API_KEY={coingecko}")
    if youtube:
        lines.append(f"YOUTUBE_API_KEY={youtube}")
    if github:
        lines.append(f"GITHUB_TOKEN={github}")
    lines.append(f"TELEGRAM_BOT_TOKEN={tg_token}")
    lines.append(f"TELEGRAM_CHAT_ID={tg_chat}")
    lines.extend([
        "",
        "LOG_LEVEL=INFO",
        "DATA_RETENTION_DAYS=90",
    ])

    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n✅ Wrote {env_path}")

    # Validate LLM connectivity
    print("\n🔍 Testing LLM connectivity...")
    try:
        import requests
        resp = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            available = [m.get("name", "") for m in data.get("models", [])]
            if model in available:
                print(f"  ✓ Primary model '{model}' available")
            else:
                print(f"  ⚠️ Model '{model}' not found in Ollama. Available: {available}")
            if fallback in available:
                print(f"  ✓ Fallback model '{fallback}' available")
            else:
                print(f"  ⚠️ Fallback model '{fallback}' not found")
        else:
            print(f"  ✗ Ollama returned {resp.status_code}")
    except Exception as e:
        print(f"  ✗ Could not reach Ollama: {e}")

    print("\n✅ Setup complete!")
    print("Run: python3 main.py")


if __name__ == "__main__":
    main()
```

**Step 2: Make executable**
```bash
chmod +x scripts/setup.py
```

---

## Task 9: Doctor script (`scripts/doctor.py`)

**Objective:** Health check + auto-fix script. Checks LLM, APIs, file permissions, and attempts to repair common issues.

**Files:**
- Create: `scripts/doctor.py`

**Step 1: Write doctor**

```python
#!/usr/bin/env python3
"""Chain Monitor — Health check and auto-fix doctor.

Run: python3 scripts/doctor.py
"""

import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).parent.parent


def check_env() -> list[str]:
    """Check .env exists and key variables are set."""
    issues = []
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        issues.append(".env missing — run: python3 scripts/setup.py")
    else:
        content = env_path.read_text()
        for key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "LLM_MODEL"]:
            if f"{key}=" not in content or f"{key}=your_" in content or f"{key}=***" in content:
                issues.append(f"{key} not configured in .env")
    return issues


def check_llm() -> list[str]:
    """Check LLM connectivity."""
    issues = []
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        if resp.status_code != 200:
            issues.append(f"Ollama returned {resp.status_code}")
        else:
            data = resp.json()
            names = {m.get("name", "") for m in data.get("models", [])}
            model = os.environ.get("LLM_MODEL", "")
            if model and model not in names:
                issues.append(f"LLM model '{model}' not pulled. Run: ollama pull {model}")
    except requests.exceptions.ConnectionError:
        issues.append(f"Cannot connect to Ollama at {host} — is it running?")
    except Exception as e:
        issues.append(f"LLM check error: {e}")
    return issues


def check_storage() -> list[str]:
    """Check storage directories exist and are writable."""
    issues = []
    for subdir in ["storage/events", "storage/health", "storage/narratives"]:
        p = REPO_ROOT / subdir
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
                print(f"  ✓ Created {subdir}")
            except Exception as e:
                issues.append(f"Cannot create {subdir}: {e}")
        elif not os.access(p, os.W_OK):
            issues.append(f"{subdir} is not writable")
    return issues


def check_telegram() -> list[str]:
    """Check Telegram credentials by calling getMe."""
    issues = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token.startswith("your_"):
        issues.append("TELEGRAM_BOT_TOKEN not set")
        return issues
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                print(f"  ✓ Telegram bot: @{data['result']['username']}")
            else:
                issues.append(f"Telegram getMe error: {data}")
        elif resp.status_code == 401:
            issues.append("Telegram token invalid (401)")
        else:
            issues.append(f"Telegram check returned {resp.status_code}")
    except Exception as e:
        issues.append(f"Telegram check failed: {e}")
    return issues


def check_python_deps() -> list[str]:
    """Check required Python packages are installed."""
    issues = []
    for pkg in ["requests", "PyYAML", "aiohttp", "feedparser", "python-dotenv"]:
        try:
            __import__(pkg)
        except ImportError:
            issues.append(f"Missing Python package: {pkg} — run: pip install -r requirements.txt")
    return issues


def main():
    print("🏥 Chain Monitor Doctor")
    print("=" * 50)

    all_checks = [
        ("Environment", check_env),
        ("Python dependencies", check_python_deps),
        ("LLM connectivity", check_llm),
        ("Storage", check_storage),
        ("Telegram", check_telegram),
    ]

    total_issues = 0
    for name, check_fn in all_checks:
        print(f"\n{name}:")
        issues = check_fn()
        if not issues:
            print("  ✓ All good")
        else:
            for iss in issues:
                print(f"  ✗ {iss}")
            total_issues += len(issues)

    print(f"\n{'='*50}")
    if total_issues == 0:
        print("✅ All checks passed. Chain Monitor is healthy.")
    else:
        print(f"⚠️  {total_issues} issue(s) found. Run the suggested fixes above.")
    return total_issues


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Make executable**
```bash
chmod +x scripts/doctor.py
```

---

## Task 10: Management CLI (`scripts/chain_monitor_cli.py`)

**Objective:** A unified CLI for managing chains, cron jobs, output format, and running digests. Uses argparse (typer adds a dep; keep it light).

**Files:**
- Create: `scripts/chain_monitor_cli.py`

**Step 1: Write CLI**

```python
#!/usr/bin/env python3
"""Chain Monitor — Management CLI.

Usage:
    chain-monitor setup        # Interactive setup wizard
    chain-monitor doctor       # Health check + auto-fix
    chain-monitor chains list  # List monitored chains
    chain-monitor chains add <name> --config config.yaml
    chain-monitor chains remove <name>
    chain-monitor digest --dry-run
    chain-monitor cron install [--hour 9]
    chain-monitor cron remove
    chain-monitor config edit  # Open config/ directory
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config.loader import get_active_chains, get_chain, load_yaml, get_sources


def cmd_setup(args):
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "setup.py")])


def cmd_doctor(args):
    rc = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "doctor.py")]).returncode
    sys.exit(rc)


def cmd_chains_list(args):
    chains = get_active_chains()
    print(f"Monitored chains ({len(chains)}):")
    for c in sorted(chains):
        cfg = get_chain(c) or {}
        print(f"  • {c} — tier {cfg.get('tier', '?')}, category: {cfg.get('category', '?')}")


def cmd_chains_add(args):
    chains_path = REPO_ROOT / "config" / "chains.yaml"
    config = load_yaml("chains.yaml")
    if args.name in config:
        print(f"Chain '{args.name}' already exists.")
        return 1
    config[args.name] = {
        "category": args.category or "others",
        "tier": args.tier or 3,
        "coingecko_id": args.coingecko_id,
        "defillama_slug": args.defillama_slug,
        "github_repos": [],
        "blog_rss": None,
        "youtube_channel": None,
        "status_page": None,
        "governance_forum": None,
    }
    import yaml
    with open(chains_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"✅ Added chain '{args.name}' to chains.yaml")
    return 0


def cmd_chains_remove(args):
    chains_path = REPO_ROOT / "config" / "chains.yaml"
    config = load_yaml("chains.yaml")
    if args.name not in config:
        print(f"Chain '{args.name}' not found.")
        return 1
    del config[args.name]
    import yaml
    with open(chains_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"✅ Removed chain '{args.name}' from chains.yaml")
    return 0


def cmd_digest(args):
    if args.dry_run:
        print("🧪 Dry run: executing pipeline without sending Telegram...")
        os.environ["TELEGRAM_BOT_TOKEN"] = ""  # Disable send
    import asyncio
    from main import run_pipeline
    ctx = asyncio.run(run_pipeline())
    print(f"\nPipeline result: {len(ctx.chain_digests)} chain digests")
    if ctx.chain_digests:
        top = sorted(ctx.chain_digests, key=lambda d: -d.priority_score)[0]
        print(f"Top chain: {top.chain} (score {top.priority_score})")
    print(f"\nDigest preview:\n{'-'*40}\n{ctx.final_digest[:600]}...")
    return 0


def cmd_cron_install(args):
    hour = args.hour or 9
    cmdline = f"{sys.executable} {REPO_ROOT}/main.py >> {REPO_ROOT}/storage/health/cron.log 2>&1"
    cron_entry = f"0 {hour} * * * cd {REPO_ROOT} && {cmdline}\n"
    # Add to crontab
    subprocess.run(["crontab", "-l"], capture_output=True)  # Ensure crontab exists
    result = subprocess.run("crontab -l | grep -v 'chain-monitor'", shell=True, capture_output=True, text=True)
    new_crontab = result.stdout + cron_entry
    proc = subprocess.run("crontab -", shell=True, input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"✅ Cron job installed: daily at {hour}:00 UTC")
    else:
        print(f"✗ Failed to install cron: {proc.stderr}")
        return 1
    return 0


def cmd_cron_remove(args):
    result = subprocess.run("crontab -l | grep -v 'chain-monitor' | crontab -", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Cron job removed")
    else:
        print("✗ No chain-monitor cron job found")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Chain Monitor Management CLI")
    subparsers = parser.add_subparsers(dest="command")

    # setup
    subparsers.add_parser("setup", help="Run interactive setup wizard")

    # doctor
    subparsers.add_parser("doctor", help="Run health check and auto-fix")

    # chains
    chains_p = subparsers.add_parser("chains", help="Manage monitored chains")
    chains_sub = chains_p.add_subparsers(dest="chains_cmd")
    chains_sub.add_parser("list", help="List all chains")
    add_p = chains_sub.add_parser("add", help="Add a chain")
    add_p.add_argument("name")
    add_p.add_argument("--category", default="others")
    add_p.add_argument("--tier", type=int, default=3)
    add_p.add_argument("--coingecko-id")
    add_p.add_argument("--defillama-slug")
    rm_p = chains_sub.add_parser("remove", help="Remove a chain")
    rm_p.add_argument("name")

    # digest
    digest_p = subparsers.add_parser("digest", help="Run digest pipeline")
    digest_p.add_argument("--dry-run", action="store_true", help="Run without sending")

    # cron
    cron_p = subparsers.add_parser("cron", help="Manage cron jobs")
    cron_sub = cron_p.add_subparsers(dest="cron_cmd")
    install_p = cron_sub.add_parser("install", help="Install daily cron job")
    install_p.add_argument("--hour", type=int, default=9)
    cron_sub.add_parser("remove", help="Remove cron job")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    cmd_map = {
        ("setup", None): cmd_setup,
        ("doctor", None): cmd_doctor,
        ("chains", "list"): cmd_chains_list,
        ("chains", "add"): cmd_chains_add,
        ("chains", "remove"): cmd_chains_remove,
        ("digest", None): cmd_digest,
        ("cron", "install"): cmd_cron_install,
        ("cron", "remove"): cmd_cron_remove,
    }

    key = (args.command, getattr(args, "chains_cmd", None) or getattr(args, "cron_cmd", None))
    fn = cmd_map.get(key)
    if fn:
        rc = fn(args) or 0
        sys.exit(rc)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Make executable + symlink**
```bash
chmod +x scripts/chain_monitor_cli.py
ln -sf scripts/chain_monitor_cli.py chain-monitor  # Optional convenience link
```

---

## Task 11: Create skill for chain monitor management

**Objective:** A reusable Hermes skill that wraps the CLI commands.

**Step 1: Write skill**

Create `~/.hermes/skills/devops/chain-monitor-management/SKILL.md`:

```yaml
---
name: chain-monitor-management
description: Manage the Chain Monitor crypto intelligence pipeline — setup, health checks, chain configuration, digest execution, and cron scheduling.
category: devops
tags: [crypto, monitoring, chain-monitor, automation, cron]
---

# Chain Monitor Management

## Setup & Installation

Initialize a fresh Chain Monitor installation:

```bash
cd ~/workspaces/default/chain-monitor
python3 scripts/setup.py
```

Follow the interactive prompts for LLM provider, API keys, and Telegram settings.

## Health Check

Run the doctor to diagnose issues:

```bash
python3 scripts/doctor.py
```

Checks: .env config, Python deps, LLM connectivity, storage dirs, Telegram bot.

## Day-to-day Operations

### Run a digest (dry-run)

```bash
python3 scripts/chain_monitor_cli.py digest --dry-run
```

### Run a digest and send to Telegram

```bash
python3 main.py
```

### List monitored chains

```bash
python3 scripts/chain_monitor_cli.py chains list
```

### Add a chain

```bash
python3 scripts/chain_monitor_cli.py chains add monad --category high_tps --tier 2
```

### Remove a chain

```bash
python3 scripts/chain_monitor_cli.py chains remove monad
```

## Cron Scheduling

Install daily digest at 09:00 UTC:

```bash
python3 scripts/chain_monitor_cli.py cron install --hour 9
```

Remove cron job:

```bash
python3 scripts/chain_monitor_cli.py cron remove
```

## Output Format Control

The digest output is controlled by LLM prompts in `processors/chain_analyzer.py` and `processors/summary_engine.py`. Edit these directly to adjust tone, length, or priorities.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Cannot connect to Ollama" | Run `ollama serve` or check OLLAMA_HOST env |
| "Model not found" | Run `ollama pull <model>` |
| "Telegram 401" | Check TELEGRAM_BOT_TOKEN in .env |
| "No events" | Run doctor. Verify API keys and source health. |
| Memory error | Reduce TWITTER_LOOKBACK_HOURS or LLM max tokens. |
```

---

## Task 12: Update tests

**Objective:** Update existing tests to use new types. Add unit tests for `dedup_engine`, `chain_analyzer`, `summary_engine`, and `parallel_runner`.

**Files:**
- Create: `tests/unit/test_dedup_engine.py`
- Create: `tests/unit/test_chain_analyzer.py`
- Create: `tests/unit/test_summary_engine.py`
- Modify: `tests/unit/test_main.py` — update to expect async behavior

**Step 1: Dedup engine test**

```python
import pytest
from processors.pipeline_types import RawEvent
from processors.dedup_engine import deduplicate_events


class TestDedupEngine:
    def test_unique_events_preserved(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7)
        b = RawEvent("ethereum", "TECH_EVENT", "upgrade", "Eth v3", "rss", 0.7)
        result = deduplicate_events([a, b])
        assert len(result) == 2

    def test_url_dedup(self):
        url = "https://example.com/news"
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7, raw_url=url, evidence={"a": 1})
        b = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "twitter", 0.8, raw_url=url, evidence={"a": 1, "b": 2})
        result = deduplicate_events([a, b])
        assert len(result) == 1
        assert result[0].source == "twitter"  # richer evidence kept

    def test_fingerprint_dedup_no_url(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7)
        b = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "twitter", 0.8)
        result = deduplicate_events([a, b])
        assert len(result) == 1
```

**Step 2: Chain analyzer test (mocked)**

```python
import pytest
from processors.pipeline_types import RawEvent, ChainDigest
from processors.chain_analyzer import analyze_chain
from unittest.mock import MagicMock


class TestChainAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_chain_with_mock_llm(self):
        client = MagicMock()
        client.generate_json.return_value = {
            "chain": "solana",
            "priority_score": 8,
            "dominant_topic": "Mainnet upgrade",
            "confidence": 0.92,
            "summary": "Solana is pushing v2 with performance gains.",
            "key_events": [{"topic": "v2 release", "category": "TECH_EVENT", "priority": 8}],
        }
        events = [RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2 launched", "rss", 0.8)]
        digest = await analyze_chain("solana", events, client)
        assert digest is not None
        assert digest.chain == "solana"
        assert digest.priority_score == 8
```

**Step 3: Run all tests**
```bash
python3 -m pytest tests/ -q --ignore=tests/system/
```
Expected: All pass.

---

## Task 13: Commit and push

```bash
git add -A
git commit -m "feat: v2.0 chain-centric pipeline with LLM synthesis, parallel runners, setup/doctor CLI"
git push origin main
```

---

## Verification Checklist

- [ ] `python3 scripts/doctor.py` passes all checks
- [ ] `python3 scripts/chain_monitor_cli.py digest --dry-run` runs without errors
- [ ] LLM chain analysis produces `ChainDigest` objects with non-empty summaries
- [ ] Final digest is Telegram Markdown with per-chain narratives
- [ ] All unit tests pass
- [ ] New files are committed and pushed
