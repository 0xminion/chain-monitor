"""Semantic enricher — agent-native.

The collector-side enrichment is removed; the running agent enriches events.
"""

import logging

logger = logging.getLogger(__name__)


class SemanticEnricher:
    """Agent-native pass-through.

    The running agent reads raw tweet/event text and applies semantic
    categories, sentiment, and entity extraction.
    """

    def __init__(self, client=None, cache=None, **kwargs):
        self.client = None
        self.cache = cache
        logger.info("[semantic] Agent-native mode — enrichment deferred to agent")

    def enrich_tweets(self, tweets: list[dict], **kwargs) -> list[dict]:
        """Return tweets unchanged. Agent enriches after reading."""
        logger.info(f"[semantic] Pass-through for {len(tweets)} tweets")
        return tweets

    def enrich(self, event: dict) -> dict:
        """Return event unchanged. Agent enriches after reading."""
        return event

    def get_health(self) -> dict:
        return {
            "provider": "agent-native",
            "mode": "pass-through",
            "note": "The running agent performs semantic enrichment",
        }
