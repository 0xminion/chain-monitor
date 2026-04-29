#!/usr/bin/env python3
"""Quick smoke test of v2 digest pipeline on chains with actual tweets only."""
import asyncio, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from processors.pipeline_types import RawEvent, ChainDigest
from processors.chain_analyzer import analyze_chain
from processors.summary_engine import synthesize_digest
from processors.llm_client import LLMClient


def tweet_to_raw_event(tweet: dict) -> RawEvent:
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
    summary_path = REPO_ROOT / "storage" / "twitter" / "summaries" / "standalone_summary_20260429_130256.json"
    with open(summary_path) as f:
        data = json.load(f)
    tweets = data.get("tweets", [])
    print(f"Loaded {len(tweets)} tweets from {summary_path.name}\n")

    events = [tweet_to_raw_event(t) for t in tweets]
    by_chain = {}
    for ev in events:
        by_chain.setdefault(ev.chain, []).append(ev)

    # Only chains WITH tweets
    active_chains = {c: evs for c, evs in by_chain.items() if len(evs) > 0}
    print(f"Active chains: {sorted(active_chains.keys())}\n")

    client = LLMClient(model='gemma4:31b-cloud', timeout=120.0)
    digests = []
    for chain, evs in sorted(active_chains.items()):
        print(f"Analyzing {chain} ({len(evs)} tweets)...")
        try:
            d = await asyncio.wait_for(analyze_chain(chain, evs, client=client), timeout=180.0)
            digests.append(d)
            print(f"  priority={d.priority_score}, topic={d.dominant_topic[:60]}")
        except asyncio.TimeoutError:
            print(f"  TIMEOUT on {chain}, skipping")
        except Exception as exc:
            print(f"  ERROR on {chain}: {exc}")

    print(f"\nSynthesizing digest from {len(digests)} chain analyses...\n")
    digest = await synthesize_digest(
        digests=digests,
        client=client,
        source_health={"twitter": {"status": "healthy", "tweets": len(tweets)}},
    )

    print("=" * 60)
    print(digest)
    print("=" * 60)

    out_path = REPO_ROOT / "storage" / "twitter" / "summaries" / f"v2_digest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    with open(out_path, "w") as f:
        f.write(digest)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
