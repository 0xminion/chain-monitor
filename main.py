"""Chain Monitor — Main entry point (async).

Collectors run in parallel. Twitter uses X Search API via composable providers.
Token usage is tracked and reported in the run log.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config.loader import get_chains, get_active_chains, get_env
from collectors.defillama import DefiLlamaCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.rss_collector import RSSCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector
from collectors.twitter.collector import TwitterCollector
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.narrative_tracker import NarrativeTracker
from output.daily_digest import DailyDigestFormatter
from output.weekly_digest import WeeklyDigestFormatter
from output.telegram_sender import TelegramSender

logging.basicConfig(
    level=get_env("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chain-monitor")


async def run_collectors() -> tuple:
    """Run all collectors concurrently. Returns (events, health, feed_health, token_summary)."""
    sync_collectors = [
        DefiLlamaCollector(),
        CoinGeckoCollector(),
        RSSCollector(),
        RegulatoryCollector(),
        RiskAlertCollector(),
        TradingViewCollector(),
        EventsCollector(),
        HackathonOutcomesCollector(),
    ]
    twitter = TwitterCollector()
    health = {}
    feed_health = {}
    all_events = []

    async def _run_sync(collector):
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, collector.collect)
            return collector, result, None
        except Exception as e:
            return collector, [], e

    sync_tasks = [asyncio.create_task(_run_sync(c)) for c in sync_collectors]
    twitter_task = asyncio.create_task(twitter.collect())

    # Await all sync tasks (order doesn't matter, each returns its collector)
    sync_results = await asyncio.gather(*sync_tasks)
    for collector, result, error in sync_results:
        if error:
            logger.error(f"  {collector.name} failed: {error}")
        else:
            all_events.extend(result)
            logger.info(f"  {collector.name}: {len(result)} events")
        health[collector.name] = collector.get_health()
        if hasattr(collector, 'get_feed_health'):
            feed_health.update(collector.get_feed_health())

    try:
        twitter_events = await twitter_task
        all_events.extend(twitter_events)
        logger.info(f"  twitter: {len(twitter_events)} events")
    except Exception as e:
        logger.error(f"  twitter failed: {e}")

    health["twitter"] = twitter.get_health()
    token_summary = twitter.get_token_summary()
    return all_events, health, feed_health, token_summary


def process_events(raw_events):
    categorizer = EventCategorizer()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()
    narrative_tracker = NarrativeTracker()
    signals = []
    for event in raw_events:
        categorized = categorizer.categorize(event)
        signal = scorer.score(categorized)
        processed_signal, action = reinforcer.process(signal)
        if action != "echo":
            narrative_tracker.record_signal(processed_signal)
        signals.append(processed_signal)
        if action == "created":
            logger.info(f"  NEW: [{processed_signal.chain}] {processed_signal.description[:60]}")
        elif action == "reinforced":
            logger.info(f"  REINFORCED ({processed_signal.source_count}x): [{processed_signal.chain}] {processed_signal.description[:60]}")
    return signals, narrative_tracker


def cleanup_old_signals():
    reinforcer = SignalReinforcer()
    retention_days = int(get_env("DATA_RETENTION_DAYS", "90"))
    reinforcer.cleanup_old(retention_days)


async def main_async():
    logger.info("=" * 50)
    logger.info("Chain Monitor — Starting collection run")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Active chains: {len(get_active_chains())}")
    logger.info("=" * 50)
    t0 = time.time()

    raw_events, health, feed_health, token_summary = await run_collectors()
    logger.info(f"Total raw events: {len(raw_events)}")

    if token_summary:
        ts = token_summary
        logger.info(
            f"[tokens] Twitter X Search: {ts['calls']} calls, "
            f"{ts['input_tokens']} in / {ts['output_tokens']} out / "
            f"{ts['total_tokens']} total tokens "
            f"(avg {ts['avg_input_per_call']}/{ts['avg_output_per_call']} per call)"
        )

    signals, narrative_tracker = process_events(raw_events)
    high_priority = [s for s in signals if s.priority_score >= 8]
    logger.info(f"Total signals: {len(signals)}, High priority: {len(high_priority)}")

    formatter = DailyDigestFormatter()
    digest = formatter.format(signals, source_health=health, source_health_detail=feed_health)

    if formatter.should_send(signals):
        sender = TelegramSender()
        success = await sender.send(digest)
        logger.info(f"Daily digest sent: {success}")
    else:
        logger.info("No daily digest sent (< 3 events scored >=6)")

    now = datetime.now(timezone.utc)
    if now.weekday() == 6:
        weekly_formatter = WeeklyDigestFormatter()
        weekly = weekly_formatter.format(signals, narrative_tracker=narrative_tracker, source_health=health)
        weekly_success = await sender.send(weekly)
        logger.info(f"Weekly digest sent: {weekly_success}")

    cleanup_old_signals()
    narrative_tracker.cleanup_old(retention_weeks=13)

    elapsed = time.time() - t0

    run_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "raw_events": len(raw_events),
        "signals": len(signals),
        "high_priority": len(high_priority),
        "digest_sent": formatter.should_send(signals),
        "source_health": health,
    }
    if token_summary:
        run_log["twitter_token_usage"] = token_summary

    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2)

    logger.info(f"Run complete - {elapsed:.1f}s")
    return signals


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(main_async())


if __name__ == "__main__":
    main()
