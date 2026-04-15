"""Risk alert collector — hacks, exploits from free sources."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_chains

logger = logging.getLogger(__name__)

# Chain mapping for hack reports
CHAIN_KEYWORDS = {
    "ethereum": ["ethereum", "eth", "ether"],
    "bitcoin": ["bitcoin", "btc"],
    "solana": ["solana", "sol"],
    "base": ["base"],
    "bsc": ["bsc", "bnb", "binance smart chain"],
    "polygon": ["polygon", "matic"],
    "arbitrum": ["arbitrum", "arb"],
    "optimism": ["optimism", "op mainnet"],
    "sei": ["sei"],
    "sui": ["sui"],
    "aptos": ["aptos"],
    "near": ["near"],
    "ton": ["ton", "toncoin"],
    "hyperliquid": ["hyperliquid"],
}


class RiskAlertCollector(BaseCollector):
    """Monitors free sources for hack/exploit signals.

    Sources:
    - DeFiLlama protocols endpoint (detects sudden TVL drops)
    - RSS feeds from security-focused blogs
    """

    CATEGORY = "RISK_ALERT"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="RiskAlert", max_retries=max_retries, backoff_base=backoff_base)
        self._chains_cfg = get_chains()

    def _make_signal(self, chain: str, description: str, reliability: float, evidence: dict) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": evidence.get("source", "RiskAlert"),
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _match_chain(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for chain, keywords in CHAIN_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return chain
        return None

    def _detect_tvl_crashes(self) -> list[dict]:
        """Detect protocols with sudden TVL drops (potential hacks)."""
        signals = []

        # Fetch all protocols
        data = self.fetch_with_retry("https://api.llama.fi/protocols")
        if not data or not isinstance(data, list):
            return signals

        now = datetime.now(timezone.utc)
        for p in data:
            change_1d = p.get("change_1d")
            change_7d = p.get("change_7d")
            tvl = p.get("tvl", 0)
            name = p.get("name", "")
            chains = p.get("chains", [])

            if not tvl or tvl < 1_000_000:  # skip small protocols (<$1M)
                continue

            # Detect >50% drop in 24h — likely hack/exploit
            if change_1d is not None and change_1d < -50:
                amount_lost = tvl * abs(change_1d) / 100
                chain = chains[0].lower() if chains else "unknown"

                if amount_lost >= 1_000_000:  # $1M+ loss
                    if amount_lost >= 1e9:
                        amount_str = f"${amount_lost/1e9:.1f}B"
                    else:
                        amount_str = f"${amount_lost/1e6:.1f}M"

                    signals.append(self._make_signal(
                        chain=chain,
                        description=f"{name}: TVL dropped {abs(change_1d):.0f}% in 24h ({amount_str} at risk)",
                        reliability=0.7,  # heuristic, not confirmed hack
                        evidence={
                            "source": "DefiLlama",
                            "metric": "tvl_crash",
                            "protocol": name,
                            "tvl": tvl,
                            "change_1d": change_1d,
                            "amount_at_risk": amount_lost,
                            "chains": chains,
                        },
                    ))

        return signals[:5]  # max 5 per run

    def _collect_security_rss(self) -> list[dict]:
        """Collect from security-focused RSS feeds."""
        import feedparser
        signals = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=2)  # Only recent posts for daily relevance

        # Security-focused feeds
        feeds = [
            ("https://medium.com/feed/@immunefi", "Immunefi"),
        ]

        for feed_url, source_name in feeds:
            try:
                raw = self.fetch_text_with_retry(feed_url)
                if not raw:
                    continue
                feed = feedparser.parse(raw)
                for entry in feed.entries[:10]:
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    link = getattr(entry, "link", "")

                    # Date filter — skip old posts
                    pub_date = None
                    for field in ("published_parsed", "updated_parsed"):
                        ts = getattr(entry, field, None)
                        if ts:
                            try:
                                from time import mktime
                                pub_date = datetime.fromtimestamp(mktime(ts), tz=timezone.utc)
                                break
                            except (OverflowError, ValueError):
                                pass
                    if pub_date and pub_date < cutoff:
                        continue

                    # Check if security-related
                    combined = f"{title} {summary}".lower()
                    if not any(kw in combined for kw in ["vulnerability", "exploit", "hack", "security", "audit", "bug bounty", "cve"]):
                        continue

                    chain = self._match_chain(combined)
                    signals.append(self._make_signal(
                        chain=chain or "unknown",
                        description=f"[{source_name}] {title[:80]}",
                        reliability=0.8,
                        evidence={
                            "source": source_name,
                            "metric": "security_post",
                            "title": title,
                            "link": link,
                        },
                    ))
            except Exception as e:
                logger.warning(f"[RiskAlert] {source_name} feed failed: {e}")

        return signals[:3]

    def collect(self) -> list[dict]:
        signals = []
        signals.extend(self._detect_tvl_crashes())
        signals.extend(self._collect_security_rss())
        logger.info(f"[RiskAlert] Collected {len(signals)} signals")
        return signals
