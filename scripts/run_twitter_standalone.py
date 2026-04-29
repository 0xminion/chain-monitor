#!/usr/bin/env python3
"""
Twitter/X standalone collector — parallel batched execution.

Split 138 handles into 10 batches, run across 5 parallel workers.
Each worker reuses a single page (page.goto() per handle).

Usage:
    python scripts/run_twitter_standalone.py --hours 24
    python scripts/run_twitter_standalone.py --hours 48 --telegram
"""

import argparse
import json
import logging
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("twitter-standalone")

# ---------------------------------------------------------------------------
# Worker function (must be importable / picklable for ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def _scrape_batch(worker_id: int, batches: list, lookback_hours: int, accounts: dict) -> list[dict]:
    """Open one browser + one page per worker, scrape 2 batches of handles.

    Args:
        worker_id: Worker index for logging.
        batches: List of batches, each batch is a list of (chain, handle_cfg).
        lookback_hours: Tweet lookback window.
        accounts: Full accounts config dict (chain -> cfg).
    """
    from collectors.twitter_collector import TwitterCollector
    # Import here to avoid pickling heavy deps from module level
    import time, random

    log = logging.getLogger(f"twitter-worker-{worker_id}")
    log.info(f"[worker {worker_id}] Starting with {len(batches)} batches")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    collector = TwitterCollector(standalone_mode=True, lookback_hours=lookback_hours)
    collector._accounts = accounts  # inject full config

    try:
        collector._start_browser()
        page = collector._context.new_page()
        log.info(f"[worker {worker_id}] Browser + single page created")
    except Exception as e:
        log.error(f"[worker {worker_id}] Failed to start browser: {e}")
        return []

    total_tweets = []
    try:
        for b_idx, batch in enumerate(batches):
            log.info(f"[worker {worker_id}] Batch {b_idx + 1}/{len(batches)} — {len(batch)} handles")
            for chain_name, hdl in batch:
                handle = hdl["handle"].lstrip("@")
                try:
                    tweets = collector._scrape_profile(handle, hdl, chain_name, cutoff, page=page)
                    total_tweets.extend(tweets)
                    log.info(f"[worker {worker_id}] @{handle}: {len(tweets)} tweets")
                    time.sleep(random.uniform(2, 5))
                except Exception as e:
                    log.error(f"[worker {worker_id}] @{handle} failed: {e}")
            # Sleep between batches to be nice to X
            time.sleep(random.uniform(5, 10))
    finally:
        try:
            page.close()
        except Exception:
            pass
        collector._cleanup()
        log.info(f"[worker {worker_id}] Cleaned up. Tweets: {len(total_tweets)}")

    return total_tweets


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Twitter/X Parallel Batched Collector")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window (default: 24)")
    parser.add_argument("--chains", type=str, default="", help="Comma-separated chains. Default: all.")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    parser.add_argument("--batches", type=int, default=10, help="Total batches (default: 10)")
    parser.add_argument("--telegram", action="store_true", help="Send digest via Telegram")
    parser.add_argument("--json-only", action="store_true", help="Save JSON, skip Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Run but don't save/send")
    parser.add_argument("--seed", type=int, default=None, help="Shuffle seed for deterministic batching")
    return parser.parse_args()


def load_accounts(chains_filter: str = "") -> dict:
    import yaml
    path = REPO_ROOT / "config" / "twitter_accounts.yaml"
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    accounts = data.get("twitter_accounts", {})
    if chains_filter:
        selected = {c.strip().lower() for c in chains_filter.split(",")}
        accounts = {k: v for k, v in accounts.items() if k.lower() in selected}
    return accounts


def chunk(lst, n):
    """Split list into n roughly-equal chunks."""
    size = len(lst) // n + (1 if len(lst) % n else 0)
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def format_telegram_digest(tweets: list[dict]) -> str:
    if not tweets:
        return "🐦 Twitter Standalone — No tweets found in window."
    lines = [
        "🐦 *Twitter Standalone Digest*",
        f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"*Tweets collected:* {len(tweets)}\n",
    ]
    by_chain = {}
    for t in tweets:
        by_chain.setdefault(t.get("chain", "unknown"), []).append(t)
    for chain, chain_tweets in sorted(by_chain.items()):
        lines.append(f"\n🔗 *{chain.upper()}*")
        for t in chain_tweets[:10]:
            h = t.get("account_handle", "")
            ts = t.get("timestamp", "")[:10]
            text = t.get("text", "")[:240].replace("*", "").replace("_", "")
            url = t.get("url", "")
            lines.append(f"• [{ts}] [@{h}](https://x.com/{h})\n  > {text}...\n  [Open tweet]({url})")
        if len(chain_tweets) > 10:
            lines.append(f"  _... and {len(chain_tweets) - 10} more_")
    return "\n".join(lines)


