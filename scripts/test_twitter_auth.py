#!/usr/bin/env python3
"""Quick Twitter auth test → scrape a single handle and report.

Usage: .venv/bin/python scripts/test_twitter_auth.py [@handle] [--workers N] [--batches N]
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.twitter_collector import TwitterCollector  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


async def run_test(handle: str, workers: int, batches: int, hours: int) -> int:
    c = TwitterCollector(
        standalone_mode=False,
        lookback_hours=hours,
        max_workers=workers,
        num_batches=batches,
    )

    # Monkey-patch accounts to only the single handle we want
    c._accounts = {"TestChain": {"official": [{"handle": handle}], "contributors": []}}

    results = await c.collect()
    print(f"\n✅ @{handle}: {len(results)} tweets found")
    for r in results[:5]:
        ts = r.get("timestamp", "")
        text = r.get("text", "")[:80]
        print(f"  {ts} → {text}...")
    return len(results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("handle", nargs="?", default="solana")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batches", type=int, default=1)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    n = asyncio.run(run_test(args.handle, args.workers, args.batches, args.hours))
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
