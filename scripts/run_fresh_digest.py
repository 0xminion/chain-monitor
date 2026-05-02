#!/usr/bin/env python3
"""
One-shot fresh daily digest runner.
Does inline Twitter scraping (no bridge/cache) concurrently with non-Twitter
sources, then full pipeline, tracks RAM/runtime.
Synthesis is delegated to the running agent (prompt saved, no LLM inline).
"""
import sys, os, json, time, logging, subprocess

# ── Force unbuffered output even when stdout is a file (non-TTY) ────────
try:
    sys.stdout = open(sys.stdout.fileno(), mode="w", buffering=1, closefd=False)
except (OSError, ValueError):
    pass
from datetime import datetime, timezone
from pathlib import Path
import asyncio

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("fresh-digest")

# ── Clear caches ───────────────────────────────────────────────────────────
def clear_caches():
    for folder in ["events", "signals", "llm_cache", "narratives"]:
        d = REPO_ROOT / "storage" / folder
        if d.exists():
            for f in d.glob("*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass
    logger.info("[CACHE] Cleared old events/signals/llm_cache/narratives")

def sweep_chrome():
    try:
        result = subprocess.run(
            ["ps", "--no-headers", "-eo", "pid,etimes,comm"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split(None, 2)
            if len(parts) < 3 or "chrome" not in parts[2].lower():
                continue
            try:
                etime = int(parts[1])
            except ValueError:
                continue
            if etime >= 60:
                try:
                    os.kill(int(parts[0]), 9)
                except ProcessLookupError:
                    pass
    except Exception:
        pass

# ── RAM helper ─────────────────────────────────────────────────────────────
def log_ram(label: str):
    try:
        import psutil
        vm = psutil.virtual_memory()
        proc = psutil.Process()
        logger.info(
            f"[RAM] {label} | Sys {vm.used/(1024**3):.1f}/{vm.total/(1024**3):.1f}GB ({vm.percent}%) "
            f"| Proc {proc.memory_info().rss/(1024**2):.0f}MB"
        )
    except Exception:
        pass

# ── Twitter Stage (CPU-bound → subprocess, runs in its own asyncio task) ──
def _run_twitter_sync(flat_handles, workers, num_batches):
    """Synchronous wrapper for Twitter scraping — runs in executor so main
    event loop stays free for non-Twitter coroutines."""
    import time as _time
    from scripts.run_twitter_standalone import run_parallel_spawn, _kill_stale_chrome
    from collectors.twitter_collector import TwitterCollector

    _kill_stale_chrome()
    t0 = _time.perf_counter()
    raw_tweets = run_parallel_spawn(
        flat_handles,
        lookback_hours=24,
        workers=workers,
        num_batches=num_batches,
    )
    tc = TwitterCollector(standalone_mode=True)
    events = tc._tweets_to_events(raw_tweets)
    elapsed = _time.perf_counter() - t0
    logger.info(f"[STAGE 1] Twitter: {len(events)} events in {elapsed:.1f}s")
    return events

# ── Non-Twitter Stage (I/O-bound → async, runs concurrently) ──────────────
async def _run_non_twitter():
    """Run non-Twitter collectors."""
    from processors.parallel_runner import collect_all
    from collectors.defillama import DefiLlamaCollector
    from collectors.coingecko_collector import CoinGeckoCollector
    from collectors.rss_collector import RSSCollector
    from collectors.regulatory_collector import RegulatoryCollector
    from collectors.risk_alert_collector import RiskAlertCollector
    from collectors.tradingview_collector import TradingViewCollector
    from collectors.events_collector import EventsCollector
    from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector

    nt_collectors = [
        DefiLlamaCollector(), CoinGeckoCollector(),
        RSSCollector(), RegulatoryCollector(), RiskAlertCollector(),
        TradingViewCollector(), EventsCollector(), HackathonOutcomesCollector(),
    ]
    nt_events, nt_health, nt_feed_health = await collect_all(nt_collectors, max_concurrent=5)
    logger.info(f"[STAGE 2] Non-Twitter: {len(nt_events)} events")
    return nt_events, nt_health, nt_feed_health


# ── Main ───────────────────────────────────────────────────────────────────
async def run():
    print("=" * 60)
    print("Chain Monitor — Fresh Daily Digest")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    sweep_chrome()
    clear_caches()
    log_ram("start")

    total_t0 = time.perf_counter()

    # ── Determine worker count ─────────────────────────────────────────────────
    workers = int(os.environ.get("TWITTER_MAX_WORKERS", "15"))
    # If no env set, query free RAM and cap
    if "TWITTER_MAX_WORKERS" not in os.environ:
        try:
            import psutil
            avail_gb = psutil.virtual_memory().available / (1024 ** 3)
            # ~300 MB per Chromium → allow enough headroom for gateways
            safe_workers = max(2, min(15, int(avail_gb / 0.5) - 4))
            workers = safe_workers
        except Exception:
            workers = 15
    num_batches = int(os.environ.get("TWITTER_NUM_BATCHES", "10"))

    # Load handles
    from config.loader import get_twitter_accounts
    accounts = get_twitter_accounts().get("twitter_accounts", {})
    flat_handles = []
    for chain_name, cfg in accounts.items():
        for h in cfg.get("official", []) + cfg.get("contributors", []):
            flat_handles.append((chain_name, h))

    logger.info(f"[CONFIG] Workers={workers} | Handles={len(flat_handles)}")

    # ── Stage 1+2: Twitter + non-Twitter concurrently ────────────────────────
    logger.info("[STAGE 1+2] Twitter scraping + non-Twitter sources — concurrently...")
    t0 = time.perf_counter()

    loop = asyncio.get_running_loop()
    twitter_task = loop.run_in_executor(
        None, _run_twitter_sync, flat_handles, workers, num_batches
    )
    non_twitter_task = asyncio.create_task(_run_non_twitter())

    results = await asyncio.gather(twitter_task, non_twitter_task, return_exceptions=True)

    # Unpack results
    twitter_events_dicts = results[0]
    nt_result = results[1]

    if isinstance(twitter_events_dicts, Exception):
        logger.error(f"[STAGE 1] Twitter crashed: {twitter_events_dicts}")
        twitter_events_dicts = []
    if isinstance(nt_result, Exception):
        logger.error(f"[STAGE 2] Non-Twitter crashed: {nt_result}")
        nt_events, nt_health, nt_feed_health = [], {}, {}
    else:
        nt_events, nt_health, nt_feed_health = nt_result

    combined_elapsed = time.perf_counter() - t0
    logger.info(f"[STAGE 1+2 complete] Combined: {combined_elapsed:.1f}s")
    log_ram("post-collection")

    # ── Stage 3: Deduplicate ────────────────────────────────────────────────
    from processors.dedup_engine import deduplicate_events
    from processors.pipeline_types import RawEvent

    all_raw = nt_events + twitter_events_dicts
    normalized_raw = []
    for ev in all_raw:
        if isinstance(ev, dict):
            normalized_raw.append(RawEvent.from_collector_dict(ev, ev.get("source", "unknown")))
        else:
            normalized_raw.append(ev)
    all_raw = normalized_raw

    logger.info(f"[STAGE 3] Dedup: {len(all_raw)} total raw events...")
    t0 = time.perf_counter()
    unique_events = deduplicate_events(all_raw)
    dedup_elapsed = time.perf_counter() - t0
    logger.info(f"[STAGE 3] Dedup: {len(unique_events)} unique ({len(all_raw)-len(unique_events)} dropped) in {dedup_elapsed:.1f}s")

    # ── Stage 4: Categorize (passthrough if no agent cache) ──────────────────
    from processors.categorizer import EventCategorizer
    logger.info("[STAGE 4] Categorize...")
    t0 = time.perf_counter()
    categorizer = EventCategorizer()
    agent_res = categorizer.try_load_results()
    event_dicts = [
        {"chain": ev.chain, "category": ev.category, "subcategory": ev.subcategory,
         "description": ev.description, "source": ev.source, "reliability": ev.reliability,
         "evidence": ev.evidence, "semantic": ev.semantic}
        for ev in unique_events
    ]
    if agent_res is not None:
        categorized = categorizer.apply_categories(event_dicts, agent_res)
    else:
        categorized = event_dicts
    cat_elapsed = time.perf_counter() - t0
    logger.info(f"[STAGE 4] Categorize: {len(categorized)} events in {cat_elapsed:.1f}s")

    # ── Stage 5: Score + Reinforce ──────────────────────────────────────────
    from processors.scoring import SignalScorer
    from processors.reinforcement import SignalReinforcer
    logger.info("[STAGE 5] Score + Reinforce...")
    t0 = time.perf_counter()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()
    signals = []
    for ev_dict in categorized:
        try:
            signals.append(scorer.score(ev_dict))
        except Exception as exc:
            logger.warning(f"Scoring failed: {exc}")
    reinforced = []
    for sig in signals:
        try:
            processed, action = reinforcer.process(sig)
            reinforced.append(processed)
        except Exception as exc:
            logger.warning(f"Reinforcement failed: {exc}")
    score_elapsed = time.perf_counter() - t0
    logger.info(f"[STAGE 5] Score+Reinforce: {len(reinforced)} signals in {score_elapsed:.1f}s")
    log_ram("post-score")

    # ── Stage 6: Per-chain analysis ────────────────────────────────────────
    from processors.chain_analyzer import analyze_all_chains
    from config.loader import get_active_chains
    logger.info("[STAGE 6] Chain analysis...")
    t0 = time.perf_counter()
    by_chain = {}
    for sig in reinforced:
        by_chain.setdefault(sig.chain, []).append(sig)
    for ch in get_active_chains():
        by_chain.setdefault(ch, [])
    chain_digests = await analyze_all_chains(by_chain)
    analysis_elapsed = time.perf_counter() - t0
    significant = sum(1 for d in chain_digests if d.has_significant_activity())
    logger.info(f"[STAGE 6] Analysis: {len(chain_digests)} digests ({significant} active) in {analysis_elapsed:.1f}s")

    # ── Stage 7: Synthesize digest (prompt-only, agent synthesizes later) ───
    from processors.summary_engine import synthesize_digest
    logger.info("[STAGE 7] Building agent prompt...")
    t0 = time.perf_counter()
    health = {"twitter": {"status": "ok", "events": len(twitter_events_dicts)}}
    health.update(nt_health)
    feed_health = nt_feed_health
    digest = await synthesize_digest(chain_digests, source_health=health, source_health_detail=feed_health)
    synth_elapsed = time.perf_counter() - t0
    logger.info(f"[STAGE 7] Prompt saved: {len(digest)} chars in {synth_elapsed:.1f}s")
    log_ram("post-synth")

    total_elapsed = time.perf_counter() - total_t0

    # Persist timing
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    health_dir = REPO_ROOT / "storage" / "health"
    health_dir.mkdir(parents=True, exist_ok=True)
    timing = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_seconds": total_elapsed,
        "combined_collection_seconds": combined_elapsed,
        "dedup_seconds": dedup_elapsed,
        "categorize_seconds": cat_elapsed,
        "score_seconds": score_elapsed,
        "analysis_seconds": analysis_elapsed,
        "synth_seconds": synth_elapsed,
        "stats": {
            "raw_events": len(all_raw),
            "unique_events": len(unique_events),
            "signals": len(reinforced),
            "chain_digests": len(chain_digests),
            "twitter_events": len(twitter_events_dicts),
            "non_twitter_events": len(nt_events),
            "significant_chains": significant,
            "twitter_workers": workers,
        },
    }
    timing_path = health_dir / f"timing_{ts}.json"
    with open(timing_path, "w") as f:
        json.dump(timing, f, indent=2)

    # Build report
    try:
        import psutil
        vm = psutil.virtual_memory()
        proc = psutil.Process()
        ram_str = f"{vm.used/(1024**3):.1f}/{vm.total/(1024**3):.1f} GB ({vm.percent}%)"
        proc_ram = f"{proc.memory_info().rss/(1024**2):.0f} MB"
    except Exception:
        ram_str = "N/A"
        proc_ram = "N/A"

    report = f"""**Chain Monitor Daily Digest**

⏱ Runtime: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)
🖥 RAM: {ram_str} | Proc: {proc_ram}

📊 Stats
- Raw events: {len(all_raw)} (Twitter: {len(twitter_events_dicts)}, Other: {len(nt_events)})
- Unique events: {len(unique_events)}
- Signals: {len(reinforced)}
- Chain digests: {len(chain_digests)} ({significant} active)
- Twitter workers: {workers}

⏱ Stage Timing
- Combined collection: {combined_elapsed:.0f}s
- Dedup: {dedup_elapsed:.1f}s
- Categorize: {cat_elapsed:.1f}s
- Score+Reinforce: {score_elapsed:.1f}s
- Chain analysis: {analysis_elapsed:.1f}s
- Prompt build: {synth_elapsed:.1f}s

{digest}
"""

    # Save report
    report_path = health_dir / f"digest_report_{ts}.txt"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"[DONE] Report: {report_path}")

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run())
