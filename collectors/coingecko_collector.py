"""CoinGecko collector — price, market cap, volume signals."""

import logging
import time

from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_chains, get_baselines, get_sources, get_env

logger = logging.getLogger(__name__)


class CoinGeckoCollector(BaseCollector):
    """Collects price, market cap, and volume data from CoinGecko API.

    Detects:
    - Price spikes (24h percentage change above threshold)
    - Market cap milestones (absolute threshold crossings)
    - Volume anomalies (24h volume vs market cap ratio)

    Rate limit: 30 req/min (free tier). Uses simple per-request delay.
    """

    CATEGORY = "FINANCIAL"
    DEFAULT_BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="CoinGecko", max_retries=max_retries, backoff_base=backoff_base)

        sources_cfg = get_sources()
        cg_cfg = sources_cfg.get("coingecko", {})
        self.base_url = cg_cfg.get("base_url", self.DEFAULT_BASE_URL)
        self.rate_limit_per_min = cg_cfg.get("rate_limit_per_min", 30)

        self._api_key = get_env("COINGECKO_API_KEY", "")
        if self._api_key:
            self.session.headers.update({"x-cg-demo-api-key": self._api_key})

        self._chains_cfg = get_chains()
        self._baselines_cfg = get_baselines()

        # Minimum interval between requests to respect rate limit
        self._min_interval = 60.0 / self.rate_limit_per_min
        self._last_request_time: float = 0.0

    def _rate_limited_fetch(self, url: str, params: dict = None) -> Optional[dict]:
        """Fetch with rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()
        return self.fetch_with_retry(url, params=params)

    def _make_signal(
        self,
        chain: str,
        description: str,
        reliability: float,
        evidence: dict,
    ) -> dict:
        return {
            "chain": chain,
            "category": self.CATEGORY,
            "description": description,
            "source": "CoinGecko",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _get_market_data(self, coingecko_id: str) -> Optional[dict]:
        """Fetch coin market data from CoinGecko /coins/{id} endpoint."""
        url = f"{self.base_url}/coins/{coingecko_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
        }
        data = self._rate_limited_fetch(url, params=params)
        if not data:
            return None
        return data.get("market_data")

    def _check_price_spike(
        self,
        chain: str,
        market_data: dict,
        baseline: dict,
    ) -> list[dict]:
        """Detect price spikes from 24h change percentage."""
        signals: list[dict] = []
        pct_24h = market_data.get("price_change_percentage_24h")
        if pct_24h is None:
            return signals

        spike_threshold = baseline.get("price_change_spike", 20)
        notable_threshold = baseline.get("price_change_notable", 10)
        current_price = market_data.get("current_price", {}).get("usd")

        if abs(pct_24h) >= spike_threshold:
            direction = "surged" if pct_24h > 0 else "dropped"
            desc = f"Price {direction} {abs(pct_24h):.1f}% in 24h"
            if current_price is not None:
                desc += f" (${current_price:,.4f})"
            signals.append(self._make_signal(
                chain=chain,
                description=desc,
                reliability=0.85,
                evidence={
                    "metric": "price_spike_24h",
                    "price_change_pct_24h": round(pct_24h, 2),
                    "current_price_usd": current_price,
                    "threshold": spike_threshold,
                },
            ))
        elif abs(pct_24h) >= notable_threshold:
            direction = "rose" if pct_24h > 0 else "fell"
            desc = f"Price {direction} {abs(pct_24h):.1f}% in 24h"
            if current_price is not None:
                desc += f" (${current_price:,.4f})"
            signals.append(self._make_signal(
                chain=chain,
                description=desc,
                reliability=0.7,
                evidence={
                    "metric": "price_notable_24h",
                    "price_change_pct_24h": round(pct_24h, 2),
                    "current_price_usd": current_price,
                    "threshold": notable_threshold,
                },
            ))

        return signals

    def _check_market_cap_milestone(
        self,
        chain: str,
        market_data: dict,
        baseline: dict,
    ) -> list[dict]:
        """Check if market cap has crossed a milestone."""
        signals: list[dict] = []
        mcap = market_data.get("market_cap", {}).get("usd")
        if mcap is None:
            return signals

        # Use tvl_absolute_milestone as a proxy for market cap milestones
        # if no dedicated mcap milestone is set
        milestone = baseline.get("market_cap_milestone")
        if milestone is None:
            return signals

        band = milestone * 0.05
        if mcap >= milestone and mcap < milestone + band:
            signals.append(self._make_signal(
                chain=chain,
                description=f"Market cap crossed ${milestone/1e9:.1f}B (current: ${mcap/1e9:.2f}B)",
                reliability=0.9,
                evidence={
                    "metric": "market_cap_milestone",
                    "market_cap_usd": mcap,
                    "milestone": milestone,
                },
            ))

        return signals

    def _check_volume_anomaly(
        self,
        chain: str,
        market_data: dict,
        baseline: dict,
    ) -> list[dict]:
        """Detect unusual volume relative to market cap."""
        signals: list[dict] = []
        vol_24h = market_data.get("total_volume", {}).get("usd")
        mcap = market_data.get("market_cap", {}).get("usd")
        if not vol_24h or not mcap or mcap == 0:
            return signals

        vol_mcap_ratio = vol_24h / mcap
        # Volume > 30% of market cap is notable for major tokens
        if vol_mcap_ratio > 0.30:
            signals.append(self._make_signal(
                chain=chain,
                description=f"High volume/MC ratio: {vol_mcap_ratio:.1%} (${vol_24h/1e6:.0f}M vol / ${mcap/1e9:.1f}B MC)",
                reliability=0.75,
                evidence={
                    "metric": "volume_mcap_anomaly",
                    "volume_24h_usd": vol_24h,
                    "market_cap_usd": mcap,
                    "vol_mcap_ratio": round(vol_mcap_ratio, 4),
                },
            ))

        return signals

    def collect(self) -> list[dict]:
        """Collect CoinGecko signals for all chains with coingecko_id.

        Returns:
            List of signal dicts with keys: chain, category, description,
            source, reliability, evidence.
        """
        signals: list[dict] = []

        for chain_name, chain_cfg in self._chains_cfg.items():
            coingecko_id = chain_cfg.get("coingecko_id")
            if not coingecko_id:
                continue

            baseline = self._baselines_cfg.get(chain_name, {})

            market_data = self._get_market_data(coingecko_id)
            if not market_data:
                logger.warning(f"[CoinGecko] No market data for {chain_name} ({coingecko_id})")
                continue

            signals.extend(self._check_price_spike(chain_name, market_data, baseline))
            signals.extend(self._check_market_cap_milestone(chain_name, market_data, baseline))
            signals.extend(self._check_volume_anomaly(chain_name, market_data, baseline))

        logger.info(f"[CoinGecko] Collected {len(signals)} signals")
        return signals
