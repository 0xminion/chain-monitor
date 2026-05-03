"""Parallel collector orchestration — run all collectors concurrently.

Uses asyncio.gather() over a semaphore to bound concurrency.
Collectors that are synchronous (blocking I/O) are dispatched via asyncio.to_thread()
to prevent blocking the event loop.
"""

import asyncio
import logging
from typing import Any

from processors.pipeline_types import RawEvent
from processors.pipeline_utils import should_throttle

logger = logging.getLogger(__name__)


async def _run_collector(collector: Any, semaphore: asyncio.Semaphore) -> list[RawEvent]:
    """Run a single collector under a concurrency semaphore.

    Detects whether the collector has an async collect() or sync collect()
    and dispatches appropriately.
    """
    async with semaphore:
        try:
            # Inspect first — prefer async directly
            if asyncio.iscoroutinefunction(getattr(collector, "collect_async", None)):
                raw = await collector.collect_async()
            elif asyncio.iscoroutinefunction(getattr(collector, "collect", None)):
                raw = await collector.collect()
            else:
                raw = await asyncio.to_thread(collector.collect)
        except Exception as exc:
            logger.error(f"[{collector.name}] Collector exception: {type(exc).__name__}: {exc}")
            return []

    # Normalise to list[RawEvent]
    events: list[RawEvent] = []
    for item in raw or []:
        if isinstance(item, RawEvent):
            events.append(item)
        elif isinstance(item, dict):
            try:
                events.append(RawEvent.from_collector_dict(item, collector.name))
            except Exception as exc:
                logger.warning(f"[{collector.name}] Unable to convert dict to RawEvent: {exc}")
        else:
            logger.warning(f"[{collector.name}] Ignoring unknown item type: {type(item)}")
    return events


async def collect_all(
    collectors: list[Any],
    max_concurrent: int | None = None,
) -> tuple[list[RawEvent], dict, dict]:
    """Run all collectors in parallel.

    Strategy:
      - Fire all collectors concurrently under a semaphore.
      - Wait for all to complete (fastest completion order).
      - Aggregate events, health, and per-feed health.

    Args:
        collectors: List of collector instances.
        max_concurrent: Max simultaneous collectors (default from config/pipeline.yaml).

    Returns:
        (events, health, feed_health)
    """
    if max_concurrent is None:
        from config.loader import get_pipeline_value
        max_concurrent = get_pipeline_value("pipeline.max_concurrent_collectors", 5)
    if should_throttle():
        from config.loader import get_pipeline_value
        throttle_concurrency = get_pipeline_value("pipeline.memory_throttle_concurrency", 2)
        logger.warning(f"[collect_all] Memory pressure detected — reducing concurrency to {throttle_concurrency}")
        max_concurrent = min(max_concurrent, throttle_concurrency)

    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_run_collector(c, semaphore) for c in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    events: list[RawEvent] = []
    health: dict = {}
    feed_health: dict = {}

    for collector, result in zip(collectors, results):
        if isinstance(result, Exception):
            logger.error(f"[{collector.name}] Collector failed: {type(result).__name__}: {result}")
            health[collector.name] = {"status": "down", "last_error": str(result)}
            continue

        events.extend(result)
        logger.info(f"[{collector.name}] {len(result)} events")

        # Health
        try:
            health[collector.name] = collector.get_health()
        except Exception as exc:
            logger.warning(f"[{collector.name}] get_health() failed: {exc}")
            health[collector.name] = {"status": "unknown"}

        # Per-feed health (RSS, etc)
        if hasattr(collector, "get_feed_health"):
            try:
                feed_health.update(collector.get_feed_health())
            except Exception as exc:
                logger.warning(f"[{collector.name}] get_feed_health() failed: {exc}")

    logger.info(
        f"Collection complete: {len(collectors)} collectors, "
        f"{len(events)} total events"
    )
    return events, health, feed_health
