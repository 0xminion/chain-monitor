#!/usr/bin/env python3
"""Live pipeline runner with performance telemetry."""

import asyncio
import json
import resource
import time
import sys
from pathlib import Path

# Ensure repo root
repo = Path(__file__).parent.resolve()
sys.path.insert(0, str(repo))

from main import run_pipeline
from processors.metrics import PipelineMetrics

async def run_with_perf():
    metrics = PipelineMetrics()
    t0 = time.time()
    maxrss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB

    print(f"=== RUN_START: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"maxrss_before: {maxrss_before:.2f} MB")
    print(f"---")

    try:
        ctx = await run_pipeline(metrics=metrics)
    except Exception as exc:
        print(f"PIPELINE_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise

    t1 = time.time()
    maxrss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    elapsed = t1 - t0

    stages = metrics.to_dict().get("stages", {})
    print(f"=== RUN_END ===")
    print(f"elapsed_total: {elapsed:.2f}s")
    print(f"maxrss_before: {maxrss_before:.2f} MB")
    print(f"maxrss_after:  {maxrss_after:.2f} MB")
    print(f"memory_delta:  {maxrss_after - maxrss_before:.2f} MB")
    print(f"stages:")
    for name, data in sorted(stages.items(), key=lambda x: x[1].get("latency_ms", 0) or 0):
        print(f"  {name}: {data.get('latency_ms', 'N/A')}ms | in={data.get('events_in')} out={data.get('events_out')} err={data.get('errors')}")

    # Save perf report
    perf = {
        "ts": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "elapsed_total_s": round(elapsed, 2),
        "memory_mb_before": round(maxrss_before, 2),
        "memory_mb_after": round(maxrss_after, 2),
        "stages": stages,
        "raw_events": len(ctx.raw_events),
        "unique_events": len(ctx.unique_events),
        "signals": len(ctx.signals),
        "chains_with_activity": sum(1 for d in ctx.chain_digests if d.has_significant_activity()),
    }
    perf_dir = repo / "storage" / "health"
    perf_dir.mkdir(parents=True, exist_ok=True)
    perf_file = perf_dir / f"perf_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(perf_file, "w") as f:
        json.dump(perf, f, indent=2)
    print(f"perf_report: {perf_file}")

    # Print digest
    print(f"=== DIGEST ({len(ctx.final_digest)} chars) ===")
    print(ctx.final_digest)

    return ctx.final_digest

if __name__ == "__main__":
    asyncio.run(run_with_perf())
