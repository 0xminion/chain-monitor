"""Twitter/X Search extraction — composable provider architecture.

Primary entry point: TwitterCollector from collector.py.

Provider backends:
  direct_xai.DirectXAIProvider      — direct api.x.ai calls
  antseed_provider.AntseedBuyerProvider  — via antseed P2P buyer proxy

Set XSEARCH_PROVIDER env var to choose backend.
"""

from collectors.twitter.collector import TwitterCollector
from collectors.twitter.provider import XSearchProvider, SearchResult, TokenUsage
from collectors.twitter.direct_xai import DirectXAIProvider

__all__ = [
    "TwitterCollector",
    "XSearchProvider",
    "SearchResult",
    "TokenUsage",
    "DirectXAIProvider",
]
