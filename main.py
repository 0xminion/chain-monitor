"""Chain Monitor — Main entry point."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from config.loader import get_chains, get_active_chains, get_env
from collectors.defillama import DefiLlamaCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.github_collector import GitHubCollector
from collectors.rss_collector import RSSCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector
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


def run_collectors() -> list[dict]:
    """Run all collectors and return raw events."""
    events = []
    health = {}

    collectors = [
        DefiLlamaCollector(),
        CoinGeckoCollector(),
        GitHubCollector(),
        RSSCollector(),
        RegulatoryCollector(),
        RiskAlertCollector(),
        TradingViewCollector(),
        EventsCollector(),
        HackathonOutcomesCollector(),
    ]

    for collector in collectors:
        logger.info(f"Running collector: {collector.name}")
        try:
            raw_events = collector.collect()
            events.extend(raw_events)
            logger.info(f"  {collector.name}: {len(raw_events)} events")
        except Exception as e:
            logger.error(f"  {collector.name} failed: {e}")
        health[collector.name] = collector.get_health()

    return events, health


def process_events(raw_events: list[dict]) -> tuple[list, NarrativeTracker]:
    """Process raw events through categorizer, scorer, reinforcer. Returns (signals, narrative_tracker)."""
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
    """Clean up signals older than retention period."""
    reinforcer = SignalReinforcer()
    retention_days = int(get_env("DATA_RETENTION_DAYS", "90"))
    reinforcer.cleanup_old(retention_days)


def main():
    """Main entry point — run collectors, process, format, send."""
    logger.info("=" * 50)
    logger.info("Chain Monitor — Starting collection run")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Active chains: {len(get_active_chains())}")
    logger.info("=" * 50)

    # Collect
    raw_events, health = run_collectors()
    logger.info(f"Total raw events: {len(raw_events)}")

    # Process
    signals, narrative_tracker = process_events(raw_events)
    high_priority = [s for s in signals if s.priority_score >= 8]
    logger.info(f"Total signals: {len(signals)}, High priority: {len(high_priority)}")

    # Generate digest
    formatter = DailyDigestFormatter()
    digest = formatter.format(signals, source_health=health)

    # Send if worth sending
    if formatter.should_send(signals):
        sender = TelegramSender()
        success = sender.send_sync(digest)
        logger.info(f"Daily digest sent: {success}")
    else:
        logger.info("No daily digest sent (< 3 events scored ≥6)")

    # Weekly digest (Sundays)
    now = datetime.now(timezone.utc)
    if now.weekday() == 6:  # Sunday
        weekly_formatter = WeeklyDigestFormatter()
        weekly = weekly_formatter.format(signals, narrative_tracker=narrative_tracker, source_health=health)
        sender = TelegramSender()
        success = sender.send_sync(weekly)
        logger.info(f"Weekly digest sent: {success}")

    # Cleanup
    cleanup_old_signals()
    narrative_tracker.cleanup_old(retention_weeks=13)  # ~90 days

    # Save run log
    run_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_events": len(raw_events),
        "signals": len(signals),
        "high_priority": len(high_priority),
        "digest_sent": formatter.should_send(signals),
        "source_health": health,
    }
    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2)

    logger.info("Run complete")
    return signals


if __name__ == "__main__":
    main()
