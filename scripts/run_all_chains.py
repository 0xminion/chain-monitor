#!/usr/bin/env python3
"""
Full pipeline for ALL chains using divide-and-conquer.

Phase 1: Non-Twitter collectors (run once)
Phase 2: Twitter in batches with zombie cleanup
Phase 3: Deduplicate
Phase 4: Agent categorization checkpoint (running agent provides all categories)
Phase 5: Score + Reinforce
Phase 6: Per-chain deterministic analyze
Phase 7: Agent prompt synthesis
Phase 8: Deliver

No external LLM calls. No keyword matching. The running agent is the only
semantic reasoning engine.

Run with: timeout 1800 python3 scripts/run_all_chains.py
"""

import sys, logging, subprocess, os, asyncio
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))


def _sweep_stale_chromes(min_age_sec: int = 60):
    """Kill stale Chrome renderer processes from prior runs."""
    try:
        result = subprocess.run(
            ["ps", "--no-headers", "-eo", "pid,etimes,comm"],
            capture_output=True, text=True
        )
        killed = 0
        for line in result.stdout.strip().split("\n"):
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            pid, etime_str, comm = parts[0], parts[1], parts[2]
            if "chrome" not in comm.lower():
                continue
            try:
                etime = int(etime_str)
            except ValueError:
                continue
            if etime >= min_age_sec:
                try:
                    os.kill(int(pid), 9)
                    killed += 1
                except ProcessLookupError:
                    pass
        if killed:
            print(f"  [CLEANUP] Killed {killed} stale Chrome processes")
    except Exception as e:
        print(f"  [CLEANUP] Warning: {e}")


def _free_and_swap():
    """Show memory status for diagnostics."""
    try:
        out = subprocess.run(["free", "-h"], capture_output=True, text=True).stdout.strip().split("\n")
        if len(out) >= 2:
            print(f"  [MEM] {out[1].strip()}")
        if len(out) >= 3:
            print(f"  [SWP] {out[2].strip()}")
    except Exception:
        pass


from config.loader import get_env, get_chains, get_active_chains
from processors.pipeline_types import RawEvent, PipelineContext
from processors.parallel_runner import collect_all
from processors.dedup_engine import deduplicate_events
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.chain_analyzer import analyze_all_chains
from processors.summary_engine import synthesize_digest
from output.telegram_sender import TelegramSender

from collectors.defillama import DefiLlamaCollector
from collectors.rss_collector import RSSCollector
from collectors.twitter_collector import TwitterCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.github_collector import GitHubCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chain-monitor-all")

ALL_CHAINS = list(get_chains().keys())
TIER_1_2 = [c for c, cfg in get_chains().items() if cfg.get("tier") in (1, 2)]

print("=" * 60)
print(f"Chain Monitor — All {len(ALL_CHAINS)} Chains (Agent-Native)")
print(f"Time: {datetime.now(timezone.utc).isoformat()}")
print(f"Tier 1+2 focus: {len(TIER_1_2)} chains")
print("=" * 60)


def _persist_digest(digest_text: str):
    """Write daily digest to storage/twitter/summaries for weekly rollup."""
    digest_dir = Path(__file__).parent.parent / "storage" / "twitter" / "summaries"
    digest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = digest_dir / f"daily_digest_{ts}.txt"
    try:
        path.write_text(digest_text, encoding="utf-8")
        logger.info(f"Daily digest persisted: {path}")
    except Exception as exc:
        logger.warning(f"Failed to persist daily digest: {exc}")


