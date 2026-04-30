"""Event categorizer — agent-native semantic layer.

Provides the taxonomy and validation helpers for the running agent.
Semantic classification is performed by the agent reading the events.

No keyword matching. No external LLM API calls.
"""

import logging

logger = logging.getLogger(__name__)

CATEGORY_TAXONOMY = {
    "RISK_ALERT": "Security incidents, hacks, exploits, breaches, outages, critical bugs",
    "REGULATORY": "SEC actions, lawsuits, licensing, compliance, bans, comment periods",
    "FINANCIAL": "TVL shifts, funding rounds, airdrops, grants, token launches, treasury",
    "PARTNERSHIP": "Integrations, deployments, collaborations, ecosystem expansions",
    "TECH_EVENT": "Upgrades, mainnet launches, testnets, audits, releases, governance",
    "VISIBILITY": "Conferences, AMAs, key hirings, keynotes, community calls, podcasts",
    "NEWS": "General ecosystem news not fitting above categories",
    "NOISE": "Low-value content (price predictions, engagement bait, GM threads)",
    "PRICE_NOISE": "Trading commentary, technical analysis, bullish/bearish sentiment",
}

VALID_CATEGORIES = frozenset(CATEGORY_TAXONOMY.keys())

VALID_SUBCATEGORIES = frozenset({
    "hack", "exploit", "outage", "critical_bug", "scam",
    "enforcement", "license", "approval", "comment_period", "lawsuit",
    "tvl_milestone", "tvl_spike", "funding_round", "airdrop", "tge",
    "integration", "collaboration", "deployment",
    "mainnet_launch", "upgrade", "release", "governance_passed", "audit",
    "keynote", "ama", "hire", "departure", "podcast",
    "general",
})


def validate_category(cat: str) -> str:
    cat = str(cat).upper().strip()
    return cat if cat in VALID_CATEGORIES else "NEWS"


def validate_subcat(sub: str) -> str:
    sub = str(sub).lower().strip()
    return sub if sub in VALID_SUBCATEGORIES else "general"


class EventCategorizer:
    """Agent-native categorizer. No auto-classification."""

    def __init__(self):
        logger.info("[categorizer] Agent-native mode — taxonomy loaded, classification deferred to agent")

    def categorize(self, event: dict) -> dict:
        event["category"] = validate_category(event.get("category", "NEWS"))
        event["subcategory"] = validate_subcat(event.get("subcategory", "general"))
        event.setdefault("semantic", None)  # reserved for agent reasoning output
        return event
