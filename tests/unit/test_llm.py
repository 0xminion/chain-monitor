"""Tests for SemanticEnricher — agent-native pass-through.

The real enrichment is done by the running agent.
"""

import pytest
from processors.semantic_enricher import SemanticEnricher


@pytest.fixture
def enricher():
    return SemanticEnricher()


class TestSemanticEnricherPassThrough:
    def test_enrich_non_twitter(self, enricher):
        event = {"source": "rss", "description": "hello world"}
        result = enricher.enrich(event)
        assert result == event

    def test_enrich_twitter_pass_through(self, enricher):
        event = {
            "source": "twitter",
            "chain": "ethereum",
            "description": "Mainnet upgrade live tomorrow",
        }
        result = enricher.enrich(event)
        assert result == event  # agent does classification

    def test_enrich_tweets_batch_pass_through(self, enricher):
        tweets = [
            {"chain": "eth", "text": "upgrade live", "account_handle": "eth"},
            {"chain": "sol", "text": "partnership announced", "account_handle": "sol"},
        ]
        enriched = enricher.enrich_tweets(tweets)
        assert len(enriched) == 2
        assert enriched == tweets  # unchanged — agent classifies

    def test_health(self, enricher):
        h = enricher.get_health()
        assert h["provider"] == "agent-native"
        assert h["mode"] == "pass-through"
