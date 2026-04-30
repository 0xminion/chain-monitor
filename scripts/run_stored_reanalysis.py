#!/usr/bin/env python3
"""Run collected twitter data through v2.0 chain analysis and summary engine."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from processors.pipeline_types import RawEvent, ChainDigest
from processors.chain_analyzer import analyze_chain
from processors.summary_engine import synthesize_digest


def tweet_to_raw_event(tweet: dict) -> RawEvent:
    """Convert a collected tweet dict into a RawEvent for the pipeline."""
    text = tweet.get("text", "")
    is_rt = tweet.get("is_retweet", False)
    is_q = tweet.get("is_quote_tweet", False)
    quoted = tweet.get("quoted_text", "")
    orig = tweet.get("original_author", "")
    handle = tweet.get("account_handle", "")
    role = tweet.get("account_role", "official")
    reliability = float(tweet.get("account_reliability", 0.75))

    if is_rt and orig:
        desc = f"@{handle} reposted @{orig}: {text}"
    elif is_q and quoted:
        desc = f"@{handle} quoted: {text} — Quoting: {quoted}"
    else:
        desc = text

    return RawEvent(
        chain=str(tweet.get("chain", "unknown")).lower(),
        category="NEWS",
        subcategory="twitter",
        description=desc,
        source="twitter",
        reliability=reliability,
        evidence={
            **tweet.get("evidence", {}),
            "url": tweet.get("url", ""),
            "tweet_url": tweet.get("url", ""),
            "author": handle,
            "role": role,
            "timestamp": tweet.get("timestamp", ""),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
        },
        raw_url=tweet.get("url") or tweet.get("tweet_url"),
        published_at=None,
    )


async def main():
    # Aggregate ALL tweets from today's raw files AND the latest standalone summary
    summary_dir = REPO_ROOT / "storage" / "twitter" / "summaries"
    raw_dir = REPO_ROOT / "storage" / "twitter" / "raw"

    all_tweets = []
    seen_ids = set()

    # 1. Load latest standalone summary
    summary_files = sorted(summary_dir.glob("standalone_summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if summary_files:
        with open(summary_files[0]) as f:
            data = json.load(f)
        for t in data.get("tweets", []):
            tid = t.get("tweet_id") or t.get("url", "")
            if tid not in seen_ids:
                seen_ids.add(tid)
                all_tweets.append(t)
        print(f"Loaded {len(data.get('tweets', []))} tweets from {summary_files[0].name}")

    # 2. Load ALL raw files from the last 24 hours
    import glob
    from datetime import datetime, timezone, timedelta
    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
    all_raw_files = glob.glob(str(raw_dir / "tweets_*.json"))
    recent_raw_files = [f for f in all_raw_files if os.path.getmtime(f) >= cutoff_time]
    raw_files = sorted(recent_raw_files, key=lambda p: os.path.getmtime(p), reverse=True)
    raw_added = 0
    for rf in raw_files:
        with open(rf) as f:
            data = json.load(f)
        tweets = data if isinstance(data, list) else data.get("tweets", [])
        for t in tweets:
            tid = t.get("tweet_id") or t.get("url", "")
            if tid not in seen_ids:
                seen_ids.add(tid)
                all_tweets.append(t)
                raw_added += 1
    print(f"Added {raw_added} additional tweets from {len(raw_files)} raw files")
    print(f"Total unique tweets: {len(all_tweets)}\n")

    if not all_tweets:
        print("No tweets found anywhere. Run the scraper first.")
        return

    # Convert tweets to RawEvents
    events = [tweet_to_raw_event(t) for t in all_tweets]

    # Group by chain (only chains WITH tweets)
    by_chain = {}
    for ev in events:
        by_chain.setdefault(ev.chain, []).append(ev)

    print(f"Events grouped into {len(by_chain)} chains: {sorted(by_chain.keys())}\n")

    # Stage 4: Chain analysis — agent-native deterministic heuristics (no LLM)
    print("Running chain-level analysis (agent-native deterministic)...")

    from processors.chain_analyzer import analyze_all_chains
    digests = await analyze_all_chains(by_chain, client=None, max_concurrent=5)

    for d in sorted(digests, key=lambda x: -x.priority_score):
        print(f"  {d.chain}: priority={d.priority_score}, topic={d.dominant_topic[:50]}")
    print()

    # Stage 5: Synthesize final digest
    print("Synthesizing final digest via v2.0 summary engine...\n")
    digest = await synthesize_digest(
        digests=digests,
        client=None,
        source_health={"twitter": {"status": "healthy", "tweets": len(all_tweets)}},
    )

    print("=" * 60)
    print(digest)
    print("=" * 60)

    # Save
    out_path = REPO_ROOT / "storage" / "twitter" / "summaries" / f"v2_digest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    with open(out_path, "w") as f:
        f.write(digest)
    print(f"\nDigest saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
