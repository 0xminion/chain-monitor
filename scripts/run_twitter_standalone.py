#!/usr/bin/env python3
"""Standalone Twitter collector — no external API, just browser automation.

Collects from configured accounts, outputs raw JSON for the v2.0 digest bridge.

No dedup/reinforcement — standalone pipeline does ONE scrape per profile,
max 50 tweets/account, 100-150 total, 3-7s delays between accounts.

Uses ONE browser context + ONE page reused across all handles
(defaults to Chromium persistent profile -> storage_state cookies -> plain).

Run it:
  python scripts/run_twitter_standalone.py --hours 48 --workers 3 --batches 10
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collectors.twitter_collector import TwitterCollector

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("twitter-standalone")


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def run_batch(batch_id: int, handles: list[tuple], lookback_hours: int):
    """Worker: scrape a batch of handles, save to batch JSON."""
    logger.info(f"[batch-{batch_id}] Starting with {len(handles)} handles")
    
    collector = TwitterCollector(standalone_mode=True, lookback_hours=lookback_hours)
    all_raw = []
    
    try:
        for chain_name, hcfg in handles:
            handle = hcfg["handle"].lstrip("@")
            logger.info(f"[batch-{batch_id}] Scraping @{handle} for {chain_name}")
            
            # Scrape profile (standalone returns raw tweet dicts)
            tweets = collector._scrape_profile(handle, hcfg, chain_name,
                datetime.now(timezone.utc) - timedelta(hours=lookback_hours))
            all_raw.extend(tweets)
            logger.info(f"[batch-{batch_id}] Got {len(tweets)} tweets from @{handle}")
            
            # Rate limit: 3-7s between accounts
            time.sleep(random.randint(3, 7))
    except Exception as e:
        logger.error(f"[batch-{batch_id}] Error: {e}")
    finally:
        collector._cleanup()
    
    # Save batch
    if all_raw:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = REPO_ROOT / "storage" / "twitter" / "raw"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"tweets_{ts}_batch{batch_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(all_raw, f, indent=2, ensure_ascii=False)
        logger.info(f"[batch-{batch_id}] Persisted {len(all_raw)} to {path}")
    
    return len(all_raw)


def _merge_batches() -> list[dict]:
    """Merge all batch files into a single deduped list."""
    raw_dir = REPO_ROOT / "storage" / "twitter" / "raw"
    all_tweets: list[dict] = []
    seen = set()
    
    for path in sorted(raw_dir.glob("tweets_*_batch*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            batch = data if isinstance(data, list) else data.get("tweets", [])
            for t in batch:
                tid = t.get("tweet_id") or t.get("url", "")
                if tid and tid not in seen:
                    seen.add(tid)
                    all_tweets.append(t)
        except Exception as e:
            logger.warning(f"Merge error for {path}: {e}")
    
    return all_tweets


def _build_digest(tweets: list[dict]) -> str:
    """Build plain-text digest from raw tweets."""
    lines = ["# Twitter Summary — Standalone Collection", ""]
    
    by_chain = {}
    for t in tweets:
        by_chain.setdefault(t.get("chain", "unknown"), []).append(t)
    
    for chain, c_tweets in sorted(by_chain.items()):
        lines.append(f"\n## {chain}")
        for tw in c_tweets[:7]:  # max 7 per chain in digest
            handle = tw.get("account_handle", "")
            role = tw.get("account_role", "")
            text = tw.get("text", "")
            url = tw.get("url", "")
            ts = tw.get("timestamp", "")[:16].replace("T", " ")
            
            badges = []
            if tw.get("is_retweet"):
                badges.append("🔁")
            if tw.get("is_quote_tweet"):
                badges.append("💬")
            badge_str = f" [{' '.join(badges)}]" if badges else ""
            
            # Clean text: remove @ and URLs from display
            display_text = text
            display_text = display_text.replace("@", "")
            display_text = display_text.replace("https://", "").replace("http://", "")
            
            lines.append(f"- **@{handle}** ({role}){badge_str} — [{ts}]({url})")
            lines.append(f"  > {display_text[:220]}{'...' if len(display_text) > 220 else ''}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Standalone Twitter collector")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours")
    parser.add_argument("--chains", type=str, default="", help="Comma-separated chain names")
    parser.add_argument("--telegram", action="store_true", help="Send digest via TelegramSender")
    parser.add_argument("--json-only", action="store_true", help="Skip Telegram, save files only")
    parser.add_argument("--dry-run", action="store_true", help="Test auth without saving")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers")
    parser.add_argument("--batches", type=int, default=10, help="Number of batches")
    args = parser.parse_args()

    hours = args.hours
    chains_filter = [c.strip() for c in args.chains.split(",")] if args.chains else []
    workers = max(1, args.workers)
    num_batches = max(1, args.batches)

    logger.info("=" * 60)
    logger.info("Twitter Standalone Collector")
    logger.info(f"Lookback: {hours}h | Workers: {workers} | Batches: {num_batches}")
    logger.info("=" * 60)

    # Load accounts
    import yaml
    config_path = REPO_ROOT / "config" / "twitter_accounts.yaml"
    if not config_path.exists():
        logger.error("No twitter_accounts.yaml found")
        return
    
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    accounts = data.get("twitter_accounts", {})
    
    if not accounts:
        logger.error("No chains configured")
        return

    # Filter to requested chains
    if chains_filter:
        accounts = {k: v for k, v in accounts.items() if k in chains_filter}
        if not accounts:
            logger.error(f"No matching chains for: {chains_filter}")
            return

    # Build flat handle list
    flat_handles = []
    for chain_name, cfg in accounts.items():
        for h in cfg.get("official", []) + cfg.get("contributors", []):
            flat_handles.append((chain_name, h))
    
    if not flat_handles:
        logger.error("No handles found")
        return
    
    logger.info(f"Total handles to scrape: {len(flat_handles)}")

    # DRY RUN
    if args.dry_run:
        logger.info("DRY RUN — testing authentication...")
        try:
            collector = TwitterCollector(standalone_mode=True, lookback_hours=hours)
            collector._start_browser()
            page = collector._context.new_page()
            test_url = "https://x.com/solana"
            page.goto(test_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(4)
            articles = page.query_selector_all('article[data-testid="tweet"]')
            logger.info(f"DRY RUN success: {len(articles)} articles visible on {test_url}")
            page.close()
            collector._cleanup()
            logger.info(f"DRY RUN complete — auth works, {len(articles)} articles found")
        except Exception as e:
            logger.error(f"DRY RUN failed: {e}")
        return

    # Split into batches
    batch_size = max(1, len(flat_handles) // num_batches)
    if batch_size < 1:
        batch_size = 1
    batches = [flat_handles[i:i + batch_size] for i in range(0, len(flat_handles), batch_size)]
    logger.info(f"Split into {len(batches)} batches (size ~{batch_size})")

    # Run batches in parallel
    logger.info(f"Running {len(batches)} batches with {workers} worker(s)...")
    total_collected = 0
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_batch, i, batch, hours) for i, batch in enumerate(batches)]
        for future in futures:
            try:
                total_collected += future.result()
            except Exception as e:
                logger.error(f"Batch worker error: {e}")

    logger.info(f"=== Total tweets collected: {total_collected} ===")

    # Merge and generate digest
    all_tweets = _merge_batches()
    
    if all_tweets:
        logger.info(f"Merged {len(all_tweets)} unique tweets from all batches")
        
        # Generate digest
        digest = _build_digest(all_tweets)
        
        # Save JSON summary
        summary_dir = REPO_ROOT / "storage" / "twitter" / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        json_path = summary_dir / f"standalone_summary_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"tweets": all_tweets, "digest": digest}, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON summary saved: {json_path}")
        
        # Append monthly markdown
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        md_path = summary_dir / f"twitter_summary_{month_key}.md"
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(f"\n## Standalone Run @ {ts}\n\n")
            f.write(digest + "\n")
        logger.info(f"Markdown summary appended: {md_path}")
        
        # Optional Telegram delivery
        if args.telegram and not args.json_only:
            logger.info("Sending to Telegram...")
            try:
                from output.telegram_sender import TelegramSender
                sender = TelegramSender()
                sent = sender.send(digest)
                logger.info(f"Telegram delivered: {sent}")
            except Exception as e:
                logger.error(f"Telegram failed: {e}")
    else:
        logger.warning("No tweets collected in any batch")


if __name__ == "__main__":
    main()
