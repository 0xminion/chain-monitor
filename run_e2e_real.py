#!/usr/bin/env python3
"""End-to-end pipeline with real Twitter collector (async pages).

v0.2.0 refactor: ONE browser context + concurrent pages via asyncio.
This replaces the ProcessPoolExecutor approach that launched 15 separate
Chromium processes, each consuming hundreds of MB of RAM.
"""

import asyncio
import json
import time
import psutil
from pathlib import Path
from datetime import datetime, timezone

import sys
sys.path.insert(0, "/home/deck/chain-monitor")

process = psutil.Process()

def get_ram_mb():
    return process.memory_info().rss / (1024 ** 2)

async def main():
    from main import run_pipeline
    from processors.metrics import PipelineMetrics

    metrics = PipelineMetrics()
    ram_before = get_ram_mb()
    t0 = time.time()

    ctx = await run_pipeline(metrics=metrics)

    elapsed = time.time() - t0
    ram_after = get_ram_mb()

    # Read the metrics line
    metrics_path = Path("/home/deck/chain-monitor/storage/metrics/metrics.jsonl")
    stage_data = {}
    if metrics_path.exists():
        lines = metrics_path.read_text().strip().split("\n")
        for line in lines:
            d = json.loads(line)
            stage_data = d.get("stages", {})

    # Print report
    print("=" * 60)
    print("CHAIN MONITOR — END-TO-END DAILY DIGEST RUN")
    print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print(f"\nTotal elapsed: {elapsed:.1f}s")
    print(f"RAM before: {ram_before:.0f}MB")
    print(f"RAM after:  {ram_after:.0f}MB")
    print(f"RAM delta:  {ram_after - ram_before:.0f}MB")
    print(f"\nRaw events: {len(ctx.raw_events)}")
    print(f"Unique events: {len(ctx.unique_events)}")
    print(f"Signals scored: {len(ctx.signals)}")
    print(f"Chain digests: {len(ctx.chain_digests)}")
    print(f"Active chains: {sum(1 for d in ctx.chain_digests if d.has_significant_activity())}")
    print(f"\nPer-stage timing:")
    for name, data in stage_data.items():
        lat = data.get("latency_ms")
        if lat is not None:
            print(f"  {name:12s}: {lat:6.0f}ms")
    print(f"\nDigest length: {len(ctx.final_digest)} chars")
    print("=" * 60)

    # Also write report to file for recovery
    report_path = Path("/home/deck/chain-monitor/storage/metrics/run_report.json")
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 2),
        "ram_before_mb": round(ram_before, 1),
        "ram_after_mb": round(ram_after, 1),
        "ram_delta_mb": round(ram_after - ram_before, 1),
        "raw_events": len(ctx.raw_events),
        "unique_events": len(ctx.unique_events),
        "signals": len(ctx.signals),
        "chain_digests": len(ctx.chain_digests),
        "active_chains": sum(1 for d in ctx.chain_digests if d.has_significant_activity()),
        "stages": stage_data,
        "digest_length": len(ctx.final_digest),
        "twitter_async": True,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {report_path}")

    # Print digest artifact
    print("\n" + "=" * 60)
    print("DIGEST ARTIFACT (first 2000 chars)")
    print("=" * 60)
    print(ctx.final_digest[:2000])
    print("\n[...truncated...]" if len(ctx.final_digest) > 2000 else "")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
