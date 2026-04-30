"""Chain Monitor v2.0 — Main entry point.

6-stage pipeline:
  1. Parallel collect (async gather across all collectors)
  2. Dedup (O(n) hash-based)
  3. Categorize + score + reinforce (per-event, backward compat)
  4. Per-chain LLM analyze (27 parallel calls, semantic synthesis)
  5. Final digest synthesize (LLM prose for ≥5, bullets for <5)
  6. Deliver (Telegram) + cleanup
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.loader import get_active_chains, get_env, reload_configs
from processors.pipeline_types import PipelineContext, RawEvent
from processors.parallel_runner import collect_all
from processors.dedup_engine import deduplicate_events
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.chain_analyzer import analyze_all_chains
from processors.summary_engine import synthesize_digest
from output.telegram_sender import TelegramSender

# Import all collectors
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
    """Execute the full 6-stage pipeline.

    Returns a PipelineContext with all intermediate and final data.
    """
    reload_configs()
    ctx = PipelineContext()
    logger.info("=" * 50)
    logger.info("Chain Monitor v2.0 — Starting pipeline")
    logger.info(f"Active chains: {len(get_active_chains())}")
    logger.info("=" * 50)

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
    logger.info(
        f"Stage 1 complete: {len(ctx.raw_events)} raw events from "
        f"{len([c for c in collectors if ctx.health.get(c.name, {}).get('status') != 'down'])} healthy collectors"
    )

    # ── Stage 2: Dedup (O(n)) ──────────────────────────────────
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    logger.info(
        f"Stage 2 complete: {len(ctx.unique_events)} unique events "
        f"({len(ctx.raw_events) - len(ctx.unique_events)} duplicates dropped)"
    )

    # ── Stage 3: Categorize + Score + Reinforce ────────────────
    # 3a. Categorize + score
    categorizer = EventCategorizer()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    enriched_events: list[RawEvent] = []
    signals_for_storage: list = []

    for ev in ctx.unique_events:
        # Categorize (keyword + optional semantic)
        ev_dict = {
            "chain": ev.chain,
            "category": ev.category,
            "subcategory": ev.subcategory,
            "description": ev.description,
            "source": ev.source,
            "reliability": ev.reliability,
            "evidence": ev.evidence,
            "semantic": ev.semantic,
        }
        categorized = categorizer.categorize(ev_dict)
        ev.category = categorized.get("category", ev.category)
        ev.subcategory = categorized.get("subcategory", ev.subcategory)
        ev.semantic = categorized.get("semantic")
        enriched_events.append(ev)

        # Score into Signal (backward compat with storage)
        try:
            signal = scorer.score(categorized)
            signals_for_storage.append(signal)
        except Exception as exc:
            logger.warning(f"Scoring failed for {ev.chain}: {exc}")

    ctx.signals = signals_for_storage
    logger.info(f"Stage 3a complete: {len(ctx.signals)} signals scored")

    # 3b. Reinforce (persist to storage)
    reinforced_signals: list = []
    for sig in signals_for_storage:
        try:
            processed_signal, action = reinforcer.process(sig)
            reinforced_signals.append(processed_signal)
            if action == "created":
                logger.info(f"  NEW: [{sig.chain}] {sig.description[:60]} (score {sig.priority_score})")
            elif action == "reinforced":
                logger.info(f"  REINFORCED ({sig.source_count}x): [{sig.chain}] {sig.description[:60]}")
        except Exception as exc:
            logger.warning(f"Reinforcement failed for signal [{sig.chain}]: {exc}")

    ctx.signals = reinforced_signals
    logger.info(f"Stage 3b complete: {len(ctx.signals)} signals reinforced")

    # ── Stage 4: Per-chain LLM analyze ───────────────────────────
    # Group enriched events by chain (pass the UNIQUE events, not reinforced signals,
    # so the LLM sees all distinct raw observations to merge them properly)
    events_by_chain: dict[str, list[RawEvent]] = {}
    for ev in enriched_events:
        events_by_chain.setdefault(ev.chain, []).append(ev)

    # Ensure every configured chain has an entry (even empty)
    for chain_name in get_active_chains():
        events_by_chain.setdefault(chain_name, [])

    # Agent-native: no LLM client needed
    ctx.chain_digests = await analyze_all_chains(
        events_by_chain,
        client=None,
        max_concurrent=5,
    )
    significant = sum(1 for d in ctx.chain_digests if d.has_significant_activity())
    logger.info(
        f"Stage 4 complete: {len(ctx.chain_digests)} chain digests, "
        f"{significant} with significant activity"
    )

    # ── Stage 5: Final digest synthesize ───────────────────────
    ctx.final_digest = await synthesize_digest(
        ctx.chain_digests,
        source_health=ctx.health,
        source_health_detail=ctx.feed_health,
        client=None,
    )
    logger.info(f"Stage 5 complete: digest {len(ctx.final_digest)} chars")

    # ── Stage 6: Deliver + cleanup ─────────────────────────────
    sender = TelegramSender()
    sent = False
    if _should_send(ctx.chain_digests):
        try:
            sent = await sender.send(ctx.final_digest)
            logger.info(f"Digest delivered: {sent}")
        except Exception as exc:
            logger.error(f"Telegram delivery failed: {exc}")
    else:
        logger.info("Digest not sent — fewer than 3 chains with significant activity")

    # Save run log
    _save_run_log(ctx, sent)

    # Persist daily digest for weekly rollup
    _persist_daily_digest(ctx.final_digest)

    # Cleanup old signals
    try:
        retention_days = int(get_env("DATA_RETENTION_DAYS", "90"))
        reinforcer.cleanup_old(retention_days)
    except (ValueError, Exception):
        logger.warning("Failed to cleanup old signals")

    logger.info("Pipeline complete")
    return ctx


def _should_send(chain_digests: list) -> bool:
    """Send digest if ≥2 chains have significant activity or ≥1 high-priority (≥5)."""
    significant = [d for d in chain_digests if d.has_significant_activity()]
    high = [d for d in chain_digests if d.priority_score >= 5]
    return len(significant) >= 2 or len(high) >= 1


def _save_run_log(ctx: PipelineContext, sent: bool):
    """Write run statistics to storage/health/."""
    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)

    stats = ctx.stats()
    stats["timestamp"] = datetime.now(timezone.utc).isoformat()
    stats["digest_sent"] = sent
    stats["source_health"] = ctx.health

    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(log_path, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as exc:
        logger.warning(f"Failed to write run log: {exc}")


def _persist_daily_digest(digest_text: str):
    """Write daily digest to storage/twitter/summaries for weekly rollup."""
    digest_dir = Path(__file__).parent / "storage" / "twitter" / "summaries"
    digest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = digest_dir / f"daily_digest_{ts}.txt"
    try:
        path.write_text(digest_text, encoding="utf-8")
        logger.info(f"Daily digest persisted: {path}")
    except Exception as exc:
        logger.warning(f"Failed to persist daily digest: {exc}")


async def main():
    """Main entry — run pipeline."""
    await run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
