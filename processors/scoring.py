"""Signal scorer — assigns impact/urgency scores based on baselines."""

import logging
from typing import Optional

from config.loader import get_baselines, get_chains
from processors.signal import Signal

logger = logging.getLogger(__name__)


# Trader context templates per category
TRADER_TEMPLATES = {
    "TECH_EVENT": "{chain} upgrade/event affects {detail}. Watch: validator adoption, client diversity, ecosystem impact.",
    "PARTNERSHIP": "{chain} + {detail} partnership signals ecosystem expansion. Watch for follow-on protocol deployments.",
    "FINANCIAL": "{chain} {detail}. This is {context_direction} the baseline of {baseline}. Signal: {signal_type}.",
    "RISK_ALERT": "{chain} {detail} — incident detected. Check exposure. Monitor withdrawals and bridge risk.",
    "REGULATORY": "{detail}. Direct impact: token listing risk, exchange access. Timeline: immediate to 90 days.",
    "VISIBILITY": "{chain} {detail}. Chains with multiple visibility events often see narrative forming. Watch for confirmation.",
}

# Per-chain trader context overrides
CHAIN_TRADER_CONTEXT = {
    "ethereum": {
        "TECH_EVENT": "Expect gas fee volatility around upgrade. Validators need to update. Historically ETH sees 5-15% moves 2 weeks pre-upgrade.",
        "FINANCIAL": "Ethereum TVL = dominance metric. Shifts in ETH TVL share signal capital rotation to/from L2s.",
    },
    "bitcoin": {
        "REGULATORY": "BTC regulatory news flows through ETF issuers (BlackRock, Fidelity). Watch IBIT inflows/outflows.",
        "TECH_EVENT": "Bitcoin upgrades are rare and contentious. Any upgrade proposal is high-signal.",
    },
    "hyperliquid": {
        "FINANCIAL": "HYPE volume ATH often precedes CEX listing rumors.",
        "REGULATORY": "No regulatory clarity is the single biggest risk. Any regulatory mention is maximum severity.",
    },
    "monad": {
        "TECH_EVENT": "Governance proposals = pre-mainnet DeFi wave setup. Each passed proposal = capability unlocked for ecosystem.",
        "PARTNERSHIP": "Every major protocol on Monad = ecosystem validation. Track which top-50 protocols deploy.",
    },
    "xlayer": {
        "FINANCIAL": "OKX deploying capital without announcement = stealth accumulation. TVL is proxy for OKX ecosystem bet size.",
    },
}