async def run_all_chains_pipeline() -> PipelineContext:
    """Execute full agent-native pipeline with batched Twitter collection."""
    ctx = PipelineContext()

    # ── Phase 1: Non-Twitter collectors ──────────────────────────────────────
    print("\n[Phase 1] Non-Twitter collectors")
    non_twitter_collectors = [
        DefiLlamaCollector(), CoinGeckoCollector(), GitHubCollector(),
        RSSCollector(), RegulatoryCollector(), RiskAlertCollector(),
        TradingViewCollector(), EventsCollector(), HackathonOutcomesCollector(),
    ]

    nt_events, nt_health, nt_feed_health = await collect_all(non_twitter_collectors, max_concurrent=5)
    ctx.raw_events.extend(nt_events)
    ctx.health.update(nt_health)
    ctx.feed_health.update(nt_feed_health)
    print(f"  [Phase 1] {len(nt_events)} non-Twitter events")

    # ── Phase 2: Twitter via standalone bridge ──────────────────────────────────────────
    print(f"\n[Phase 2] Loading standalone Twitter data...")
    from collectors.twitter_standalone_bridge import load_recent_standalone_tweets
    twitter_events = load_recent_standalone_tweets(lookback_hours=24)
    ctx.raw_events.extend(twitter_events)
    ctx.health["twitter"] = {"status": "ok", "events": len(twitter_events)}
    print(f"  [OK] {len(twitter_events)} Twitter events loaded")
    print(f"  Total raw events: {len(ctx.raw_events)}")

    # ── Phase 3: Deduplicate ─────────────────────────────────────────────────
    print("\n[Phase 3] Deduplicating events...")
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    print(f"  Unique events: {len(ctx.unique_events)} ({len(ctx.raw_events) - len(ctx.unique_events)} duplicates)")

    # ── Phase 4: Categorization (non-blocking) ──────────────────────────────────────────
    print("\n[Phase 4] Categorization...")
    categorizer = EventCategorizer()

    # Try to load agent categorization results, but DON'T block on it
    agent_results = categorizer.try_load_results()
    if agent_results is not None:
        print(f"  Using agent categorization ({len(agent_results)} results)")
    else:
        print("  No agent categorization available — using source-provided categories")

    event_dicts = [
        {
            "chain": ev.chain,
            "category": ev.category,
            "subcategory": ev.subcategory,
            "description": ev.description,
            "source": ev.source,
            "reliability": ev.reliability,
            "evidence": ev.evidence,
            "semantic": ev.semantic,
        }
        for ev in ctx.unique_events
    ]

    if agent_results is not None:
        categorized_dicts = categorizer.apply_categories(event_dicts, agent_results)
    else:
        # Source-provided fallback — don't block pipeline
        categorized_dicts = event_dicts

    print(f"  {len(categorized_dicts)} events ready for scoring")

    # ── Phase 5: Score + Reinforce ─────────────────────────────────────────────────
    print("\n[Phase 5] Scoring and reinforcing...")
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    signals_for_storage = []
    for ev_dict in categorized_dicts:
        try:
            signal = scorer.score(ev_dict)
            signals_for_storage.append(signal)
        except Exception as exc:
            logger.warning(f"Scoring failed for {ev_dict.get('chain')}: {exc}")

    ctx.signals = signals_for_storage
    print(f"  Signals scored: {len(ctx.signals)}")

    reinforced_signals = []
    for sig in signals_for_storage:
        try:
            processed_signal, action = reinforcer.process(sig)
            reinforced_signals.append(processed_signal)
        except Exception as exc:
            logger.warning(f"Reinforcement failed: {exc}")
    ctx.signals = reinforced_signals
    print(f"  Signals reinforced: {len(ctx.signals)}")

    # ── Phase 6: Per-chain deterministic analyze ─────────────────────────────────
    print("\n[Phase 6] Per-chain deterministic analysis...")

    signals_by_chain = {}
    for sig in ctx.signals:
        signals_by_chain.setdefault(sig.chain, []).append(sig)
    for chain_name in get_active_chains():
        signals_by_chain.setdefault(chain_name, [])

    ctx.chain_digests = await analyze_all_chains(signals_by_chain)
    significant = sum(1 for d in ctx.chain_digests if d.has_significant_activity())
    print(f"  Chain digests: {len(ctx.chain_digests)} ({significant} with activity)")
    for d in sorted(ctx.chain_digests, key=lambda x: -x.priority_score)[:5]:
        print(f"    {d.chain}: score={d.priority_score}, topic={d.dominant_topic[:50]}")

    # ── Phase 7: Agent prompt synthesis ──────────────────────────────────────────
    print("\n[Phase 7] Building agent synthesis prompt...")
    ctx.final_digest = await synthesize_digest(
        ctx.chain_digests,
        source_health=ctx.health,
        source_health_detail=ctx.feed_health,
    )
    print(f"  Prompt saved. Length: {len(ctx.final_digest)} chars")

    # ── Phase 8: Deliver ───────────────────────────────────────────────────────────
    sender = TelegramSender()
    sent = False
    significant_digests = [d for d in ctx.chain_digests if d.has_significant_activity()]
    high_priority = [d for d in ctx.chain_digests if d.priority_score >= 5]
    if len(significant_digests) >= 2 or len(high_priority) >= 1:
        if "🤖 Agent synthesis required" in ctx.final_digest:
            print("  Agent prompt ready — awaiting agent synthesis before sending")
        else:
            try:
                sent = await sender.send(ctx.final_digest)
                print(f"  Digest delivered: {sent}")
            except Exception as exc:
                logger.error(f"Telegram delivery failed: {exc}")
    else:
        print("  Digest not sent — low activity threshold")

    # Persist for weekly rollup
    _persist_digest(ctx.final_digest)

    # Cleanup
    try:
        retention_days = int(get_env("DATA_RETENTION_DAYS", "90"))
        reinforcer.cleanup_old(retention_days)
    except Exception:
        pass

    return ctx


if __name__ == "__main__":
    ctx = asyncio.run(run_all_chains_pipeline())
    print("\n" + "=" * 60)
    print(ctx.final_digest)
    print("=" * 60)
    print("\n[INFO] Run complete")
