#!/usr/bin/env python3
"""Quick Twitter auth test → scrape a single handle and report.

Usage: .venv/bin/python scripts/test_twitter_auth.py [@handle] [--workers N] [--batches N]
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.twitter_collector import TwitterCollector  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("handle", nargs="?", default="solana")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batches", type=int, default=1)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    c = TwitterCollector(
        standalone_mode=False,
        lookback_hours=args.hours,
        max_workers=args.workers,
        num_batches=args.batches,
    )

    # Monkey-patch accounts to only the single handle we want
    c._accounts = {"TestChain": {"official": [{"handle": args.handle}], "contributors": []}}

    results = c.collect()
    print(f"\n✅ @{args.handle}: {len(results)} tweets found")
    for r in results[:5]:
        ts = r.get("timestamp", "")
        text = r.get("text", "")[:80]
        print(f"  {ts} → {text}...")
    return len(results)


if __name__ == "__main__":
    n = main()
    sys.exit(0 if n > 0 else 1)