def score_tweets(tweets: list[dict]) -> list:
    from processors.scoring import SignalScorer
    scorer = SignalScorer()
    signals = []
    for t in tweets:
        chain = t.get("chain", "unknown")
        text = t.get("text", "").strip()
        is_rt = t.get("is_retweet", False)
        is_q = t.get("is_quote_tweet", False)
        handle = t.get("account_handle", "")
        role = t.get("account_role", "official")
        reliability = float(t.get("account_reliability", 0.75))
        url = t.get("url", "")
        ts = t.get("timestamp", "")

        if is_rt:
            desc = f"@{handle} reposted: {text}"
        elif is_q:
            desc = f"@{handle} quoted: {text}"
        else:
            desc = text

        event = {
            "chain": chain,
            "category": "NEWS",
            "description": desc[:500],
            "source": "twitter",
            "reliability": reliability,
            "timestamp": ts or datetime.now(timezone.utc).isoformat(),
        }
        try:
            signal = scorer.score(event)
            signals.append(signal)
        except Exception as e:
            logger.warning(f"Scoring failed for tweet: {e}")
    return signals


def main():
    args = parse_args()
    logger.info("=" * 50)
    logger.info("Twitter/X Parallel Batched Collector v2")
    logger.info(f"Batches: {args.batches} | Workers: {args.workers} | Lookback: {args.hours}h")
    logger.info("=" * 50)

    accounts = load_accounts(args.chains)
    if not accounts:
        logger.error("No accounts matched. Exiting.")
        sys.exit(1)

    # Flatten all handles into a single list
    all_handles = []
    for chain, cfg in accounts.items():
        for hdl in cfg.get("official", []) + cfg.get("contributors", []):
            all_handles.append((chain, hdl))

    logger.info(f"Total handles: {len(all_handles)}")

    # Shuffle for even distribution across batches (deterministic if --seed)
    if args.seed is not None:
        random.seed(args.seed)
    random.shuffle(all_handles)

    # Split into batches
    batched = chunk(all_handles, args.batches)
    logger.info(f"Batches created: {len(batched)} (sizes: {[len(b) for b in batched]})")

    # Assign batches to workers: worker i gets batches[i], [i+workers], ...
    worker_tasks = {wid: [] for wid in range(args.workers)}
    for i, batch in enumerate(batched):
        worker_tasks[i % args.workers].append(batch)

    # Filter empty workers
    tasks = [
        {"worker_id": wid, "batches": batches, "lookback_hours": args.hours, "accounts": accounts}
        for wid, batches in worker_tasks.items() if batches
    ]
    logger.info(f"Workers assigned: {len(tasks)}")
    for t in tasks:
        total_handles = sum(len(b) for b in t["batches"])
        logger.info(f"  Worker {t['worker_id']}: {len(t['batches'])} batches, {total_handles} handles")

    # Run parallel scraping
    all_tweets = []
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_scrape_batch, t["worker_id"], t["batches"], t["lookback_hours"], t["accounts"]): t for t in tasks}
        for future in as_completed(futures):
            worker_cfg = futures[future]
            try:
                tweets = future.result()
                logger.info(f"[main] Worker {worker_cfg['worker_id']} returned {len(tweets)} tweets")
                all_tweets.extend(tweets)
            except Exception as e:
                logger.error(f"[main] Worker {worker_cfg['worker_id']} crashed: {e}")

    elapsed = time.time() - start_time
    logger.info(f"[main] All workers done — {len(all_tweets)} tweets in {elapsed:.1f}s")

    if not all_tweets:
        logger.info("No tweets collected. Nothing to do.")
        if args.telegram and not args.dry_run:
            from output.telegram_sender import TelegramSender
            TelegramSender().send_sync("🐦 Twitter — No tweets found.")
        return

    # Score signals
    signals = score_tweets(all_tweets)
    high_priority = [s for s in signals if getattr(s, "priority_score", 0) >= 8]
    logger.info(f"Signals scored: {len(signals)}, high priority: {len(high_priority)}")

    # Persist
    if not args.dry_run:
        now = datetime.now(timezone.utc)
        summary_dir = REPO_ROOT / "storage" / "twitter" / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_path = summary_dir / f"standalone_summary_{now.strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": now.isoformat(),
                    "lookback_hours": args.hours,
                    "chains": list(accounts.keys()),
                    "tweet_count": len(all_tweets),
                    "tweets": all_tweets,
                    "signals": [s.to_dict() for s in signals],
                    "high_priority_count": len(high_priority),
                    "elapsed_seconds": elapsed,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"Summary written: {summary_path}")

    # Telegram
    if args.telegram and not args.dry_run:
        from output.telegram_sender import TelegramSender
        digest = format_telegram_digest(all_tweets)
        sender = TelegramSender()
        success = sender.send_sync(digest)
        logger.info(f"Telegram sent: {success}")

    # Print top chains
    by_chain = {}
    for t in all_tweets:
        by_chain.setdefault(t.get("chain", "unknown"), 0)
        by_chain[t.get("chain", "unknown")] += 1
    logger.info("Tweet counts by chain:")
    for chain, count in sorted(by_chain.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"  {chain}: {count}")

    logger.info("Standalone run complete.")


if __name__ == "__main__":
    main()
