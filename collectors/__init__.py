"""Chain Monitor Collectors Package."""

from collectors.defillama import DefiLlamaCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.github_collector import GitHubCollector
from collectors.rss_collector import RSSCollector
from collectors.regulatory_collector import RegulatoryCollector
from collectors.risk_alert_collector import RiskAlertCollector
from collectors.tradingview_collector import TradingViewCollector
from collectors.events_collector import EventsCollector
from collectors.hackathon_outcomes_collector import HackathonOutcomesCollector

__all__ = [
    "DefiLlamaCollector",
    "CoinGeckoCollector",
    "GitHubCollector",
    "RSSCollector",
    "RegulatoryCollector",
    "RiskAlertCollector",
    "TradingViewCollector",
    "EventsCollector",
    "HackathonOutcomesCollector",
]
