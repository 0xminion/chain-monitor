#!/usr/bin/env python3
"""
Twitter/X standalone collector — run independently of daily digest cycle.

Usage:
    python scripts/run_twitter_standalone.py --hours 48 --chains monad,solana
    python scripts/run_twitter_standalone.py --hours 24 --all --telegram
    python scripts/run_twitter_standalone.py --json-only

Features:
- Deduplication: OFF (intentional — each standalone run is independent).
- Telegram delivery: optional (--telegram flag).
- Persistence: raw JSON + monthly Markdown summary (always writes).
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Set up repo root path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("twitter-standalone")

from collectors.twitter_collector import TwitterCollector
from processors.signal import Signal
from processors.scoring import SignalScorer
from output.telegram_sender import TelegramSender


def parse_args():
    parser = argparse.ArgumentParser(description="Twitter/X standalone collector")
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours (default: 24)",
    )
    parser.add_argument(
        "--chains",
        type=str,
        default="",
        help="Comma-separated chain names to monitor. Default: all",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Monitor all chains (default behavior, explicit flag for clarity)",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Send output via Telegram bot",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only write JSON/Markdown output, skip Telegram",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run collection but do not send Telegram or write files",
    )
    return parser.parse_args()


def format_telegram_digest(tweets: list[dict]) -> str:
    """Format tweets into a Telegram-ready Markdown digest."""
    if not tweets:
        return "🐦 Twitter Standalone — No tweets found in window."

    lines = [
        "🐦 *Twitter Standalone Digest*",
        f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"*Tweets collected:* {len(tweets)}\n",
    ]

    # Group by chain
    by_chain: dict[str, list[dict]] = {}
    for t in tweets:
        chain = t.get("chain", "unknown")
        by_chain.setdefault(chain, []).append(t)

    for chain, chain_tweets in sorted(by_chain.items()):
        lines.append(f"\n🔗 *{chain.upper()}*")
        for t in chain_tweets[:10]:  # Cap at 10 per chain for digest
            handle = t.get("account_handle", "")
            role = t.get("account_role", "")
            role_badge = "✅" if role == "official" else "👤"
            ts = t.get("timestamp", "")[:10]
            text = t.get("text", "")
            is_rt = t.get("is_retweet", False)
            is_q = t.get("is_quote_tweet", False)
            url = t.get("url", "")

            rt_badge = "🔁 " if is_rt else ""
            q_badge = "💬 " if is_q else ""
            badge = f"{role_badge} {rt_badge}{q_badge}".strip()

            safe_text = text[:240].replace("*", "").replace("_", "")
            if len(text) > 240:
                safe_text += "..."

            lines.append(
                f"• [{ts}] {badge} [@{handle}](https://x.com/{handle})\n"
                f"  > {safe_text}\n"
                f"  [Open tweet]({url})"
            )

        if len(chain_tweets) > 10:
            lines.append(f"  _... and {len(chain_tweets) - 10} more_")

    return "\n".join(lines)


def score_tweets_as_signals(tweets: list[dict]) -> list[Signal]:
    """Score tweets using the pipeline's SignalScorer. Returns Signals for reference."""
    scorer = SignalScorer()
    signals = []

    for t in tweets:
        chain = t.get("chain", "unknown")
        text = t.get("text", "").strip()
        is_rt = t.get("is_retweet", False)
        is_q = t.get("is_quote_tweet", False)
        quoted_text = t.get("quoted_text", "")
        handle = t.get("account_handle", "")
        role = t.get("account_role", "official")
        reliability = float(t.get("account_reliability", 0.75))
        url = t.get("url", "")
        ts = t.get("timestamp", "")
        original_author = t.get("original_author", "")

        # Build description
        if is_rt and original_author:
            description = f"@{handle} reposted @{original_author}: {text}"
        elif is_q and quoted_text:
            description = f"@{handle} quoted: {text} — Quoting: {quoted_text}"
        else:
            description = text

        # Boost reliability for RTs of official accounts
        if is_rt and role != "official":
            from collectors.twitter_collector import TwitterCollector as TC
            accounts = TC._accounts if hasattr(TC, '_accounts') else {}
            chain_cfg = accounts.get(chain, {})
            official_handles = {
                h["handle"].lstrip("@").lower()
                for h in chain_cfg.get("official", [])
            }
            if original_author.lower() in official_handles:
                reliability = max(reliability, 0.95)

        evidence = {
            "tweet_id": t.get("tweet_id"),
            "url": url,
            "author": handle,
            "role": role,
            "timestamp": ts,
            "likes": t.get("likes", 0),
            "retweets": t.get("retweets", 0),
        }

        event = {
            "chain": chain,
            "category": "NEWS",  # categorizer will refine
            "description": description[:500],
            "source": "twitter",
            "reliability": reliability,
            "evidence": evidence,
            "timestamp": ts or datetime.now(timezone.utc).isoformat(),
            "has_official_source": role == "official" or reliability >= 0.95,
        }

        signal = scorer.score(event)
        signals.append(signal)

    return signals


def main():
    args = parse_args()
    logger.info("=" * 50)
    logger.info("Twitter/X Standalone Collector")
    logger.info(f"Lookback: {args.hours}h")
    logger.info(f"Chains: {args.chains or 'ALL'}")
    logger.info(f"Telegram: {args.telegram}")
    logger.info("=" * 50)

    # Build collector
    collector = TwitterCollector(standalone_mode=True, lookback_hours=args.hours)

    # If --chains specified, filter the accounts before running
    if args.chains:
        selected = {c.strip().lower() for c in args.chains.split(",")}
        collector._accounts = {
            k: v for k, v in collector._accounts.items()
            if k.lower() in selected
        }
        logger.info(f"Filtered to {len(collector._accounts)} chains")

    if not collector._accounts:
        logger.error("No chains matched. Exiting.")
        sys.exit(1)

    # Run collection (raw tweets, no dedup)
    raw_tweets = collector.collect_raw()
    logger.info(f"Collected {len(raw_tweets)} tweets")

    if not raw_tweets:
        logger.info("No tweets found — nothing to do.")
        if args.telegram and not args.dry_run:
            sender = TelegramSender()
            sender.send_sync("🐦 Twitter Standalone — No tweets found.")
        return

    # Score signals (reference, not used for dedup)
    signals = score_tweets_as_signals(raw_tweets)
    high_priority = [s for s in signals if s.priority_score >= 8]
    logger.info(f"Signals scored: {len(signals)}, high priority (>=8): {len(high_priority)}")

    # Write standalone JSON summary
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
                    "chains": list(collector._accounts.keys()),
                    "tweet_count": len(raw_tweets),
                    "tweets": raw_tweets,
                    "signals": [s.to_dict() for s in signals],
                    "high_priority_count": len(high_priority),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"Standalone summary written: {summary_path}")

    # Telegram delivery (optional; can be triggered independently)
    if args.telegram and not args.json_only and not args.dry_run:
        digest = format_telegram_digest(raw_tweets)
        sender = TelegramSender()
        success = sender.send_sync(digest)
        logger.info(f"Telegram sent: {success}")

    logger.info("Standalone run complete.")


if __name__ == "__main__":
    main()
