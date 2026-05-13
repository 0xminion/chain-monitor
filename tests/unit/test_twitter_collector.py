"""Unit tests for the new composable TwitterCollector (collectors/twitter/collector.py)."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collectors.twitter.collector import (
    TwitterCollector,
    RAW_OUT_DIR,
    SUMMARY_OUT_DIR,
)


@pytest.fixture
def collector():
    """Create a collector with a mock provider."""
    return TwitterCollector(lookback_hours=24)


@pytest.fixture
def sample_tweets():
    """Sample tweets in the new internal format (from SurplusTwitterProvider etc)."""
    return [
        {
            "id": "2054368886603276574",
            "handle": "jessepollak",
            "text": "x402 now supports batched settlement. This unlocks many tiny payments.",
            "created_at": "2026-05-13T02:37:18.000Z",
            "is_retweet": False,
            "retweeted_handle": None,
            "likes": 450,
            "retweets": 120,
            "replies": 35,
            "chain": "base",
            "account_role": "official",
            "account_reliability": 0.95,
            "account_name": "Jesse Pollak",
        },
        {
            "id": "2054368886603276575",
            "handle": "keoneHD",
            "text": "gm builders",
            "created_at": "2026-05-13T01:00:00.000Z",
            "is_retweet": False,
            "retweeted_handle": None,
            "likes": 45,
            "retweets": 2,
            "replies": 1,
            "chain": "monad",
            "account_role": "contributor",
            "account_reliability": 0.90,
            "account_name": "Keone Hon",
        },
        {
            "id": "2054368886603276576",
            "handle": "keoneHD",
            "text": "RT @monad_xyz: Mainnet launch is next week!",
            "created_at": "2026-05-13T02:00:00.000Z",
            "is_retweet": True,
            "retweeted_handle": "monad_xyz",
            "likes": 300,
            "retweets": 120,
            "replies": 15,
            "chain": "monad",
            "account_role": "contributor",
            "account_reliability": 0.90,
            "account_name": "Keone Hon",
        },
        {
            "id": "2054368886603276577",
            "handle": "solana",
            "text": "Alpenglow upgrade is now live on mainnet.",
            "created_at": "2026-05-13T03:00:00.000Z",
            "is_retweet": False,
            "retweeted_handle": None,
            "likes": 2500,
            "retweets": 600,
            "replies": 130,
            "chain": "solana",
            "account_role": "official",
            "account_reliability": 0.95,
            "account_name": "Solana",
        },
    ]


class TestTweetToEventConversion:
    """Test _tweets_to_events with new composable collector."""

    def test_basic_conversion(self, collector, sample_tweets):
        events = collector._tweets_to_events(sample_tweets)
        assert len(events) == len(sample_tweets)
        assert all(e["source"] == "twitter" for e in events)

    def test_event_fields(self, collector, sample_tweets):
        events = collector._tweets_to_events([sample_tweets[0]])
        ev = events[0]
        assert ev["chain"] == "base"
        assert ev["reliability"] == 0.95
        assert ev["has_official_source"] is True
        assert "x402 now supports batched settlement" in ev["description"]
        assert ev["evidence"]["url"] == "https://x.com/jessepollak/status/2054368886603276574"
        assert ev["evidence"]["likes"] == 450
        assert ev["evidence"]["retweets"] == 120

    def test_retweet_handling(self, collector, sample_tweets):
        events = collector._tweets_to_events([sample_tweets[2]])  # RT
        ev = events[0]
        assert "reposted @monad_xyz" in ev["description"]

    def test_query_marker_filtered(self, collector):
        """_query markers from SurplusIntelligenceProvider are filtered out."""
        tweets = [
            {"_query": "from:solana since:2026-05-12"},
            {"id": "1", "handle": "solana", "text": "real tweet", "is_retweet": False,
             "created_at": "2026-05-13T00:00:00Z", "likes": 0, "retweets": 0, "replies": 0,
             "chain": "solana", "account_role": "official", "account_reliability": 0.9,
             "account_name": "Solana"},
        ]
        events = collector._tweets_to_events(tweets)
        assert len(events) == 1
        assert events[0]["description"] == "real tweet"


class TestBatchHandling:
    """Test handle batching logic."""

    def test_batch_sizes(self):
        handles = [(f"chain{i}", f"user{i}", {"role": "official"}) for i in range(25)]
        batches = TwitterCollector._batch_handles(handles, max_per_batch=10)
        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_single_batch(self):
        handles = [(f"chain{i}", f"user{i}", {}) for i in range(3)]
        batches = TwitterCollector._batch_handles(handles)
        assert len(batches) == 1
        assert len(batches[0]) == 3


class TestLoadAccounts:
    """Test account loading from config."""

    def test_accounts_loaded(self, collector):
        assert len(collector._accounts) > 0
        assert "solana" in collector._accounts
        assert "ethereum" in collector._accounts

    def test_account_structure(self, collector):
        sol = collector._accounts["solana"]
        assert "official" in sol
        assert "contributors" in sol


class TestMarkdownSummary:
    """Test _append_summary_md formatting."""

    def test_append_summary(self, collector, tmp_path, sample_tweets):
        now = datetime.now(timezone.utc)
        p = tmp_path / "summary.md"
        collector._append_summary_md(p, [sample_tweets[0]], now)
        content = p.read_text()
        assert "base" in content
        assert "jessepollak" in content
        assert "x402 now supports" in content
