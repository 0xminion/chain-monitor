"""Twitter/X Search provider interface — composable backend abstraction.

All providers must implement search() returning parsed tweets + token usage.
To swap backends, change the TWITTER_PROVIDER env var or config entry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenUsage:
    """Token consumption for a single provider call."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class SearchResult:
    """Result from a single X search call (one batch of handles)."""
    tweets: list[dict] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: Optional[str] = None


class XSearchProvider(ABC):
    """Composable backend for X/Twitter search extraction.

    Implementations: DirectXAIProvider, AntseedBuyerProvider, OpenRouterProvider.
    """

    @abstractmethod
    async def search(
        self,
        handles: list[str],
        from_date: str,
        to_date: str,
    ) -> SearchResult:
        """Search tweets/retweets for given handles within date range.

        Args:
            handles: X handles (without @) — max 10 per call
            from_date: ISO8601 start date (YYYY-MM-DD)
            to_date: ISO8601 end date (YYYY-MM-DD)

        Returns:
            SearchResult with parsed tweets and token usage stats.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model name used by this provider."""
        ...
