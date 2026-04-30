#!/usr/bin/env python3
"""
Full pipeline for ALL chains using divide-and-conquer.

Phase 1: Non-Twitter collectors (run once)
Phase 2: Twitter in batches with zombie cleanup
Phase 3: Process through v2.0 pipeline (dedup → categorize → score → reinforce → chain analyze → synthesize)

Run with: timeout 1800 python3 scripts/run_all_chains.py
"""

import sys, logging, time, subprocess, os, asyncio
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
from processors.llm_client import LLMClient
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
print(f"Chain Monitor — All {len(ALL_CHAINS)} Chains (Divide & Conquer)")
print(f"Time: {datetime.now(timezone.utc).isoformat()}")
print(f"LLM model: {get_env('LLM_DIGEST_MODEL', 'gemma4:31b-cloud')}")
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
    """Execute full pipeline with batched Twitter collection."""
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

    # ── Phase 2: Twitter in batches ──────────────────────────────────────────
    print(f"\n[Phase 2] Twitter collection in batches ({len(ALL_CHAINS)} chains)")
    _sweep_stale_chromes()
    _free_and_swap()

    full_twitter = TwitterCollector(standalone_mode=False, lookback_hours=24)
    full_accounts = getattr(full_twitter, '_accounts', {})

    batch_size = (len(ALL_CHAINS) + 2) // 3
    batches = [ALL_CHAINS[i:i+batch_size] for i in range(0, len(ALL_CHAINS), batch_size)]

    total_tweets = 0
    for i, batch in enumerate(batches, 1):
        print(f"\n  [Batch {i}/{len(batches)}] Chains: {', '.join(batch)}")
        batch_accounts = {k: v for k, v in full_accounts.items() if k in batch}

        if not batch_accounts:
            print(f"  [SKIP] No accounts for this batch")
            continue

        twitter = TwitterCollector(standalone_mode=False, lookback_hours=24)
        twitter._accounts = batch_accounts

        batch_events = []
        try:
            batch_events = twitter.collect()
            ctx.raw_events.extend(batch_events)
            total_tweets += len(batch_events)
            print(f"  [OK] Batch {i}: {len(batch_events)} tweets")
        except Exception as e:
            print(f"  [ERR] Batch {i}: {e}")

        ctx.health["twitter"] = twitter.get_health()

        if i < len(batches):
            print(f"  [WAIT] 10s cooldown + zombie sweep...")
            time.sleep(5)
            _sweep_stale_chromes(min_age_sec=10)
            _free_and_swap()
            time.sleep(5)

    print(f"\n[Phase 2] Total Twitter tweets: {total_tweets}")
    print(f"[Phase 2] Total raw events: {len(ctx.raw_events)}")

    # ── Phase 3: Deduplicate ─────────────────────────────────────────────────
    print("\n[Phase 3] Deduplicating events...")
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    print(f"  Unique events: {len(ctx.unique_events)} ({len(ctx.raw_events) - len(ctx.unique_events)} duplicates)")

    # ── Phase 4: Categorize + Score + Reinforce ──────────────────────────────
    print("\n[Phase 4] Categorizing, scoring, and reinforcing...")
    categorizer = EventCategorizer()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    enriched_events = []
    signals_for_storage = []

    for ev in ctx.unique_events:
        ev_dict = {
            "chain": ev.chain, "category": ev.category, "subcategory": ev.subcategory,
            "description": ev.description, "source": ev.source, "reliability": ev.reliability,
            "evidence": ev.evidence, "semantic": ev.semantic,
        }
        categorized = categorizer.categorize(ev_dict)
        ev.category = categorized.get("category", ev.category)
        ev.subcategory = categorized.get("subcategory", ev.subcategory)
        ev.semantic = categorized.get("semantic")
        enriched_events.append(ev)

        try:
            signal = scorer.score(categorized)
            signals_for_storage.append(signal)
        except Exception as exc:
            logger.warning(f"Scoring failed for {ev.chain}: {exc}")

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

    # ── Phase 5: Per-chain LLM analyze ───────────────────────────────────────
    print("\n[Phase 5] Per-chain LLM analysis...")
    _sweep_stale_chromes(min_age_sec=5)

    events_by_chain = {}
    for ev in enriched_events:
        events_by_chain.setdefault(ev.chain, []).append(ev)
    for chain_name in get_active_chains():
        events_by_chain.setdefault(chain_name, [])

    llm_client = LLMClient.from_env()
    ctx.chain_digests = await analyze_all_chains(
        events_by_chain,
        client=llm_client,
        max_concurrent=int(get_env("LLM_MAX_CONCURRENT_CHAINS", "5")),
    )
    significant = sum(1 for d in ctx.chain_digests if d.has_significant_activity())
    print(f"  Chain digests: {len(ctx.chain_digests)} ({significant} with activity)")
    for d in sorted(ctx.chain_digests, key=lambda x: -x.priority_score)[:5]:
        print(f"    {d.chain}: score={d.priority_score}, topic={d.dominant_topic[:50]}")

    # ── Phase 6: Final digest synthesize ─────────────────────────────────────
    print("\n[Phase 6] Synthesizing final digest...")
    ctx.final_digest = await synthesize_digest(
        ctx.chain_digests,
        source_health=ctx.health,
        source_health_detail=ctx.feed_health,
        client=llm_client,
    )
    print(f"  Digest length: {len(ctx.final_digest)} chars")

    # ── Phase 7: Deliver ─────────────────────────────────────────────────────
    sender = TelegramSender()
    sent = False
    significant_digests = [d for d in ctx.chain_digests if d.has_significant_activity()]
    high_priority = [d for d in ctx.chain_digests if d.priority_score >= 5]
    if len(significant_digests) >= 2 or len(high_priority) >= 1:
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