class SignalScorer:
    """Scores raw events into signals with impact/urgency and trader context."""

    def __init__(self):
        self.baselines = get_baselines()
        self.chains = get_chains()

    def score(self, event: dict) -> Signal:
        """Score a raw event dict into a Signal."""
        chain = event.get("chain", "unknown")
        category = event.get("category", "TECH_EVENT")
        description = event.get("description", "")
        source = event.get("source", "unknown")
        reliability = event.get("reliability", 0.7)
        evidence = event.get("evidence", description)

        baseline = self.baselines.get(chain, {})
        impact, urgency = self._calculate_scores(event, category, baseline)
        trader_context = self._generate_trader_context(chain, category, description, baseline)

        signal = Signal(
            id=Signal.generate_id(chain, category, description),
            chain=chain,
            category=category,
            description=description,
            trader_context=trader_context,
            impact=impact,
            urgency=urgency,
            priority_score=impact * urgency,
        )
        signal.add_activity(source, reliability, evidence)

        return signal

    def _calculate_scores(self, event: dict, category: str, baseline: dict) -> tuple[int, int]:
        """Calculate impact and urgency scores."""
        impact = 2
        urgency = 1

        if category == "FINANCIAL":
            impact = self._score_financial(event, baseline)
        elif category == "TECH_EVENT":
            impact = self._score_tech(event, baseline)
        elif category == "RISK_ALERT":
            impact = self._score_risk(event, baseline)
        elif category == "REGULATORY":
            impact = self._score_regulatory(event, baseline)
        elif category == "PARTNERSHIP":
            impact = self._score_partnership(event)
        elif category == "VISIBILITY":
            impact = self._score_visibility(event)

        # Urgency
        subcategory = event.get("subcategory", "")
        if category == "RISK_ALERT" and subcategory in ("hack", "exploit", "outage"):
            urgency = 3
        elif category == "REGULATORY" and subcategory == "enforcement":
            urgency = 3
        elif category in ("FINANCIAL", "TECH_EVENT") and impact >= 4:
            urgency = 2
        elif subcategory == "governance_vote":
            urgency = 2
        else:
            urgency = 1

        # Hyperliquid regulatory override — only for enforcement, not approvals/licenses
        if event.get("chain") == "hyperliquid" and category == "REGULATORY":
            if event.get("subcategory") in ("enforcement", "general"):
                impact = baseline.get("regulatory_any_mention_impact", 5)

        return impact, urgency

    def _score_financial(self, event: dict, baseline: dict) -> int:
        subcategory = event.get("subcategory", "")
        if subcategory == "tvl_milestone":
            return 4
        elif subcategory == "tvl_spike":
            spike_pct = event.get("value", 0)
            if spike_pct >= baseline.get("tvl_change_spike", 25):
                return 4
            return 3
        elif subcategory == "volume_breakout":
            return 3
        elif subcategory == "funding_round":
            amount = event.get("value", 0)
            if amount >= 50_000_000:
                return 4
            return 3
        return 2

    def _score_tech(self, event: dict, baseline: dict) -> int:
        subcategory = event.get("subcategory", "")
        floor = baseline.get("upgrade_impact_floor", 3)
        if subcategory == "mainnet_launch":
            return 5
        elif subcategory == "upgrade":
            return max(floor, 4)
        elif subcategory == "release":
            return max(floor, 3)
        elif subcategory == "governance_passed":
            return 4
        elif subcategory == "governance_submitted":
            return 3
        elif subcategory == "audit":
            return 3
        return 2

    def _score_risk(self, event: dict, baseline: dict) -> int:
        subcategory = event.get("subcategory", "")
        amount = event.get("value", 0)
        if subcategory == "hack" and amount >= 10_000_000:
            return 5
        elif subcategory in ("hack", "exploit"):
            return 4
        elif subcategory == "outage":
            return 4
        elif subcategory == "critical_bug":
            return 4
        return 3

    def _score_regulatory(self, event: dict, baseline: dict) -> int:
        subcategory = event.get("subcategory", "")
        if subcategory == "enforcement":
            return 5
        elif subcategory in ("license", "approval"):
            return 4
        elif subcategory == "comment_period":
            return 3
        return 3

    def _score_partnership(self, event: dict) -> int:
        partner_tier = event.get("partner_tier", 2)
        if partner_tier == 1:
            return 4
        return 2

    def _score_visibility(self, event: dict) -> int:
        subcategory = event.get("subcategory", "")
        if subcategory in ("keynote", "hire", "departure"):
            return 3
        elif subcategory in ("ama", "conference", "podcast"):
            return 2
        return 2

    def _generate_trader_context(self, chain: str, category: str, description: str, baseline: dict) -> str:
        """Generate trader-relevant context for a signal."""
        # Check chain-specific overrides first
        chain_ctx = CHAIN_TRADER_CONTEXT.get(chain, {})
        if category in chain_ctx:
            return chain_ctx[category]

        # Fall back to template
        template = TRADER_TEMPLATES.get(category, "")
        if not template:
            return ""

        baseline_val = baseline.get("tvl_absolute_milestone", "N/A")
        notes = baseline.get("trader_context_notes", "")

        return template.format(
            chain=chain.capitalize(),
            detail=description[:80],
            baseline=f"${baseline_val:,.0f}" if isinstance(baseline_val, (int, float)) else str(baseline_val),
            context_direction="above" if "cross" in description.lower() else "near",
            signal_type="capital_inflow" if "up" in description.lower() else "ecosystem_activity",
        ) + (f" {notes}" if notes else "")
