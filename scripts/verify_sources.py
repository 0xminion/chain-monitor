"""Verify data sources — run during setup to check all endpoints."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import feedparser
from config.loader import get_chains, get_sources


def check_url(url: str, name: str) -> bool:
    """Check if URL is accessible."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "ChainMonitor/1.0"})
        if resp.status_code == 200:
            print(f"  ✓ {name}: {url[:60]}...")
            return True
        else:
            print(f"  ⚠ {name}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return False


def check_rss(url: str, name: str) -> bool:
    """Check if RSS feed is valid."""
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            print(f"  ✓ {name}: {len(feed.entries)} entries")
            return True
        elif feed.bozo:
            print(f"  ⚠ {name}: parse error — {feed.bozo_exception}")
            return False
        else:
            print(f"  ⚠ {name}: valid but empty")
            return True
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return False


def verify_defillama_slugs():
    """Verify DefiLlama chain slugs exist."""
    print("\n🔗 DefiLlama Chain Slugs:")
    try:
        resp = requests.get("https://api.llama.fi/chains", timeout=15)
        chains = resp.json()
        available = {c["name"].lower(): c for c in chains}

        for chain_name, config in get_chains().items():
            slug = config.get("defillama_slug")
            if not slug:
                print(f"  — {chain_name}: no slug (not tracked)")
                continue

            found = any(slug.lower() in k or k in slug.lower() for k in available.keys())
            if found:
                print(f"  ✓ {chain_name}: '{slug}' found")
            else:
                print(f"  ✗ {chain_name}: '{slug}' NOT FOUND in DefiLlama")
    except Exception as e:
        print(f"  ✗ Failed to fetch DefiLlama chains: {e}")


def verify_rss_feeds():
    """Verify RSS feeds for chains."""
    print("\n📡 Chain RSS Feeds:")
    for chain_name, config in get_chains().items():
        rss = config.get("blog_rss")
        if rss:
            check_rss(rss, chain_name)


def verify_global_feeds():
    """Verify global RSS feeds."""
    sources = get_sources()
    for category, feeds in sources.get("rss_feeds", {}).items():
        print(f"\n📰 {category.title()} Feeds:")
        for feed in feeds:
            check_rss(feed["url"], feed["name"])


def main():
    print("🔍 Chain Monitor — Source Verification")
    print("=" * 50)
    verify_defillama_slugs()
    verify_rss_feeds()
    verify_global_feeds()
    print("\n✅ Verification complete")


if __name__ == "__main__":
    main()
