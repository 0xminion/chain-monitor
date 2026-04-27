"""Parallel collector orchestration — run all collectors concurrently.

Uses asyncio.gather() over a semaphore to bound concurrency.
Collectors that are synchronous (blocking I/O) are run in a thread pool.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from processors.pipeline_types import RawEvent

logger = logging.getLogger(__name__)

# Reusable thread pool for CPU-bound or sync-I/O collectors
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="collector-")


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
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(_EXECUTOR, collector.collect)
        except Exception as exc:
            logger.error(f"[{collector.name}] Collector exception: {exc}")
            return []

    # Normalise to list[RawEvent]
    events: list[RawEvent] = []
    for item in raw or []:
        if isinstance(item, RawEvent):
            events.append(item)
        elif isinstance(item, dict):
            events.append(RawEvent.from_collector_dict(item, collector.name))
        else:
            logger.warning(f"[{collector.name}] Ignoring unknown item type: {type(item)}")
    return events


async def collect_all(
    collectors: list[Any],
    max_concurrent: int = 5,
) -> tuple[list[RawEvent], dict, dict]:
    """Run all collectors in parallel.

    Strategy:
      - Fire all collectors concurrently under a semaphore.
      - Wait for all to complete (fastest completion order).
      - Aggregate events, health, and per-feed health.

    Args:
        collectors: List of collector instances.
        max_concurrent: Max simultaneous collectors (default 5).

    Returns:
        (events, health, feed_health)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_run_collector(c, semaphore) for c in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    events: list[RawEvent] = []
    health: dict = {}
    feed_health: dict = {}

    for collector, result in zip(collectors, results):
        if isinstance(result, Exception):
            logger.error(f"[{collector.name}] Collector failed: {result}")
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
