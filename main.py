"""Chain Monitor v0.1.0 — Agent-native pipeline.

7-stage pipeline:
  1. Parallel collect (async gather across all collectors)
  2. Dedup (O(n) hash-based)
  3. Agent categorization checkpoint (running agent provides all categories)
  4. Score + Reinforce (deterministic heuristics)
  5. Per-chain deterministic analyze (builds ChainDigest for agent review)
  6. Agent prompt synthesis (rich markdown prompt saved for running agent)
  7. Persist + optional delivery + cleanup

No external LLM calls. No keyword matching. The running agent is the only
semantic reasoning engine in the pipeline.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.loader import get_active_chains, get_env, reload_configs, get_pipeline_value
from processors.pipeline_types import PipelineContext
from processors.parallel_runner import collect_all
from processors.dedup_engine import deduplicate_events
from processors.categorizer import EventCategorizer
from processors.scoring import SignalScorer
from processors.reinforcement import SignalReinforcer
from processors.chain_analyzer import analyze_all_chains
from processors.summary_engine import synthesize_digest
from processors.pipeline_utils import safe_json_write
from processors.metrics import PipelineMetrics
from processors.agent_runner import AgentDigestRunner

# Import all collectors
from collectors.defillama import DefiLlamaCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.rss_collector import RSSCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector
from collectors.twitter_collector import TwitterCollector

import logging

logging.basicConfig(
    level=get_env("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chain-monitor")

__version__ = "0.1.0"


async def run_pipeline(metrics: PipelineMetrics | None = None, weekly: bool = False) -> PipelineContext:
    """Execute the full 7-stage agent-native pipeline.

    Args:
        metrics: Optional PipelineMetrics instance for telemetry.
        weekly: If True, run weekly synthesis instead of daily.

    Returns a PipelineContext with all intermediate and final data.
    """
    metrics = metrics or PipelineMetrics()
    reload_configs()
    ctx = PipelineContext()
    ctx.started_at = datetime.now(timezone.utc)
    logger.info("=" * 50)
    logger.info("Chain Monitor v0.1.0 — Agent-native pipeline")
    logger.info(f"Active chains: {len(get_active_chains())}")
    logger.info("=" * 50)

    # ── Stage 1: Parallel Collect ─────────────────────────────────────
    metrics.stage_start("collect")
    collectors = [
        DefiLlamaCollector(),
        CoinGeckoCollector(),
        RSSCollector(),
        RegulatoryCollector(),
        RiskAlertCollector(),
        TradingViewCollector(),
        EventsCollector(),
        HackathonOutcomesCollector(),
        TwitterCollector(standalone_mode=False),
    ]

    ctx.raw_events, ctx.health, ctx.feed_health = await collect_all(
        collectors, max_concurrent=get_pipeline_value("pipeline.max_concurrent_collectors", 4)
    )
    for collector in collectors:
        name = collector.name
        ev_count = len([e for e in ctx.raw_events if e.source == name or getattr(e, 'source', '') == name])
        is_down = ctx.health.get(name, {}).get("status") == "down"
        metrics.record_collector(name, events=ev_count, error=is_down)
    metrics.stage_end("collect", events_in=0, events_out=len(ctx.raw_events), errors=sum(1 for h in ctx.health.values() if h.get("status") == "down"))
    logger.info(
        f"Stage 1 complete: {len(ctx.raw_events)} raw events from "
        f"{len([c for c in collectors if ctx.health.get(c.name, {}).get('status') != 'down'])} healthy collectors"
    )

    # ── Stage 2: Dedup (O(n)) ─────────────────────────────────────────
    metrics.stage_start("dedup")
    ctx.unique_events = deduplicate_events(ctx.raw_events)
    metrics.stage_end("dedup", events_in=len(ctx.raw_events), events_out=len(ctx.unique_events), errors=0)
    logger.info(
        f"Stage 2 complete: {len(ctx.unique_events)} unique events "
        f"({len(ctx.raw_events) - len(ctx.unique_events)} duplicates dropped)"
    )

    # ── Stage 3: Categorization (non-blocking) ───────────────────────────
    metrics.stage_start("categorize")
    categorizer = EventCategorizer()

    # Try to load existing agent categorization results
    agent_results = categorizer.try_load_results()
    if agent_results is not None:
        logger.info(f"[categorizer] Loaded agent results for {len(agent_results)} events")
    else:
        logger.info("[categorizer] No agent results found — using source-provided categories")

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

    metrics.stage_end("categorize", events_in=len(event_dicts), events_out=len(categorized_dicts), errors=0)
    logger.info(f"Stage 3 complete: {len(categorized_dicts)} events categorized")

    # ── Stage 4: Score + Reinforce ─────────────────────────────────────────
    metrics.stage_start("score")
    scorer = SignalScorer()
    reinforcer = SignalReinforcer()

    signals_for_storage: list = []
    score_errors = 0
    for ev_dict in categorized_dicts:
        try:
            signal = scorer.score(ev_dict)
            signals_for_storage.append(signal)
        except Exception as exc:
            score_errors += 1
            logger.warning(f"Scoring failed for {ev_dict.get('chain')}: {type(exc).__name__}: {exc}")

    ctx.signals = signals_for_storage
    metrics.stage_end("score", events_in=len(categorized_dicts), events_out=len(ctx.signals), errors=score_errors)
    logger.info(f"Stage 4a complete: {len(ctx.signals)} signals scored")

    metrics.stage_start("reinforce")
    reinforced_signals: list = []
    reinforce_errors = 0
    for sig in signals_for_storage:
        try:
            processed_signal, action = reinforcer.process(sig)
            reinforced_signals.append(processed_signal)
            if action == "created":
                logger.info(f"  NEW: [{sig.chain}] {sig.description[:60]} (score {sig.priority_score})")
            elif action == "reinforced":
                logger.info(f"  REINFORCED ({sig.source_count}x): [{sig.chain}] {sig.description[:60]}")
        except Exception as exc:
            reinforce_errors += 1
            logger.warning(f"Reinforcement failed for signal [{sig.chain}]: {type(exc).__name__}: {exc}")

    ctx.signals = reinforced_signals
    metrics.stage_end("reinforce", events_in=len(signals_for_storage), events_out=len(ctx.signals), errors=reinforce_errors)
    logger.info(f"Stage 4b complete: {len(ctx.signals)} signals reinforced")

    # ── Stage 5: Per-chain deterministic analyze ─────────────────────────────
    metrics.stage_start("analyze")
    signals_by_chain: dict[str, list] = {}
    for sig in ctx.signals:
        signals_by_chain.setdefault(sig.chain, []).append(sig)

    # Ensure every configured chain has an entry (even empty)
    for chain_name in get_active_chains():
        signals_by_chain.setdefault(chain_name, [])

    ctx.chain_digests = await analyze_all_chains(signals_by_chain)
    significant = sum(1 for d in ctx.chain_digests if d.has_significant_activity())
    metrics.stage_end("analyze", events_in=len(ctx.signals), events_out=len(ctx.chain_digests), errors=0)
    logger.info(
        f"Stage 5 complete: {len(ctx.chain_digests)} chain digests, "
        f"{significant} with significant activity"
    )

    # ── Stage 6: Agent-native synthesis (closed loop) ────────────────────────
    metrics.stage_start("synthesize")
    agent_runner = AgentDigestRunner()
    if weekly:
        ctx.final_digest = await agent_runner.synthesize_weekly()
    else:
        ctx.final_digest = await agent_runner.synthesize(
            ctx.chain_digests,
            source_health=ctx.health,
            source_health_detail=ctx.feed_health,
        )
    metrics.stage_end("synthesize", events_in=len(ctx.chain_digests), events_out=len(ctx.final_digest), errors=0)
    logger.info(f"Stage 6 complete: digest length {len(ctx.final_digest)} chars")

    # ── Stage 7: Persist + optional delivery + cleanup ───────────────────────────
    metrics.stage_start("deliver")
    # 7a: Save run log
    _save_run_log(ctx)

    # 7b: Persist daily digest for weekly rollup
    _persist_daily_digest(ctx.final_digest)

    # 7c: Collector heartbeat alerts (Recommendation #6)
    alert_lines = metrics.get_collector_alert_lines(ctx.health)
    if alert_lines:
        for alert in alert_lines:
            logger.warning(alert)
        # Inject alerts into digest if there are any
        if alert_lines and ctx.final_digest:
            ctx.final_digest = ctx.final_digest + "\n\n" + "\n".join(alert_lines)

    # ── Stage 7d: Agent-native delivery (no external Telegram) ──────────────
    # In v0.2+, the running agent (you) reads the saved prompt and writes
    # prose directly into this chat. The TelegramSender is deprecated.
    logger.info("Digest delivered via agent-native channel (this chat)")

    # Cleanup old signals
    try:
        retention_days = get_pipeline_value("pipeline.data_retention_days", 90)
        reinforcer.cleanup_old(retention_days)
    except (ValueError, Exception):
        logger.warning("Failed to cleanup old signals")

    # Write metrics
    metrics.write()

    logger.info("Pipeline complete")
    return ctx


def _should_send(chain_digests: list) -> bool:
    """Send digest if ≥2 chains have significant activity or ≥1 high-priority (≥5)."""
    min_chains = get_pipeline_value("pipeline.min_chains_for_telegram", 2)
    min_priority = get_pipeline_value("pipeline.min_priority_for_telegram", 5)
    significant = [d for d in chain_digests if d.has_significant_activity()]
    high = [d for d in chain_digests if d.priority_score >= min_priority]
    return len(significant) >= min_chains or len(high) >= 1


def _save_run_log(ctx: PipelineContext):
    """Write pipeline statistics to storage/health/ atomically."""
    log_dir = Path(__file__).parent / "storage" / "health"
    log_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "raw_events": len(ctx.raw_events),
        "unique_events": len(ctx.unique_events),
        "signals": len(ctx.signals),
        "chain_digests": len(ctx.chain_digests),
        "chains_with_activity": sum(1 for d in ctx.chain_digests if d.has_significant_activity()),
        "digest_length": len(ctx.final_digest),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "digest_sent": False,  # Caller can update if needed
        "source_health": ctx.health,
    }

    log_path = log_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    try:
        safe_json_write(log_path, stats)
        logger.info(f"Run log saved: {log_path}")
    except Exception as exc:
        logger.warning(f"Failed to write run log: {exc}")


def _persist_daily_digest(digest_text: str):
    """Write daily digest to storage/twitter/summaries for weekly rollup."""
    digest_dir = Path(__file__).parent / "storage" / "twitter" / "summaries"
    digest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = digest_dir / f"daily_digest_{ts}.txt"
    try:
        from processors.pipeline_utils import safe_text_write
        safe_text_write(path, digest_text)
        logger.info(f"Daily digest persisted: {path}")
    except Exception as exc:
        logger.warning(f"Failed to persist daily digest: {exc}")


async def main():
    """Main entry — run pipeline."""
    import argparse
    parser = argparse.ArgumentParser(description="Chain Monitor Agent-Native Pipeline")
    parser.add_argument("--weekly", action="store_true", help="Run weekly digest synthesis")
    args = parser.parse_args()
    await run_pipeline(weekly=args.weekly)


if __name__ == "__main__":
    asyncio.run(main())
