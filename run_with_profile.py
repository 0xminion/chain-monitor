#!/usr/bin/env python3
"""End-to-end pipeline runner with timing + RAM profiling."""

import asyncio
import json
import os
import time
from pathlib import Path

import psutil

# Ensure project root
os.chdir(Path(__file__).parent)

from main import run_pipeline
from processors.metrics import PipelineMetrics

print("=" * 60)
print("Chain Monitor — End-to-End Daily Digest Run")
print("=" * 60)

process = psutil.Process()
start_time = time.time()
ram_samples = []
peak_ram_mb = 0.0

async def run_with_profiling():
    global peak_ram_mb
    metrics = PipelineMetrics()

    # Sample RAM every 2 seconds in background
    async def sample_ram():
        global peak_ram_mb
        while True:
            await asyncio.sleep(2)
            try:
                rss = process.memory_info().rss / (1024 ** 2)
                ram_samples.append(rss)
                if rss > peak_ram_mb:
                    peak_ram_mb = rss
            except Exception:
                pass

    sampler = asyncio.create_task(sample_ram())
    try:
        ctx = await run_pipeline(metrics=metrics)
    finally:
        sampler.cancel()
        try:
            await sampler
        except asyncio.CancelledError:
            pass
    return ctx

ctx = asyncio.run(run_with_profiling())
elapsed = time.time() - start_time

# Read metrics
metrics_path = Path("storage/metrics/metrics.jsonl")
stages = {}
if metrics_path.exists():
    with open(metrics_path) as f:
        for line in f:
            data = json.loads(line)
            stages = data.get("stages", {})
            break

print("\n" + "=" * 60)
print("RUNTIME REPORT")
print("=" * 60)
print(f"Total elapsed: {elapsed:.1f}s")
for name, data in stages.items():
    latency = data.get("latency_ms")
    if latency:
        print(f"  Stage {name}: {latency:.0f}ms")
print(f"  RAM peak: {peak_ram_mb:.0f}MB")
print(f"  RAM start: {ram_samples[0]:.0f}MB" if ram_samples else "  RAM start: N/A")

print("\n" + "=" * 60)
print("DIGEST ARTIFACT")
print("=" * 60)
print(ctx.final_digest[:3000])
print("\n[...truncated...]" if len(ctx.final_digest) > 3000 else "")
print("=" * 60)
