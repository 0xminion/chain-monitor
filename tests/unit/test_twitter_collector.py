"""Unit tests for TwitterCollector.

Tests:
- Config loading
- Noise filtering
- Tweet-to-event conversion
- Reliability boost for RTs of official accounts
- Markdown summary formatting
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from collectors.twitter_collector import TwitterCollector
from processors.categorizer import EventCategorizer


@pytest.fixture
def sample_tweets():
    return [
        {
            "tweet_id": "180000000000000001",
            "url": "https://x.com/monad_xyz/status/180000000000000001",
            "timestamp": "2026-04-21T14:30:00.000Z",
            "text": "Mainnet launch is next week! Exciting times for Monad.",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 1200,
            "retweets": 340,
            "replies": 89,
            "media_urls": [],
            "chain": "monad",
            "account_handle": "monad_xyz",
            "account_role": "official",
            "account_name": "Monad",
            "account_reliability": 0.95,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "tweet_id": "180000000000000002",
            "url": "https://x.com/keoneHD/status/180000000000000002",
            "timestamp": "2026-04-21T16:00:00.000Z",
            "text": "gm builders",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 45,
            "retweets": 2,
            "replies": 1,
            "media_urls": [],
            "chain": "monad",
            "account_handle": "keoneHD",
            "account_role": "contributor",
            "account_name": "Keone Hon",
            "account_reliability": 0.90,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "tweet_id": "180000000000000003",
            "url": "https://x.com/keoneHD/status/180000000000000003",
            "timestamp": "2026-04-21T18:00:00.000Z",
            "text": "RT @monad_xyz: Mainnet launch is next week!",
            "is_retweet": True,
            "original_author": "monad_xyz",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 300,
            "retweets": 120,
            "replies": 15,
            "media_urls": [],
            "chain": "monad",
            "account_handle": "keoneHD",
            "account_role": "contributor",
            "account_name": "Keone Hon",
            "account_reliability": 0.90,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "tweet_id": "180000000000000004",
            "url": "https://x.com/monad_xyz/status/180000000000000004",
            "timestamp": "2026-04-21T20:00:00.000Z",
            "text": "Big news: we're partnering with Protocol X for cross-chain integration.",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 800,
            "retweets": 200,
            "replies": 56,
            "media_urls": [],
            "chain": "monad",
            "account_handle": "monad_xyz",
            "account_role": "official",
            "account_name": "Monad",
            "account_reliability": 0.95,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "tweet_id": "180000000000000005",
            "url": "https://x.com/solana/status/180000000000000005",
            "timestamp": "2026-04-21T10:00:00.000Z",
            "text": "Excited to keynote at Breakpoint 2026! See you there.",
            "is_retweet": False,
            "original_author": "",
            "is_quote_tweet": False,
            "quoted_text": "",
            "likes": 2500,
            "retweets": 600,
            "replies": 130,
            "media_urls": [],
            "chain": "solana",
            "account_handle": "solana",
            "account_role": "official",
            "account_name": "Solana",
            "account_reliability": 0.95,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
    ]


class TestTwitterCollector:
    def test_tweets_to_events_basic(self, sample_tweets):
        collector = TwitterCollector(standalone_mode=True, lookback_hours=48)
        # Mock accounts so _tweets_to_events doesn't fail on empty cfg
        collector._accounts = {
            "monad": {
                "official": [{"handle": "@monad_xyz", "name": "Monad", "reliability": 0.95}],
                "contributors": [{"handle": "@keoneHD", "name": "Keone Hon", "role": "founder", "reliability": 0.90}],
            },
            "solana": {
                "official": [{"handle": "@solana", "name": "Solana", "reliability": 0.95}],
                "contributors": [],
            },
        }

        events = collector._tweets_to_events(sample_tweets)
        assert len(events) == len(sample_tweets)

        # Check official event has high reliability
        official_event = events[0]
        assert official_event["chain"] == "monad"
        assert official_event["reliability"] == 0.95
        assert official_event["has_official_source"] is True
        assert "Mainnet launch is next week" in official_event["description"]

    def test_rt_reliability_boost(self, sample_tweets):
        """RTs of official accounts get reliability bumped to official level."""
        collector = TwitterCollector(standalone_mode=True, lookback_hours=48)
        collector._accounts = {
            "monad": {
                "official": [{"handle": "@monad_xyz", "name": "Monad", "reliability": 0.95}],
                "contributors": [{"handle": "@keoneHD", "name": "Keone Hon", "role": "founder", "reliability": 0.90}],
            },
        }

        rt_tweet = sample_tweets[2]  # Keone RT of monad_xyz
        events = collector._tweets_to_events([rt_tweet])
        assert len(events) == 1
        assert events[0]["reliability"] == 0.95
        assert "monad_xyz" in events[0]["description"]

    def test_noise_filter(self, sample_tweets):
        """The categorizer should filter 'gm builders' as noise."""
        c = EventCategorizer()
        gm_event = {
            "chain": "monad",
            "category": "NEWS",
            "description": "gm builders",
            "source": "twitter",
            "source_name": "Twitter (@keoneHD)",
            "evidence": {"text": "gm builders"},
        }
        result = c.categorize(gm_event)
        assert result["category"] == "NOISE"
        assert result.get("_filtered_twitter_noise") is True

    def test_tech_event_detection(self, sample_tweets):
        """Mainnet launch tweet should be categorized as TECH_EVENT."""
        c = EventCategorizer()
        event = {
            "chain": "monad",
            "category": "NEWS",
            "description": "Mainnet launch is next week! Exciting times for Monad.",
            "source": "twitter",
            "source_name": "Twitter (@monad_xyz)",
            "evidence": {"text": "Mainnet launch is next week! Exciting times for Monad."},
        }
        result = c.categorize(event)
        assert result["category"] == "TECH_EVENT"

    def test_partnership_detection(self, sample_tweets):
        """Partnership tweet should be categorized as PARTNERSHIP."""
        c = EventCategorizer()
        event = {
            "chain": "monad",
            "category": "NEWS",
            "description": "Big news: we're partnering with Protocol X for cross-chain integration.",
            "source": "twitter",
            "source_name": "Twitter (@monad_xyz)",
            "evidence": {"text": "Big news: we're partnering with Protocol X for cross-chain integration."},
        }
        result = c.categorize(event)
        assert result["category"] == "PARTNERSHIP"

    def test_visibility_detection(self, sample_tweets):
        """Keynote tweet should be categorized as VISIBILITY."""
        c = EventCategorizer()
        event = {
            "chain": "solana",
            "category": "NEWS",
            "description": "Excited to keynote at Breakpoint 2026! See you there.",
            "source": "twitter",
            "source_name": "Twitter (@solana)",
            "evidence": {"text": "Excited to keynote at Breakpoint 2026! See you there."},
        }
        result = c.categorize(event)
        assert result["category"] == "VISIBILITY"


def test_load_accounts():
    collector = TwitterCollector(standalone_mode=True, lookback_hours=48)
    assert "monad" in collector._accounts
    assert "solana" in collector._accounts
    monad_official = collector._accounts["monad"]["official"]
    assert len(monad_official) >= 1
    assert monad_official[0]["handle"] == "monad_xyz"


class TestMarkdownSummary:
    def test_append_summary(self, tmp_path):
        from collectors.twitter_collector import TwitterCollector
        collector = TwitterCollector(standalone_mode=True, lookback_hours=48)
        summary_path = tmp_path / "test_summary.md"
        tweets = [
            {
                "chain": "monad",
                "account_handle": "monad_xyz",
                "account_role": "official",
                "timestamp": "2026-04-21T14:30:00.000Z",
                "text": "Mainnet launch!",
                "is_retweet": False,
                "is_quote_tweet": False,
                "url": "https://x.com/monad_xyz/status/1",
            }
        ]
        now = datetime.now(timezone.utc)
        collector._append_summary_md(summary_path, tweets, now)
        content = summary_path.read_text()
        assert "monad" in content
        assert "Mainnet launch" in content
        assert "https://x.com/monad_xyz/status/1" in content
