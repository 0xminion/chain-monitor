"""RSS/Atom feed collector — blog posts, news matching narrative keywords."""

import logging
import re
from datetime import datetime, timezone
from time import mktime
from typing import Optional

import feedparser

from collectors.base import BaseCollector
from config.loader import get_chains, get_baselines, get_sources, get_narratives, get_env

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """Fetches RSS/Atom feeds and matches against narrative keywords.

    Sources:
    - Per-chain blog_rss from chains.yaml
    - Global news feeds from sources.yaml rss_feeds

    Categorization:
    - Matches post title + summary against narrative keywords
    - Falls back to "NEWS" category if no keyword match
    - Maps matched narratives to descriptive categories
    """

    # Mapping from narrative keys to output categories
    NARRATIVE_CATEGORY_MAP = {
        "ai_agents": "AI_NARRATIVE",
        "payments_stablecoins": "FINANCIAL",
        "defi": "FINANCIAL",
        "l2_infrastructure": "INFRASTRUCTURE",
        "rwa": "FINANCIAL",
        "gaming": "ECOSYSTEM",
        "privacy": "SECURITY",
        "security": "SECURITY",
    }
    DEFAULT_CATEGORY = "NEWS"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="RSS", max_retries=max_retries, backoff_base=backoff_base)

        self._chains_cfg = get_chains()
        self._baselines_cfg = get_baselines()

        try:
            self._narratives_cfg = get_narratives()
        except FileNotFoundError:
            logger.warning("[RSS] narratives.yaml not found, keyword matching disabled")
            self._narratives_cfg = {}

        try:
            self._sources_cfg = get_sources()
        except FileNotFoundError:
            self._sources_cfg = {}

        # Build chain keyword lookup: chain_name -> list of keywords (lowercase)
        # Uses narrative keywords + chain name as implicit keywords
        self._chain_keywords: dict[str, list[str]] = {}
        narratives = self._narratives_cfg.get("narratives", {})
        for chain_name in self._chains_cfg:
            keywords = [chain_name.lower()]
            # Add chain aliases/variants
            aliases = self._get_chain_aliases(chain_name)
            keywords.extend(aliases)
            self._chain_keywords[chain_name] = keywords

        # Build narrative keyword sets for categorization
        self._narrative_keywords: dict[str, list[str]] = {}
        for narrative_key, narrative_cfg in narratives.items():
            kws = narrative_cfg.get("keywords", [])
            self._narrative_keywords[narrative_key] = [kw.lower() for kw in kws]

    @staticmethod
    def _get_chain_aliases(chain_name: str) -> list[str]:
        """Generate common aliases for a chain name."""
        aliases_map = {
            "ethereum": ["eth", "ether"],
            "bitcoin": ["btc"],
            "solana": ["sol"],
            "arbitrum": ["arb"],
            "starknet": ["strk"],
            "optimism": ["op"],
            "polygon": ["matic", "pol"],
            "base": ["coinbase"],  # Base is Coinbase's chain
            "bsc": ["bnb", "binance smart chain", "binance chain"],
            "sui": [],
            "aptos": ["apt"],
            "sei": [],
            "near": ["near protocol"],
            "ton": ["toncoin", "the open network"],
            "monad": [],
            "hyperliquid": ["hype"],
            "mantle": ["mnt"],
            "gnosis": ["xdai", "gno"],
            "bittensor": ["tao"],
            "virtuals": ["virtual"],
        }
        return aliases_map.get(chain_name.lower(), [])

    def _parse_date(self, entry) -> Optional[datetime]:
        """Extract published date from a feed entry."""
        for field in ("published_parsed", "updated_parsed"):
            time_struct = getattr(entry, field, None)
            if time_struct:
                try:
                    return datetime.fromtimestamp(mktime(time_struct), tz=timezone.utc)
                except (OverflowError, ValueError, OSError):
                    continue
        return None

    def _match_narratives(self, text: str) -> list[str]:
        """Return list of narrative keys whose keywords appear in text."""
        text_lower = text.lower()
        matched = []
        for narrative_key, keywords in self._narrative_keywords.items():
            for kw in keywords:
                # Use word boundary matching to avoid false positives
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    matched.append(narrative_key)
                    break
        return matched

    def _match_chain(self, text: str) -> Optional[str]:
        """Determine which chain a text item is about based on keyword matching."""
        text_lower = text.lower()
        best_match = None
        best_match_len = 0

        for chain_name, keywords in self._chain_keywords.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    # Prefer longer/more specific matches
                    if len(kw) > best_match_len:
                        best_match = chain_name
                        best_match_len = len(kw)

        return best_match

    def _make_signal(
        self,
        chain: str,
        category: str,
        description: str,
        reliability: float,
        evidence: dict,
    ) -> dict:
        return {
            "chain": chain,
            "category": category,
            "description": description,
            "source": "RSS",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _process_feed(
        self,
        feed_url: str,
        source_name: str,
        default_chain: Optional[str] = None,
    ) -> list[dict]:
        """Parse a single RSS/Atom feed and return matching signals.

        Args:
            feed_url: URL of the RSS/Atom feed.
            source_name: Human-readable name of the feed source.
            default_chain: If set, associate unattributed entries with this chain.

        Returns:
            List of signal dicts.
        """
        signals: list[dict] = []

        # Fetch raw feed text (feedparser handles XML, not JSON)
        raw = self.fetch_text_with_retry(feed_url)
        if not raw:
            logger.warning(f"[RSS] Failed to fetch feed: {feed_url}")
            return signals

        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            logger.warning(f"[RSS] Feed parse error for {feed_url}: {feed.bozo_exception}")
            return signals

        # Only process entries from the last 48 hours (7 days for chain blogs)
        now = datetime.now(timezone.utc)
        if default_chain:
            cutoff = now.timestamp() - (7 * 24 * 3600)  # 7 days for chain-specific blogs
        else:
            cutoff = now.timestamp() - (48 * 3600)  # 48h for news feeds

        for entry in feed.entries:
            pub_date = self._parse_date(entry)
            if pub_date and pub_date.timestamp() < cutoff:
                continue

            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            combined_text = f"{title} {summary}"

            # Determine chain attribution
            chain = self._match_chain(combined_text) or default_chain
            if not chain:
                # Skip news items we can't attribute to a chain
                continue

            # Match narratives for categorization
            matched_narratives = self._match_narratives(combined_text)
            if matched_narratives:
                primary = matched_narratives[0]
                category = self.NARRATIVE_CATEGORY_MAP.get(primary, self.DEFAULT_CATEGORY)
            else:
                category = self.DEFAULT_CATEGORY

            # Build description
            desc = title[:200] if title else "New post"
            if source_name:
                desc = f"[{source_name}] {desc}"

            age_hours = None
            if pub_date:
                age_hours = (now - pub_date).total_seconds() / 3600

            signals.append(self._make_signal(
                chain=chain,
                category=category,
                description=desc,
                reliability=0.7 if matched_narratives else 0.5,
                evidence={
                    "metric": "rss_post",
                    "source_name": source_name,
                    "feed_url": feed_url,
                    "title": title,
                    "link": link,
                    "published_at": pub_date.isoformat() if pub_date else None,
                    "age_hours": round(age_hours, 1) if age_hours else None,
                    "matched_narratives": matched_narratives,
                    "matched_keywords": True if matched_narratives else False,
                },
            ))

        return signals

    def collect(self) -> list[dict]:
        """Collect RSS signals from chain blogs and global news feeds.

        Returns:
            List of signal dicts with keys: chain, category, description,
            source, reliability, evidence.
        """
        signals: list[dict] = []

        # 1. Per-chain blog feeds
        for chain_name, chain_cfg in self._chains_cfg.items():
            blog_rss = chain_cfg.get("blog_rss")
            if not blog_rss:
                continue
            signals.extend(self._process_feed(
                feed_url=blog_rss,
                source_name=f"{chain_name} blog",
                default_chain=chain_name,
            ))

        # 2. Global news feeds from sources.yaml
        rss_feeds = self._sources_cfg.get("rss_feeds", {})
        
        # Map chain_event feed names to chain names for attribution
        chain_name_map = {
            "Solana Blog": "solana",
            "Avalanche Blog": "avalanche",
            "Sui Blog": "sui",
            "Near Blog": "near",
            "Aptos Blog": "aptos",
            "Monad Blog": "monad",
            "Arbitrum Blog": "arbitrum",
            "Starknet Blog": "starknet",
            "Mantle Blog": "mantle",
            "Morph Blog": "morph",
            "BNB Chain Blog": "bsc",
            "Hyperliquid": "hyperliquid",
            "Gnosis Blog": "gnosis",
            "Stablechain Blog": "stablechain",
            "Virtuals": "virtuals",
        }
        
        for category, feeds in rss_feeds.items():
            if not isinstance(feeds, list):
                continue
            for feed_cfg in feeds:
                if not isinstance(feed_cfg, dict):
                    continue
                feed_url = feed_cfg.get("url")
                feed_name = feed_cfg.get("name", category)
                if not feed_url:
                    continue
                # Chain event feeds: attribute to specific chain
                default_chain = chain_name_map.get(feed_name) if category == "chain_events" else None
                signals.extend(self._process_feed(
                    feed_url=feed_url,
                    source_name=feed_name,
                    default_chain=default_chain,
                ))

        logger.info(f"[RSS] Collected {len(signals)} signals")
        return signals
