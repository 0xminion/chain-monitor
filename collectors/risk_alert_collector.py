"""Risk alert collector — hacks, exploits from DeFiLlama."""

import logging
from datetime import datetime, timedelta, timezone

from collectors.base import BaseCollector
from config.loader import get_chains

logger = logging.getLogger(__name__)


class RiskAlertCollector(BaseCollector):
    """Monitors DeFiLlama hacks endpoint for recent security incidents."""

    CATEGORY = "RISK_ALERT"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="RiskAlert", max_retries=max_retries, backoff_base=backoff_base)
        self.hacks_endpoint = "https://api.llama.fi/hacks"
        self._chains_cfg = get_chains()
        # Build slug -> chain_name lookup
        self._slug_to_chain = {}
        for name, cfg in self._chains_cfg.items():
            slug = cfg.get("defillama_slug")
            if slug:
                self._slug_to_chain[slug.lower()] = name

    def _make_signal(self, chain: str, description: str, reliability: float, evidence: dict) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": "DefiLlama",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def collect(self) -> list[dict]:
        """Collect recent hack/exploit signals."""
        signals = []
        data = self.fetch_with_retry(self.hacks_endpoint)
        if not data or not isinstance(data, list):
            return signals

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        for hack in data:
            # Filter to recent hacks
            date_str = hack.get("date")
            if not date_str:
                continue
            try:
                hack_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if hack_date < cutoff:
                continue

            name = hack.get("name", "Unknown")
            chain_raw = hack.get("chain", "")
            amount = hack.get("amount", 0)
            classification = hack.get("classification", "hack")
            technique = hack.get("technique", "")

            # Map chain
            chain = self._slug_to_chain.get(chain_raw.lower(), chain_raw.lower())
            if not chain:
                chain = "unknown"

            # Format amount
            if amount >= 1e6:
                amount_str = f"${amount/1e6:.1f}M"
            elif amount >= 1e3:
                amount_str = f"${amount/1e3:.0f}K"
            else:
                amount_str = f"${amount:.0f}"

            desc = f"{name}: {classification} — {amount_str} lost"
            if technique:
                desc += f" ({technique[:50]})"

            signals.append(self._make_signal(
                chain=chain,
                description=desc,
                reliability=0.9,
                evidence={
                    "metric": "hack",
                    "name": name,
                    "chain": chain_raw,
                    "amount": amount,
                    "classification": classification,
                    "technique": technique,
                    "date": date_str,
                    "source_url": hack.get("link", ""),
                },
            ))

        logger.info(f"[RiskAlert] Collected {len(signals)} signals")
        return signals
