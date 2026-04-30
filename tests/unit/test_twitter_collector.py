"""Unit tests for TwitterCollector — agent-native.

Tests collector side only. Semantic enrichment deferred to running agent.
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
            "likes": 10,
            "retweets": 5,
            "replies": 2,
            "media_urls": [],
        }
    ]


class TestTwitterCollectorConfig:
    def test_loads_without_crash(self):
        tc = TwitterCollector(standalone_mode=False)
        assert tc is not None


class TestTweetToEvent:
    def test_tweet_to_event_basic(self):
        tc = TwitterCollector()
        tc._accounts = {"monad": {"official": [{"handle": "@monad_xyz", "name": "Monad", "reliability": 0.9}]}}
        tweet = {
            "tweet_id": "180000000000000001",
            "url": "https://x.com/monad_xyz/status/180000000000000001",
            "timestamp": "2026-04-21T14:30:00.000Z",
            "text": "Mainnet launch next week",
            "is_retweet": False,
            "is_quote_tweet": False,
            "quoted_text": "",
            "original_author": "",
            "account_handle": "monad_xyz",
            "account_role": "official",
            "account_reliability": 0.9,
            "account_name": "Monad",
            "chain": "monad",
            "likes": 10,
            "retweets": 5,
        }
        events = tc._tweets_to_events([tweet])
        assert len(events) == 1
        assert events[0]["source"] == "twitter"
        assert "Mainnet" in events[0]["description"]

    def test_retweet_boosts_reliability(self):
        tc = TwitterCollector()
        tc._accounts = {"monad": {"official": [{"handle": "@monad_xyz", "name": "Monad", "reliability": 0.9}]}}
        tweet = {
            "tweet_id": "180000000000000001",
            "url": "https://x.com/monad_xyz/status/180000000000000001",
            "timestamp": "2026-04-21T14:30:00.000Z",
            "text": "Exciting",
            "is_retweet": True,
            "is_quote_tweet": False,
            "quoted_text": "",
            "original_author": "monad_xyz",
            "account_handle": "contributor",
            "account_role": "contributor",
            "account_reliability": 0.6,
            "account_name": "Contributor",
            "chain": "monad",
            "likes": 5,
            "retweets": 3,
        }
        events = tc._tweets_to_events([tweet])
        assert events[0]["reliability"] >= 0.95

    def test_quotetweet_builds_description(self):
        tc = TwitterCollector()
        tweet = {
            "tweet_id": "180000000000000001",
            "url": "https://x.com/monad_xyz/status/180000000000000001",
            "timestamp": "2026-04-21T14:30:00.000Z",
            "text": "This is important",
            "is_retweet": False,
            "is_quote_tweet": True,
            "quoted_text": "Original opinion",
            "original_author": "",
            "account_handle": "monad_xyz",
            "account_role": "official",
            "account_reliability": 0.9,
            "account_name": "Monad",
            "chain": "monad",
            "likes": 10,
            "retweets": 5,
        }
        events = tc._tweets_to_events([tweet])
        assert "quoting" in events[0]["description"].lower()


class TestTwitterCollector:
    def test_agent_native_pass_through(self, sample_tweets):
        """Agent-native: categorizer passes through, agent classifies."""
        c = EventCategorizer()
        event = {
            "chain": "monad",
            "category": "NEWS",
            "description": "Mainnet launch is next week!",
            "source": "twitter",
            "evidence": {"text": "Mainnet launch is next week!"},
        }
        result = c.categorize(event)
        assert result["category"] == "NEWS"  # agent-native: category preserved
        assert result["subcategory"] == "general"

    def test_agent_native_preserves_existing(self):
        """If a category is already set, it's preserved."""
        c = EventCategorizer()
        event = {
            "chain": "solana",
            "category": "VISIBILITY",
            "description": "Excited to keynote at Breakpoint 2026!",
            "source": "twitter",
            "evidence": {"text": "Excited to keynote at Breakpoint 2026!"},
        }
        result = c.categorize(event)
        assert result["category"] == "VISIBILITY"  # preserved

    def test_agent_native_invalid_normalized(self):
        """Invalid categories get normalized."""
        c = EventCategorizer()
        event = {
            "chain": "ethereum",
            "category": "UNKNOWN_CAT",
            "description": "Something",
            "source": "twitter",
            "evidence": {},
        }
        result = c.categorize(event)
        assert result["category"] == "NEWS"  # normalized


def test_load_accounts():
    collector = TwitterCollector(standalone_mode=True, lookback_hours=48)
    accounts = collector._accounts
    assert isinstance(accounts, dict)


def test_standalone_defaults():
    tc = TwitterCollector(standalone_mode=True, lookback_hours=24)
    assert tc.lookback_hours == 24


def test_collected_event_reliability():
    tc = TwitterCollector()
    tweet = {
        "tweet_id": "180000000000000002",
        "url": "https://x.com/test/status/180000000000000002",
        "timestamp": "2026-04-21T14:30:00.000Z",
        "text": "Test tweet",
        "is_retweet": False,
        "is_quote_tweet": False,
        "quoted_text": "",
        "original_author": "",
        "account_handle": "test_account",
        "account_role": "official",
        "account_reliability": 0.9,
        "account_name": "Test",
        "chain": "solana",
        "likes": 5,
        "retweets": 2,
    }
    result = tc._tweets_to_events([tweet])
    assert len(result) == 1
    assert 0 <= result[0]["reliability"] <= 1
