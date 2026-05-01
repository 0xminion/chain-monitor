"""Twitter standalone bridge — reconnects standalone Twitter collection to the daily pipeline.

Loads recent standalone Twitter data from storage/twitter/raw/ instead of
re-running browser collection inline. Falls back to inline collection if no
recent standalone data exists.

Usage in pipeline (run_all_chains.py):
    from collectors.twitter_standalone_bridge import load_recent_standalone_tweets
    twitter_events = load_recent_standalone_tweets(lookback_hours=24)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from processors.pipeline_types import RawEvent

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
RAW_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "raw"


def _tweet_to_raw_event(tweet: dict) -> Optional[RawEvent]:
    """Convert a standalone tweet dict to a RawEvent for the pipeline."""
    chain = tweet.get("chain", "unknown")
    handle = tweet.get("account_handle", "")
    text = tweet.get("text", "").strip()
    url = tweet.get("url", "")
    ts = tweet.get("timestamp", "")
    role = tweet.get("account_role", "unknown")
    reliability = tweet.get("account_reliability", 0.75)
    is_rt = tweet.get("is_retweet", False)
    is_q = tweet.get("is_quote_tweet", False)
    quoted_text = tweet.get("quoted_text", "")
    original_author = tweet.get("original_author", "")

    if not text and not url:
        return None

    # Build description
    if is_rt and original_author:
        description = f"@{handle} reposted @{original_author}: {text}"
    elif is_q and quoted_text:
        description = f"@{handle} quoted: {text} — Quoting: {quoted_text}"
    else:
        description = text

    evidence = {
        "tweet_id": tweet.get("tweet_id"),
        "url": url,
        "author": handle,
        "role": role,
        "timestamp": ts,
        "likes": tweet.get("likes", 0),
        "retweets": tweet.get("retweets", 0),
        "is_retweet": is_rt,
        "is_quote": is_q,
        "original_author": original_author,
        "quoted_text": quoted_text,
        "media_urls": tweet.get("media_urls", []),
    }

    # Determine category based on content hints
    category = "NEWS"
    subcategory = "general"

    # Boost official accounts to VISIBILITY
    if role == "official":
        category = "VISIBILITY"
        subcategory = "keynote" if "conference" in text.lower() or " summit" in text.lower() else "general"

    return RawEvent(
        chain=chain,
        category=category,
        subcategory=subcategory,
        description=description[:500],
        source="twitter",
        reliability=float(reliability),
        evidence=evidence,
        raw_url=url if url and url.startswith("http") else None,
        published_at=_parse_timestamp(ts) if ts else None,
    )


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO timestamp string."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def load_recent_standalone_tweets(
    lookback_hours: int = 24,
    max_files: int = 5,
) -> list[RawEvent]:
    """Load recent standalone Twitter collection data and convert to RawEvents.

    Args:
        lookback_hours: Only load tweets newer than this many hours ago.
        max_files: Maximum number of recent JSON files to load.

    Returns:
        List of RawEvent objects ready for the pipeline.
    """
    if not RAW_OUT_DIR.exists():
        logger.info("[twitter-bridge] No standalone data directory found")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    # Find recent JSON files
    files = sorted(
        RAW_OUT_DIR.glob("tweets_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_files]

    if not files:
        logger.info("[twitter-bridge] No standalone tweet files found")
        return []

    all_tweets: list[dict] = []
    for f in files:
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                logger.debug(f"[twitter-bridge] Skipping stale file: {f.name}")
                continue
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, list):
                all_tweets.extend(data)
            elif isinstance(data, dict) and "tweets" in data:
                all_tweets.extend(data["tweets"])
            logger.info(f"[twitter-bridge] Loaded {f.name}: {len(data) if isinstance(data, list) else len(data.get('tweets', []))} tweets")
        except Exception as e:
            logger.warning(f"[twitter-bridge] Failed to load {f}: {e}")

    # Filter by timestamp
    fresh_tweets = []
    for t in all_tweets:
        ts = _parse_timestamp(t.get("timestamp", ""))
        if ts and ts >= cutoff:
            fresh_tweets.append(t)

    # Convert to RawEvents
    events = []
    for t in fresh_tweets:
        ev = _tweet_to_raw_event(t)
        if ev:
            events.append(ev)

    logger.info(
        f"[twitter-bridge] {len(events)} RawEvents from "
        f"{len(fresh_tweets)} fresh tweets ({len(all_tweets)} total loaded)"
    )
    return events


# Convenience: callable interface matching BaseCollector.collect()
class TwitterStandaloneBridge:
    """Drop-in replacement for TwitterCollector that uses standalone data."""

    def __init__(self, lookback_hours: int = 24):
        self.lookback_hours = lookback_hours
        self.name = "twitter_standalone"

    def collect(self) -> list[RawEvent]:
        return load_recent_standalone_tweets(self.lookback_hours)
