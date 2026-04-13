"""DefiLlama collector — TVL, fees, volume signals."""

import logging
from datetime import datetime, timezone
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_chains, get_baselines, get_sources, get_env

logger = logging.getLogger(__name__)


class DefiLlamaCollector(BaseCollector):
    """Collects TVL, fees, and volume data from DefiLlama API.

    Detects:
    - TVL spikes (current vs 7d ago percentage change)
    - TVL milestones (absolute threshold crossings)
    - Volume breakouts (multiplier vs baseline)
    """

    CATEGORY = "FINANCIAL"

    def __init__(self, max_retries: int = 3, backoff_base: int = 2):
        super().__init__(name="DefiLlama", max_retries=max_retries, backoff_base=backoff_base)
        sources_cfg = get_sources()
        dl_cfg = sources_cfg.get("defillama", {})
        self.chains_endpoint = dl_cfg.get("chains_endpoint", "https://api.llama.fi/chains")
        self.tvl_endpoint = dl_cfg.get("tvl_endpoint", "https://api.llama.fi/v2/historicalChainTvl")
        self.fees_endpoint = dl_cfg.get("fees_endpoint", "https://api.llama.fi/overview/fees")

        self._chains_cfg = get_chains()
        self._baselines_cfg = get_baselines()

        # Build lookup: defillama_slug -> chain_name
        self._slug_to_chain: dict[str, str] = {}
        for chain_name, cfg in self._chains_cfg.items():
            slug = cfg.get("defillama_slug")
            if slug:
                self._slug_to_chain[slug.lower()] = chain_name

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
            "source": "DefiLlama",
            "reliability": min(max(reliability, 0.0), 1.0),
            "evidence": evidence,
        }

    def _check_tvl_spike(self, chain: str, slug: str, baseline: dict) -> list[dict]:
        """Compare current TVL to 7d-ago TVL; emit spike signal if above threshold."""
        signals: list[dict] = []
        data = self.fetch_with_retry(f"{self.tvl_endpoint}/{slug}")
        if not data or not isinstance(data, list) or len(data) < 2:
            return signals

        # Sort by date ascending
        try:
            data.sort(key=lambda x: x.get("date", 0))
        except (TypeError, KeyError):
            return signals

        latest = data[-1]
        current_tvl = latest.get("tvl")
        if current_tvl is None:
            return signals

        # Find entry ~7 days ago (unix timestamp, 7*86400 = 604800)
        target_ts = latest["date"] - 604800
        week_ago_entry = None
        for entry in reversed(data):
            if entry.get("date", 0) <= target_ts:
                week_ago_entry = entry
                break

        if not week_ago_entry or not week_ago_entry.get("tvl"):
            return signals

        old_tvl = week_ago_entry["tvl"]
        pct_change = ((current_tvl - old_tvl) / old_tvl) * 100

        spike_threshold = baseline.get("tvl_change_spike", 30)
        notable_threshold = baseline.get("tvl_change_notable", 15)

        if abs(pct_change) >= spike_threshold:
            direction = "surged" if pct_change > 0 else "dropped"
            signals.append(self._make_signal(
                chain=chain,
                description=f"TVL {direction} {abs(pct_change):.1f}% in 7 days (${current_tvl/1e9:.2f}B)",
                reliability=0.85,
                evidence={
                    "metric": "tvl_7d_change",
                    "current_tvl": current_tvl,
                    "tvl_7d_ago": old_tvl,
                    "pct_change": round(pct_change, 2),
                    "threshold": spike_threshold,
                },
            ))
        elif abs(pct_change) >= notable_threshold:
            direction = "increased" if pct_change > 0 else "decreased"
            signals.append(self._make_signal(
                chain=chain,
                description=f"TVL {direction} {abs(pct_change):.1f}% in 7 days (${current_tvl/1e9:.2f}B)",
                reliability=0.7,
                evidence={
                    "metric": "tvl_7d_notable",
                    "current_tvl": current_tvl,
                    "tvl_7d_ago": old_tvl,
                    "pct_change": round(pct_change, 2),
                    "threshold": notable_threshold,
                },
            ))

        return signals

    def _check_tvl_milestone(self, chain: str, current_tvl: float, baseline: dict) -> list[dict]:
        """Check if TVL has crossed an absolute milestone."""
        signals: list[dict] = []
        milestone = baseline.get("tvl_absolute_milestone")
        if milestone is None:
            return signals

        # Detect crossing: current is above milestone, we flag it once
        # Use 5% band to avoid re-triggering every cycle
        band = milestone * 0.05
        if current_tvl >= milestone and current_tvl < milestone + band:
            signals.append(self._make_signal(
                chain=chain,
                description=f"TVL crossed ${milestone/1e9:.1f}B milestone (current: ${current_tvl/1e9:.2f}B)",
                reliability=0.9,
                evidence={
                    "metric": "tvl_milestone",
                    "current_tvl": current_tvl,
                    "milestone": milestone,
                },
            ))

        return signals

    def _check_volume_breakout(self, chain: str, slug: str, baseline: dict) -> list[dict]:
        """Check for volume breakouts via DefiLlama fees/volume endpoint."""
        signals: list[dict] = []
        multiplier_threshold = baseline.get("volume_spike_multiplier")
        if multiplier_threshold is None:
            return signals

        # DefiLlama overview/fees returns volume data with optional chain filter
        data = self.fetch_with_retry(f"{self.fees_endpoint}/{slug}")
        if not data:
            return signals

        # The endpoint returns total24h, total48hto24h for comparison
        vol_24h = data.get("total24h")
        vol_prev_24h = data.get("total48hto24h")
        if vol_24h is None or vol_prev_24h is None or vol_prev_24h == 0:
            return signals

        ratio = vol_24h / vol_prev_24h
        if ratio >= multiplier_threshold:
            signals.append(self._make_signal(
                chain=chain,
                description=f"Volume breakout: {ratio:.1f}x vs prior 24h (${vol_24h/1e6:.1f}M today)",
                reliability=0.8,
                evidence={
                    "metric": "volume_breakout",
                    "volume_24h": vol_24h,
                    "volume_prev_24h": vol_prev_24h,
                    "ratio": round(ratio, 2),
                    "threshold": multiplier_threshold,
                },
            ))

        return signals

    def collect(self) -> list[dict]:
        """Collect DefiLlama signals for all configured chains.

        Returns:
            List of signal dicts with keys: chain, category, description,
            source, reliability, evidence.
        """
        signals: list[dict] = []

        # Fetch all chains TVL overview to get current values
        all_chains = self.fetch_with_retry(self.chains_endpoint)
        if not all_chains or not isinstance(all_chains, list):
            logger.error("[DefiLlama] Failed to fetch chains overview")
            return signals

        # Index by slug
        chain_tvl_map: dict[str, float] = {}
        for entry in all_chains:
            slug = entry.get("gecko_id") or entry.get("name", "")
            tvl = entry.get("tvl")
            # DefiLlama uses lowercase name as slug in the overview
            name_slug = (entry.get("name") or "").lower()
            if name_slug and tvl is not None:
                chain_tvl_map[name_slug] = tvl

        # Process each configured chain
        for chain_name, chain_cfg in self._chains_cfg.items():
            slug = chain_cfg.get("defillama_slug")
            if not slug:
                continue

            baseline = self._baselines_cfg.get(chain_name, {})

            # TVL spike detection (fetches historical data per chain)
            signals.extend(self._check_tvl_spike(chain_name, slug, baseline))

            # TVL milestone detection (use overview data)
            current_tvl = chain_tvl_map.get(slug.lower())
            if current_tvl is not None:
                signals.extend(self._check_tvl_milestone(chain_name, current_tvl, baseline))

            # Volume breakout detection
            signals.extend(self._check_volume_breakout(chain_name, slug, baseline))

        logger.info(f"[DefiLlama] Collected {len(signals)} signals")
        return signals
