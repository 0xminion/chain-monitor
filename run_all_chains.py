#!/usr/bin/env python3
"""
Full pipeline for ALL 27 chains using divide-and-conquer.

Phase 1: Non-Twitter collectors (run once)
Phase 2: Twitter in 3 batches (~9 chains per batch) with zombie cleanup
Phase 3: LLM synthesize digest from all saved signals

Run with: timeout 1800 python3 run_all_chains.py
"""

import sys, logging, time, subprocess, os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))


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


from config.loader import get_env, get_chains
from collectors.defillama import DefiLlamaCollector
from collectors.rss_collector import RSSCollector
from collectors.twitter_collector import TwitterCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.narrative_tracker import NarrativeTracker
from output.daily_digest import DailyDigestFormatter

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

# ── Phase 1: Non-Twitter collectors ───────────────────────────────────────────
print("\n[Phase 1] Non-Twitter collectors")
events = []
health = {}
feed_health = {}

for CollectorClass in [DefiLlamaCollector, RSSCollector, RegulatoryCollector, RiskAlertCollector, TradingViewCollector, EventsCollector]:
    collector = CollectorClass()
    try:
        raw = collector.collect()
        events.extend(raw)
        print(f"  [OK] {collector.name}: {len(raw)} events")
    except Exception as e:
        print(f"  [ERR] {collector.name}: {e}")
    health[collector.name] = collector.get_health()
    if hasattr(collector, 'get_feed_health'):
        feed_health.update(collector.get_feed_health())

print(f"\n[Phase 1] Total non-Twitter events: {len(events)}")

# ── Phase 2: Twitter in 3 batches (~9 chains per batch) ─────────────────
print(f"\n[Phase 2] Twitter collection in 3 batches ({len(ALL_CHAINS)} chains)")
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
    twitter._chains_cfg = {k: {} for k in batch_accounts}
    
    batch_events = []
    try:
        batch_events = twitter.collect()
        events.extend(batch_events)
        total_tweets += len(batch_events)
        print(f"  [OK] Batch {i}: {len(batch_events)} tweets")
    except Exception as e:
        print(f"  [ERR] Batch {i}: {e}")
    
    health["twitter"] = twitter.get_health()
    
    if i < len(batches):
        print(f"  [WAIT] 10s cooldown + zombie sweep...")
        time.sleep(5)
        _sweep_stale_chromes(min_age_sec=10)
        _free_and_swap()
        time.sleep(5)

print(f"\n[Phase 2] Total Twitter tweets: {total_tweets}")
print(f"[Phase 2] Total events: {len(events)}")

# ── Phase 3: Process + digest ───────────────────────────────────────────
print("\n[Phase 3] Processing events → digest")
print("  Cleaning stale Chrome before LLM...")
_sweep_stale_chromes(min_age_sec=5)

categorizer = EventCategorizer()
scorer = SignalScorer()
reinforcer = SignalReinforcer()
narrative_tracker = NarrativeTracker()

for event in events:
    categorized = categorizer.categorize(event)
    signal = scorer.score(categorized)
    processed, action = reinforcer.process(signal)
    if action != "echo":
        narrative_tracker.record_signal(processed)

signals = list(reinforcer.signals.values())
high = [s for s in signals if s.priority_score >= 8]
print(f"[Phase 3] Signals: {len(signals)} unique, {len(high)} high-priority")

formatter = DailyDigestFormatter()
digest = formatter.format(signals, source_health=health, source_health_detail=feed_health)
print("\n" + "=" * 60)
print(digest)
print("=" * 60)
print("\n[INFO] Run complete")
