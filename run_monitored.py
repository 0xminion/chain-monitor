"""Live pipeline runner with per-component resource monitoring."""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

sys.path.insert(0, str(Path(__file__).parent))

from main import run_pipeline

logger = logging.getLogger("monitor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def get_process_metrics():
    if psutil is None:
        return {"rss_mb": 0, "cpu_percent": 0.0}
    try:
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info().rss / (1024 ** 2)
        cpu = proc.cpu_percent(interval=0.1)
        return {"rss_mb": round(mem, 1), "cpu_percent": round(cpu, 1)}
    except Exception:
        return {"rss_mb": 0, "cpu_percent": 0.0}


async def monitored_pipeline():
    overall_start = time.time()
    snapshots = []
    
    def _snap(label):
        vm = psutil.virtual_memory() if psutil else None
        proc = get_process_metrics()
        snap = {"label": label, "elapsed_sec": round(time.time() - overall_start, 2)}
        snap.update(proc)
        if vm:
            snap["sys_used_gb"] = round(vm.used / (1024**3), 2)
            snap["sys_avail_gb"] = round(vm.available / (1024**3), 2)
        snapshots.append(snap)
        ts = snap["elapsed_sec"]
        rss = snap["rss_mb"]
        cpu = snap["cpu_percent"]
        avail = snap.get("sys_avail_gb", 0)
        print(f"[{ts:6.1f}s] {label:25s} | RSS {rss:6.1f}MB | CPU {cpu:5.1f}% | Sys {avail:.1f}GB avail")
    
    print("=" * 70)
    print("Chain Monitor Live Pipeline — " + datetime.now(timezone.utc).isoformat() + "Z")
    print("=" * 70)
    
    _snap("START")
    
    try:
        ctx = await run_pipeline()
    except Exception as e:
        _snap("PIPELINE_FAILED")
        print("\nPipeline failed: " + str(e))
        import traceback
        traceback.print_exc()
        return None, snapshots
    
    _snap("PIPELINE_COMPLETE")
    
    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    stats = ctx.stats()
    for k, v in stats.items():
        print(f"  {k:25s}: {v}")
    total_runtime = round(time.time() - overall_start, 2)
    print(f"\n  total_runtime_sec          : {total_runtime}")
    
    digest = ctx.final_digest or ""
    print(f"  digest_length              : {len(digest)} chars")
    
    return digest, snapshots


if __name__ == "__main__":
    digest, snaps = asyncio.run(monitored_pipeline())
    
    # Save snapshot log
    snap_dir = Path("storage/health")
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"monitor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(snap_path, "w") as f:
        json.dump(snaps, f, indent=2)
    
    if digest:
        digest_path = Path("storage/twitter/summaries") / "daily_digest_latest.txt"
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        digest_path.write_text(digest, encoding="utf-8")
        print(f"\nDigest saved: {digest_path}")
