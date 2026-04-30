"""Chain Monitor v3.0 — Main entry point.

6-stage pipeline (agent-native):
  1. Parallel collect
  2. Dedup (O(n))
  3. Categorize pass-through (agent assigns categories)
  4. Chain analysis group (agent merges + synthesizes)
  5. Agent synthesis (delegated to running agent)
  6. Deliver (Telegram or prompt) + cleanup
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
from processors.agent_bridge import save_agent_input, agent_synthesize
from output.telegram_sender import TelegramSender

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
    reload_configs()
    ctx = PipelineContext()
    logger.info("=" * 50)
    logger.info("Chain Monitor v3.0 — Starting agent-native pipeline")
    logger.info(f"Active chains: {len(get_active_chains())}")
    logger.info("=" * 50)

    # ── Stage 1: Collect ────────────────────────────────────────
    collectors = [
        DefiLlamaCollector(), CoinGeckoCollector(), GitHubCollector(),
        RSSCollector(), TwitterCollector(standalone_mode=False),
        RegulatoryCollector(), RiskAlertCollector(), TradingViewCollector(),
        EventsCollector(), HackathonOutcomesCollector(),
    ]
    ctx.raw_events, ctx.health, ctx.feed_health = await collect_all(collectors)
    logger.info(f"Stage 1 complete: {len(ctx.raw_events)} raw events")

    # ── Stage 2: Dedup ──────────────────────────────────────────
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    logger.info(f"Stage 2 complete: {len(ctx.unique_events)} unique events")

    # ── Stage 3: Categorize pass-through ────────────────────────
    categorizer = EventCategorizer()
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    enriched_events: list[RawEvent] = []
    signals_for_storage: list = []

    for ev in ctx.unique_events:
        ev_dict = {
            "chain": ev.chain, "category": ev.category, "subcategory": ev.subcategory,
            "description": ev.description, "source": ev.source, "reliability": ev.reliability,
            "evidence": ev.evidence, "semantic": ev.semantic,
        }
        categorizer.categorize(ev_dict)
        ev.category = ev_dict["category"]
        ev.subcategory = ev_dict["subcategory"]
        ev.semantic = ev_dict.get("semantic")
        enriched_events.append(ev)

        try:
            signal = scorer.score(ev_dict)
            signals_for_storage.append(signal)
        except Exception as exc:
            logger.warning(f"Scoring failed for {ev.chain}: {exc}")

    ctx.signals = signals_for_storage
    logger.info(f"Stage 3 complete: {len(ctx.signals)} signals (stub scores)")

    # 3b. Reinforce (persist for historical tracking)
    reinforced = []
    for sig in signals_for_storage:
        try:
            proc, action = reinforcer.process(sig)
            reinforced.append(proc)
        except Exception as exc:
            logger.warning(f"Reinforcement failed: {exc}")
    ctx.signals = reinforced

    # ── Stage 4: Chain grouping + agent input ──────────────────
    events_by_chain: dict[str, list[RawEvent]] = {}
    for ev in enriched_events:
        events_by_chain.setdefault(ev.chain, []).append(ev)
    for chain_name in get_active_chains():
        events_by_chain.setdefault(chain_name, [])

    ctx.chain_digests = await analyze_all_chains(events_by_chain, client=None)
    sig = sum(1 for d in ctx.chain_digests if d.has_significant_activity())
    logger.info(f"Stage 4 complete: {len(ctx.chain_digests)} chain digests, {sig} with activity")

    # ── Stage 4b: Save agent input ─────────────────────────────
    agent_input_path = save_agent_input(ctx)
    logger.info(f"Stage 4b complete: agent input saved to {agent_input_path}")

    # ── Stage 5: Agent synthesis ───────────────────────────────
    ctx.final_digest = await synthesize_digest(
        ctx.chain_digests,
        source_health=ctx.health,
        source_health_detail=ctx.feed_health,
        client=None,
    )
    logger.info(f"Stage 5 complete: agent digest stub {len(ctx.final_digest)} chars")

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
        logger.info("Digest not sent — low activity threshold")

    _save_run_log(ctx, sent)
    _persist_daily_digest(ctx.final_digest)

    try:
        retention_days = int(get_env("DATA_RETENTION_DAYS", "90"))
        reinforcer.cleanup_old(retention_days)
    except Exception:
        logger.warning("Failed to cleanup old signals")

    logger.info("Pipeline complete")
    return ctx


def _should_send(digests: list) -> bool:
    significant = [d for d in digests if d.has_significant_activity()]
    high = [d for d in digests if d.priority_score >= 5]
    return len(significant) >= 2 or len(high) >= 1


def _save_run_log(ctx, sent):
    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)
    stats = ctx.stats()
    stats["timestamp"] = datetime.now(timezone.utc).isoformat()
    stats["digest_sent"] = sent
    stats["source_health"] = ctx.health
    path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(path, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as exc:
        logger.warning(f"Failed to write run log: {exc}")


def _persist_daily_digest(digest_text):
    digest_dir = Path(__file__).parent / "storage" / "twitter" / "summaries"
    digest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = digest_dir / f"daily_digest_{ts}.txt"
    try:
        path.write_text(digest_text, encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to persist daily digest: {exc}")


async def main():
    await run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
