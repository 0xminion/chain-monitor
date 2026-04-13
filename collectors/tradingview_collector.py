"""TradingView news collector — crypto news from tradingview.com/news-flow."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_chains

logger = logging.getLogger(__name__)

# Skip paywalled/generic entries
SKIP_TITLES = ["sign in to read", "exclusive news"]

# Category keyword rules (order matters — first match wins)
CATEGORY_RULES = [
    ("RISK_ALERT", [
        "hack", "exploit", "stolen", "drained", "rug pull", "scam",
        "vulnerability", "attack", "compromised", "breach", "drained",
        "murder", "arrested", "charged", "lawsuit against",
    ]),
    ("REGULATORY", [
        "sec ", "sec,", "sec.", "regulation", "regulatory", "enforcement",
        "ban", "approval", "license", "compliance", "lawsuit", "court",
        "senate", "congress", "european commission", "ecb ", "mica",
        "stablecoin bill", "crypto bill", "guidance", "framework",
        "broker registration", "tokenized",
    ]),
    ("PARTNERSHIP", [
        "partnership", "partners with", "teams up", "collaboration",
        "integration", "integrates with", "co-launch", "joint",
        "announce", "launches with", "debuts",
    ]),
    ("VISIBILITY", [
        "conference", "hackathon", "ama", "keynote", "speaker",
        "hired", "appointed", "joins", "departed", "podcast",
        "interview", "summit",
    ]),
    ("FINANCIAL", [
        "tvl", "volume", "funding", "raised", "grant", "airdrop",
        "tge", "token launch", "billion", "million", "etf",
        "inflows", "outflows", "ipo", "valuation", "holdings",
        "supply", "whale",
    ]),
    ("TECH_EVENT", [
        "upgrade", "mainnet", "testnet", "launch", "release",
        "hard fork", "eip", "deploy", "update", "version",
        "agentic", "agent",
    ]),
]

# Chain detection from headlines
CHAIN_KEYWORDS = {
    "bitcoin": ["bitcoin", "btc"],
    "ethereum": ["ethereum", "eth ", "ether"],
    "solana": ["solana", "sol "],
    "base": ["base", "coinbase"],
    "bsc": ["bnb", "binance"],
    "polygon": ["polygon", "matic"],
    "xrp": ["xrp", "ripple"],
    "cardano": ["cardano", "ada"],
    "avalanche": ["avalanche", "avax"],
    "arbitrum": ["arbitrum"],
    "optimism": ["optimism"],
    "hyperliquid": ["hyperliquid"],
    "sui": ["sui"],
    "aptos": ["aptos"],
    "sei": ["sei"],
    "ton": ["toncoin", "ton "],
}


class TradingViewCollector(BaseCollector):
    """Collects crypto news from TradingView News Flow page.

    Uses cloudscraper to bypass CloudFlare, parses headline text.
    Categorizes into: RISK_ALERT, REGULATORY, PARTNERSHIP, VISIBILITY,
    FINANCIAL, TECH_EVENT based on keyword matching.
    """

    CATEGORY = "NEWS"  # default, overridden by categorizer

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="TradingView", max_retries=max_retries, backoff_base=backoff_base)
        self._chains_cfg = get_chains()

    def _make_signal(self, chain: str, category: str, description: str, reliability: float, evidence: dict) -> dict:
        return {
            "chain": chain,
            "category": category,
            "description": description,
            "source": evidence.get("source", "TradingView"),
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _classify(self, title: str) -> tuple[str, float]:
        """Classify title into category with confidence."""
        title_lower = title.lower()
        for category, keywords in CATEGORY_RULES:
            for kw in keywords:
                if kw in title_lower:
                    # Higher reliability for regulatory/risk keywords
                    if category in ("RISK_ALERT", "REGULATORY"):
                        return category, 0.85
                    return category, 0.75
        return "NEWS", 0.5

    def _detect_chain(self, title: str) -> Optional[str]:
        title_lower = title.lower()
        for chain, keywords in CHAIN_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                return chain
        return None

    def collect(self) -> list[dict]:
        """Scrape TradingView crypto news flow."""
        signals = []

        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            resp = scraper.get("https://www.tradingview.com/news-flow/?market=crypto", timeout=20)
            if resp.status_code != 200:
                logger.warning(f"[TradingView] HTTP {resp.status_code}")
                return signals
        except ImportError:
            # Fallback to requests
            resp = self.fetch_text_with_retry("https://www.tradingview.com/news-flow/?market=crypto")
            if not resp:
                return signals
            # Wrap in mock response
            class MockResp:
                text = resp
            resp = MockResp()

        # Parse news from page text
        # Pattern: alternating lines of "Source" then "Title"
        text = resp.text
        lines = text.split("\n")

        # Find news section (after "Reset all" and before article content)
        news_items = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Skip empty, short, or UI elements
            if len(line) < 5 or line in ("Close", "Save", "Reset all"):
                i += 1
                continue

            # Check if next line is a title (longer, capitalized)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Source names are short (1-3 words), titles are longer
                if (len(line) < 30 and len(next_line) > 15
                    and not any(skip in next_line.lower() for skip in SKIP_TITLES)):
                    # Potential source + title pair
                    # Validate: source should look like a news source name
                    if re.match(r'^[A-Z][a-zA-Z\s]+$', line) and len(line.split()) <= 4:
                        news_items.append({
                            "source": line.strip(),
                            "title": next_line.strip(),
                        })
                        i += 2
                        continue
            i += 1

        # Deduplicate
        seen_titles = set()
        for item in news_items:
            key = item["title"][:60]
            if key in seen_titles:
                continue
            seen_titles.add(key)

            title = item["source"] + ": " + item["title"]
            category, reliability = self._classify(item["title"])
            chain = self._detect_chain(item["title"])

            signals.append(self._make_signal(
                chain=chain or "unknown",
                category=category,
                description=title[:200],
                reliability=reliability,
                evidence={
                    "source": item["source"],
                    "metric": "tradingview_news",
                    "title": item["title"],
                    "provider": item["source"],
                },
            ))

        logger.info(f"[TradingView] Collected {len(signals)} signals")
        return signals[:30]  # cap at 30
