"""TradingView News Flow collector — scrapes crypto news via Playwright Chromium."""

import logging

from datetime import datetime, timezone

from collectors.base import BaseCollector
from config.loader import get_chains

logger = logging.getLogger(__name__)

TRADINGVIEW_URL = "https://www.tradingview.com/news-flow/?market=crypto"

# Load our tracked chains for relevance filtering
_TRACKED_CHAINS = set()
_CHAIN_KEYWORDS = {}  # chain_name -> list of search keywords

def _init_chain_keywords():
    """Build keyword lookup from chains.yaml config."""
    global _TRACKED_CHAINS
    if _CHAIN_KEYWORDS:
        return
    try:
        chains = get_chains()
        _TRACKED_CHAINS = set(chains.keys())

        # Map chain names to search keywords
        keyword_map = {
            "ethereum": ["ethereum", "eth ", "eth,", "ether", "eip", "erc-", "vitalik"],
            "bitcoin": ["bitcoin", "btc ", "btc,", "ordinals", "brc-20", "runes", "saylor"],
            "solana": ["solana", "sol ", "sol,", "svm", "solana "],
            "base": ["base chain", "coinbase l2", "base l2", "base network"],
            "arbitrum": ["arbitrum", "arb ", "arb,", "arbitrum one"],
            "optimism": ["optimism", "op stack", "superchain"],
            "polygon": ["polygon", "matic", "pol ", "polygon "],
            "bsc": ["bnb chain", "bsc", "binance smart chain", "bnb "],
            "xlayer": ["xlayer", "x layer", "okx chain"],
            "monad": ["monad"],
            "hyperliquid": ["hyperliquid", "hype "],
            "sui": ["sui "],
            "aptos": ["aptos"],
            "sei": ["sei "],
            "near": ["near ", "near protocol"],
            "ton": ["ton ", "toncoin", "ton "],
            "starknet": ["starknet", "strk"],
            "mantle": ["mantle", "mnt "],
            "gnosis": ["gnosis", "xdai"],
            "ink": ["ink chain", "ink network"],
            "morph": ["morph "],
            "megaeth": ["megaeth", "mega-evm"],
            "tempo": ["tempo chain", "tempo network"],
            "plasma": ["plasma "],
            "stablechain": ["stablechain"],
            "bittensor": ["bittensor", "tao "],
            "virtuals": ["virtuals protocol", "virtual "],
        }
        for chain_name in _TRACKED_CHAINS:
            _CHAIN_KEYWORDS[chain_name] = keyword_map.get(chain_name, [chain_name])
    except Exception:
        pass

_init_chain_keywords()

# JS extraction script for Playwright
EXTRACT_JS = '''() => {
    const items = [];
    const links = document.querySelectorAll('a[href*="/news/"]');
    const seen = new Set();

    links.forEach(a => {
        const href = a.href || '';
        const text = a.innerText?.trim();
        if (!text || text.length < 10 || seen.has(href)) return;
        if (text === 'Sign in to read exclusive news') return;

        seen.add(href);

        // Extract source from URL: /news/[source]:[id]:[slug]/
        const sourceMatch = href.match(/\\/news\\/([^:]+):/);
        const source = sourceMatch ? sourceMatch[1] : 'unknown';

        // Clean title — extract actual headline
        let title = text;
        // Handle "SourceName\\nActual Title" pattern
        if (title.includes('\\n')) {
            const parts = title.split('\\n').map(p => p.trim()).filter(p => p);
            if (parts.length >= 2) {
                title = parts.slice(1).join(' ').trim();
            }
        }
        // Handle "SourceName Actual Title" (no newline)
        const sourceClean = source.replace(/_/g, ' ').replace(/_/g, ' ');
        if (title.toLowerCase().startsWith(sourceClean.toLowerCase()) && title.length > sourceClean.length + 5) {
            title = title.substring(sourceClean.length).trim();
        }

        items.push({
            source: source,
            title: title,
            href: href,
        });
    });

    return items;
}'''


