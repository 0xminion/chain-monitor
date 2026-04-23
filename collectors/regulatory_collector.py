"""Regulatory collector — SEC EDGAR, CoinCenter, policy blogs."""

import logging

from datetime import datetime, timedelta, timezone
from time import mktime
from typing import Optional

import feedparser

from collectors.base import BaseCollector
from config.loader import get_chains

logger = logging.getLogger(__name__)

# SEC EDGAR crypto-related form types
SEC_FORM_TYPES = ["8-K", "S-1", "10-K", "10-Q", "DEF 14A"]

# Keywords that indicate crypto relevance in SEC filings
CRYPTO_KEYWORDS = [
    "cryptocurrency", "digital asset", "blockchain", "token", "defi",
    "decentralized finance", "virtual currency", "stablecoin", "web3",
    "nft", "non-fungible", "mining", "staking", "wallet",
    "ethereum", "bitcoin", "solana", "binance", "coinbase",
    "sec charges", "sec sues", "wells notice", "cease and desist",
    "enforcement action", "settlement",
]

# Chain name mapping for SEC filings
CHAIN_KEYWORDS = {
    "ethereum": ["ethereum", "eth ", "ether"],
    "bitcoin": ["bitcoin", "btc"],
    "solana": ["solana", "sol "],
    "base": ["base", "coinbase"],
    "bsc": ["bnb", "binance"],
    "polygon": ["polygon", "matic"],
    "arbitrum": ["arbitrum"],
    "optimism": ["optimism", "op "],
}


class RegulatoryCollector(BaseCollector):
    """Monitors SEC EDGAR and policy blogs for crypto regulatory signals."""

    CATEGORY = "REGULATORY"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="Regulatory", max_retries=max_retries, backoff_base=backoff_base)
        self._chains_cfg = get_chains()

        # SEC EDGAR requires User-Agent with contact
        self.session.headers.update({
            "User-Agent": "ChainMonitor research@chainmonitor.dev",
            "Accept": "application/atom+xml",
        })

    def _make_signal(self, chain: str, description: str, reliability: float, evidence: dict) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": evidence.get("source", "Regulatory"),
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _parse_date(self, entry) -> Optional[datetime]:
        for field in ("published_parsed", "updated_parsed"):
            ts = getattr(entry, field, None)
            if ts:
                try:
                    return datetime.fromtimestamp(mktime(ts), tz=timezone.utc)
                except (OverflowError, ValueError, OSError):
                    continue
        return None

    def _match_chain(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for chain, keywords in CHAIN_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return chain
        return None

    def _is_crypto_relevant(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in CRYPTO_KEYWORDS)

    def _collect_sec_edgar(self) -> list[dict]:
        """Collect recent crypto-related SEC filings."""
        signals = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        # Search EDGAR for recent 8-K filings mentioning crypto
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": " OR ".join(f'"{kw}"' for kw in CRYPTO_KEYWORDS[:8]),
            "forms": ",".join(SEC_FORM_TYPES),
            "dateRange": "custom",
            "startdt": cutoff.strftime("%Y-%m-%d"),
            "enddt": now.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.fetch_with_retry(url, params=params)
            if not resp:
                return signals
            if isinstance(resp, dict):
                hits = resp.get("hits", {}).get("hits", [])
                for hit in hits[:10]:
                    source = hit.get("_source", {})
                    title = source.get("display_names", [""])[0] if source.get("display_names") else ""
                    form = source.get("form_type", "")
                    filed = source.get("file_date", "")
                    company = source.get("entity_name", "Unknown")
                    desc_text = f"{company} {title}"
                    chain = self._match_chain(desc_text)

                    signals.append(self._make_signal(
                        chain=chain or "unknown",
                        description=f"SEC {form}: {company} — {title[:80]}",
                        reliability=0.85,
                        evidence={
                            "source": "SEC EDGAR",
                            "metric": "sec_filing",
                            "form_type": form,
                            "company": company,
                            "title": title,
                            "filed_date": filed,
                        },
                    ))
        except Exception as e:
            logger.warning(f"[Regulatory] SEC EFTS failed: {e}")

        # Also try Atom feed for general 8-K filings
        try:
            feed_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&owner=include&count=10&output=atom"
            raw = self.fetch_text_with_retry(feed_url)
            if raw:
                feed = feedparser.parse(raw)
                for entry in feed.entries[:5]:
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    link = getattr(entry, "link", "")
                    pub_date = self._parse_date(entry)

                    if pub_date and pub_date < cutoff:
                        continue

                    combined = f"{title} {summary}"
                    if not self._is_crypto_relevant(combined):
                        continue

                    chain = self._match_chain(combined)
                    signals.append(self._make_signal(
                        chain=chain or "unknown",
                        description=f"SEC 8-K: {title[:80]}",
                        reliability=0.8,
                        evidence={
                            "source": "SEC EDGAR",
                            "metric": "sec_filing",
                            "form_type": "8-K",
                            "title": title,
                            "link": link,
                        },
                    ))
        except Exception as e:
            logger.warning(f"[Regulatory] SEC Atom feed failed: {e}")

        return signals[:5]  # max 5 SEC signals per run

    def _collect_coincenter(self) -> list[dict]:
        """Collect CoinCenter policy blog posts."""
        signals = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        raw = self.fetch_text_with_retry("https://www.coincenter.org/feed/")
        if not raw:
            return signals

        feed = feedparser.parse(raw)
        for entry in feed.entries[:10]:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            link = getattr(entry, "link", "")
            pub_date = self._parse_date(entry)

            if pub_date and pub_date < cutoff:
                continue

            combined = f"{title} {summary}"
            chain = self._match_chain(combined)

            # Classify subcategory
            title_lower = title.lower()
            if any(w in title_lower for w in ["enforcement", "charges", "sues", "penalty"]):
                subcategory = "enforcement"
                reliability = 0.9
            elif any(w in title_lower for w in ["bill", "legislation", "congress", "senate"]):
                subcategory = "legislation"
                reliability = 0.85
            elif any(w in title_lower for w in ["rule", "regulation", "guidance", "framework"]):
                subcategory = "regulation"
                reliability = 0.8
            else:
                subcategory = "policy"
                reliability = 0.7

            signals.append(self._make_signal(
                chain=chain or "unknown",
                description=f"[CoinCenter] {title[:80]}",
                reliability=reliability,
                evidence={
                    "source": "CoinCenter",
                    "metric": "policy_blog",
                    "subcategory": subcategory,
                    "title": title,
                    "link": link,
                    "published_at": pub_date.isoformat() if pub_date else None,
                },
            ))

        return signals[:5]

    def collect(self) -> list[dict]:
        signals = []
        signals.extend(self._collect_sec_edgar())
        signals.extend(self._collect_coincenter())
        logger.info(f"[Regulatory] Collected {len(signals)} signals")
        return signals
