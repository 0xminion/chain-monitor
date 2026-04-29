"""Tests for O(n) deduplication engine."""

import pytest
from datetime import datetime, timezone, timedelta

from processors.pipeline_types import RawEvent
from processors.dedup_engine import deduplicate_events


class TestDedupEngine:

    def test_unique_events_all_preserved(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7)
        b = RawEvent("ethereum", "TECH_EVENT", "upgrade", "Eth v3", "rss", 0.7)
        result = deduplicate_events([a, b])
        assert len(result) == 2
        assert {r.chain for r in result} == {"solana", "ethereum"}

    def test_url_dedup_keeps_richer(self):
        url = "https://blog.solana.com/v2"
        a = RawEvent(
            "solana", "TECH_EVENT", "upgrade", "Solana v2",
            "rss", 0.7, raw_url=url, evidence={"a": 1}, semantic={"cat": "TECH_EVENT"}
        )
        b = RawEvent(
            "solana", "TECH_EVENT", "upgrade", "Solana v2",
            "twitter", 0.8, raw_url=url, evidence={"a": 1, "b": 2}, semantic={"cat": "TECH_EVENT"}
        )
        result = deduplicate_events([a, b])
        assert len(result) == 1
        # Should keep the richer one (b has more evidence)
        assert result[0].source == "twitter"
        assert result[0].reliability == 0.8

    def test_url_dedup_different_chains_kept(self):
        url = "https://coindesk.com/news"
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Story", "rss", 0.7, raw_url=url)
        b = RawEvent("ethereum", "TECH_EVENT", "upgrade", "Story", "rss", 0.7, raw_url=url)
        result = deduplicate_events([a, b])
        # URL + chain: different key → both kept
        assert len(result) == 2

    def test_fingerprint_dedup_no_url(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7)
        b = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "twitter", 0.8)
        result = deduplicate_events([a, b])
        assert len(result) == 1

    def test_fingerprint_distinct_descriptions_preserved(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2 release", "rss", 0.7)
        b = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana devnet reset", "rss", 0.7)
        result = deduplicate_events([a, b])
        assert len(result) == 2

    def test_timestamp_tiebreaker(self):
        now = datetime.now(timezone.utc)
        earlier = RawEvent(
            "solana", "TECH_EVENT", "upgrade", "Solana v2",
            "rss", 0.7, evidence={"a": 1}, published_at=now
        )
        later = RawEvent(
            "solana", "TECH_EVENT", "upgrade", "Solana v2",
            "twitter", 0.7, evidence={"a": 1}, published_at=now + timedelta(seconds=1)
        )
        result = deduplicate_events([earlier, later])
        assert len(result) == 1
        # Should keep the later one
        assert result[0].published_at == later.published_at

    def test_empty_input(self):
        result = deduplicate_events([])
        assert result == []

    def test_preserves_insertion_order(self):
        a = RawEvent("solana", "TECH_EVENT", "upgrade", "Solana v2", "rss", 0.7)
        b = RawEvent("ethereum", "TECH_EVENT", "upgrade", "Eth v3", "rss", 0.7)
        c = RawEvent("bitcoin", "TECH_EVENT", "upgrade", "Bitcoin core", "rss", 0.7)
        result = deduplicate_events([a, b, c])
        assert [r.chain for r in result] == ["solana", "ethereum", "bitcoin"]

    def test_from_collector_dict_adapter(self):
        """Verify RawEvent.from_collector_dict correctly extracts URLs."""
        d = {
            "chain": "solana",
            "category": "TECH_EVENT",
            "subcategory": "upgrade",
            "description": "Solana v2 released",
            "source": "rss",
            "reliability": 0.8,
            "evidence": {
                "link": "https://blog.solana.com/v2",
                "published": "2026-04-27T10:30:00+00:00",
            },
        }
        ev = RawEvent.from_collector_dict(d, "rss")
        assert ev.chain == "solana"
        assert ev.raw_url == "https://blog.solana.com/v2"
        assert ev.published_at is not None