class TradingViewCollector(BaseCollector):
    """Collects news from TradingView's News Flow page using Playwright."""

    def __init__(self, browser_type: str = "chromium"):
        super().__init__(name="tradingview")
        self.browser_type = browser_type
        self._playwright = None
        self._browser = None

    def collect(self) -> list[dict]:
        """Scrape TradingView news flow for crypto news."""
        signals = []

        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            if self.browser_type == "camoufox":
                try:
                    from camoufox.sync_api import Camoufox
                    self._browser = Camoufox(headless=True).__enter__()
                    # Camoufox returns a context, get the browser
                    page = self._browser.new_page()
                except Exception as e:
                    logger.warning(f"Camoufox failed ({e}), falling back to Chromium")
                    self._browser = self._playwright.chromium.launch(headless=True)
                    page = self._browser.new_page()
            else:
                self._browser = self._playwright.chromium.launch(headless=True)
                page = self._browser.new_page()

            logger.info("Navigating to TradingView News Flow...")
            page.goto(TRADINGVIEW_URL, timeout=30000)
            page.wait_for_timeout(8000)  # Wait for JS rendering

            # Scroll to load more items
            for _ in range(3):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(2000)

            # Extract news items
            news_items = page.evaluate(EXTRACT_JS)
            logger.info(f"TradingView: extracted {len(news_items)} news items")

            for item in news_items:
                if not item.get("title") or len(item["title"]) < 10:
                    continue

                signal = self._parse_news_item(item)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"TradingView scraper failed: {e}")
            self.health.mark_failure(str(e))
            return signals
        finally:
            self._cleanup()

        self.health.mark_success()
        return signals

    def _parse_news_item(self, item: dict) -> dict | None:
        """Parse a news item into a signal dict."""
        title = item.get("title", "").strip()
        source = item.get("source", "unknown")
        href = item.get("href", "")

        # Filter out paywalled/generic items
        skip_phrases = [
            "sign in to read",
            "exclusive news",
            "subscribe to",
            "premium content",
        ]
        if any(phrase in title.lower() for phrase in skip_phrases):
            return None

        if not title or len(title) < 10:
            return None

        # Categorize based on keywords in title
        category = self._categorize_title(title)

        # Detect chain relevance — only keep items matching our tracked chains
        chain_relevance = self._detect_chain_relevance(title)
        if not chain_relevance:
            # Skip news not related to any tracked chain
            # EXCEPT for regulatory/cross-chain macro news
            if category not in ("REGULATORY", "RISK_ALERT"):
                return None

        return {
            "type": "tradingview_news",
            "category": category,
            "chain": chain_relevance if chain_relevance else "general",
            "title": title[:300],
            "source_name": f"TradingView ({source})",
            "description": title,
            "evidence": {
                "title": title,
                "source": source,
                "url": href,
                "raw_source": "tradingview",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "importance": self._score_importance(title, category),
        }

    def _categorize_title(self, title: str) -> str:
        """Quick categorization from headline keywords."""
        t = title.lower()

        # Partnership signals
        partnership_words = [
            "partnership", "partners with", "teams up", "integration",
            "collaborates", "co-launch", "joins forces", "in partnership",
            "joint venture", "alliance", "works with", "joins",
            "deployed on", "live on", "launches on", "available on",
            "adds support for", "expands to", "enters",
        ]
        if any(w in t for w in partnership_words):
            return "PARTNERSHIP"

        # Visibility signals
        visibility_words = [
            "conference", "hackathon", "ama", "keynote", "speaker",
            "podcast", "interview", "summit", "workshop", "demo day",
            "hired", "appointed", "joins as", "new ceo", "new cto",
            "departed", "resigned", "stepped down", "leaving",
            "live stream", "community call", "town hall",
        ]
        if any(w in t for w in visibility_words):
            return "VISIBILITY"

        # Regulatory signals
        regulatory_words = [
            "sec ", "sec,", "sec.", "enforcement", "lawsuit", "ban",
            "prohibition", "license", "approval", "regulation",
            "compliance", "fine", "penalty", "mica", "fatf",
            "broker registration", "wells notice", "subpoena",
            "regulator", "cftc", "doj", "treasury",
        ]
        if any(w in t for w in regulatory_words):
            return "REGULATORY"

        # Risk signals
        risk_words = [
            "hack", "exploit", "vulnerability", "outage", "downtime",
            "halt", "critical bug", "drained", "stolen", "attack",
            "compromised", "rug pull", "scam", "breach", "incident",
        ]
        if any(w in t for w in risk_words):
            return "RISK_ALERT"

        # Tech signals
        tech_words = [
            "upgrade", "mainnet", "testnet", "launch", "release",
            "hard fork", "eip", "deploy", "update", "version",
            "network", "protocol", "chain", "layer 2", "l2",
            "rollup", "bridge", "staking",
        ]
        if any(w in t for w in tech_words):
            return "TECH_EVENT"

        # Financial signals
        financial_words = [
            "tvl", "volume", "funding", "raised", "grant", "airdrop",
            "tge", "token launch", "milestone", "billion", "million",
            "inflows", "outflows", "buyback", "treasury", "yield",
            "revenue", "earnings", "profit", "loss",
        ]
        if any(w in t for w in financial_words):
            return "FINANCIAL"

        return "NEWS"

    def _detect_chain_relevance(self, title: str) -> str | None:
        """Detect which tracked chain this news is about."""
        t = title.lower()

        for chain_name, keywords in _CHAIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in t:
                    return chain_name
        return None

    def _score_importance(self, title: str, category: str) -> str:
        """Score importance from headline."""
        t = title.lower()

        # Critical indicators
        critical_words = ["hack", "exploit", "drained", "stolen", "outage", "halt", "emergency"]
        if any(w in t for w in critical_words):
            return "critical"

        # High indicators
        high_words = ["mainnet launch", "sec charges", "sec sues", "billion", "partnership", "integration", "upgrade"]
        if any(w in t for w in high_words):
            return "high"

        # Medium for regulatory and partnerships
        if category in ("REGULATORY", "PARTNERSHIP", "RISK_ALERT"):
            return "medium"

        return "low"

    def _cleanup(self):
        """Clean up Playwright resources."""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
