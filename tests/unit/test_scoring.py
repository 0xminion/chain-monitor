"""Tests for SignalScorer."""

import pytest
from processors.scoring import SignalScorer, CHAIN_TRADER_CONTEXT, TRADER_TEMPLATES


@pytest.fixture
def scorer(mock_config):
    return SignalScorer()


class TestFinancialScoring:
    """Test FINANCIAL category scoring."""

    def test_tvl_milestone_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "TVL milestone", "subcategory": "tvl_milestone"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_tvl_spike_above_threshold(self, scorer):
        event = {
            "chain": "ethereum",
            "category": "FINANCIAL",
            "description": "TVL spike",
            "subcategory": "tvl_spike",
            "value": 30,  # above 25% threshold
        }
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_tvl_spike_below_threshold(self, scorer):
        event = {
            "chain": "ethereum",
            "category": "FINANCIAL",
            "description": "TVL spike",
            "subcategory": "tvl_spike",
            "value": 20,  # below 25% threshold
        }
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_volume_breakout_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "vol", "subcategory": "volume_breakout"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_funding_round_large(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "funding", "subcategory": "funding_round", "value": 60_000_000}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_funding_round_small(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "funding", "subcategory": "funding_round", "value": 10_000_000}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_financial_default(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "something", "subcategory": "other"}
        signal = scorer.score(event)
        assert signal.impact == 2


class TestTechScoring:
    """Test TECH_EVENT category scoring."""

    def test_upgrade_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "upgrade", "subcategory": "upgrade"}
        signal = scorer.score(event)
        # floor=4 for ethereum, so max(4,4) = 4
        assert signal.impact == 4

    def test_release_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "release v1", "subcategory": "release"}
        signal = scorer.score(event)
        # floor=4 for ethereum, so max(4,3) = 4
        assert signal.impact == 4

    def test_governance_passed_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "proposal passed", "subcategory": "governance_passed"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_governance_submitted_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "proposal submitted", "subcategory": "governance_submitted"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_mainnet_launch_is_5(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "mainnet launch", "subcategory": "mainnet_launch"}
        signal = scorer.score(event)
        assert signal.impact == 5

    def test_audit_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "audit complete", "subcategory": "audit"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_tech_default(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "misc", "subcategory": "unknown"}
        signal = scorer.score(event)
        assert signal.impact == 2


class TestRiskScoring:
    """Test RISK_ALERT category scoring."""

    def test_hack_over_10m_is_5(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "hack", "subcategory": "hack", "value": 15_000_000}
        signal = scorer.score(event)
        assert signal.impact == 5

    def test_hack_under_10m_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "hack", "subcategory": "hack", "value": 5_000_000}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_exploit_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "exploit", "subcategory": "exploit"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_outage_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "outage", "subcategory": "outage"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_critical_bug_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "critical bug", "subcategory": "critical_bug"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_risk_default_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "risk", "subcategory": "unknown"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_hack_urgency_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "hack", "subcategory": "hack", "value": 5_000_000}
        signal = scorer.score(event)
        assert signal.urgency == 3


class TestRegulatoryScoring:
    """Test REGULATORY category scoring."""

    def test_enforcement_is_5(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "enforcement", "subcategory": "enforcement"}
        signal = scorer.score(event)
        assert signal.impact == 5

    def test_license_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "license", "subcategory": "license"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_approval_is_4(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "approval", "subcategory": "approval"}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_comment_period_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "comment", "subcategory": "comment_period"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_enforcement_urgency_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "enforcement", "subcategory": "enforcement"}
        signal = scorer.score(event)
        assert signal.urgency == 3


class TestPartnershipScoring:
    """Test PARTNERSHIP category scoring."""

    def test_tier1_partnership_is_4(self, scorer):
        event = {"chain": "monad", "category": "PARTNERSHIP", "description": "collab", "partner_tier": 1}
        signal = scorer.score(event)
        assert signal.impact == 4

    def test_tier2_partnership_is_2(self, scorer):
        event = {"chain": "monad", "category": "PARTNERSHIP", "description": "collab", "partner_tier": 2}
        signal = scorer.score(event)
        assert signal.impact == 2


class TestVisibilityScoring:
    """Test VISIBILITY category scoring."""

    def test_keynote_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "VISIBILITY", "description": "keynote", "subcategory": "keynote"}
        signal = scorer.score(event)
        assert signal.impact == 3

    def test_ama_is_2(self, scorer):
        event = {"chain": "ethereum", "category": "VISIBILITY", "description": "ama", "subcategory": "ama"}
        signal = scorer.score(event)
        assert signal.impact == 2

    def test_hire_is_3(self, scorer):
        event = {"chain": "ethereum", "category": "VISIBILITY", "description": "new hire", "subcategory": "hire"}
        signal = scorer.score(event)
        assert signal.impact == 3


class TestChainSpecificOverrides:
    """Test chain-specific overrides."""

    def test_hyperliquid_regulatory_override(self, scorer):
        event = {"chain": "hyperliquid", "category": "REGULATORY", "description": "SEC enforcement action", "subcategory": "enforcement"}
        signal = scorer.score(event)
        # Enforcement should be overridden to regulatory_any_mention_impact=5
        assert signal.impact == 5

    def test_hyperliquid_regulatory_no_override_for_approvals(self, scorer):
        event = {"chain": "hyperliquid", "category": "REGULATORY", "description": "license approved", "subcategory": "license"}
        signal = scorer.score(event)
        # Approvals/licenses should NOT get the override
        assert signal.impact == 4  # normal license scoring

    def test_non_hyperliquid_regulatory_normal(self, scorer):
        event = {"chain": "ethereum", "category": "REGULATORY", "description": "comment", "subcategory": "comment_period"}
        signal = scorer.score(event)
        assert signal.impact == 3


class TestTraderContext:
    """Test trader context generation."""

    def test_chain_specific_context(self, scorer):
        event = {"chain": "hyperliquid", "category": "REGULATORY", "description": "enforcement", "subcategory": "enforcement"}
        signal = scorer.score(event)
        assert "regulatory" in signal.trader_context.lower() or "risk" in signal.trader_context.lower()

    def test_template_context_for_unknown_chain(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "bridge hack drained funds", "subcategory": "hack"}
        signal = scorer.score(event)
        assert "exposure" in signal.trader_context.lower() or "incident" in signal.trader_context.lower()

    def test_financial_template_context(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "TVL crossed milestone", "subcategory": "tvl_milestone"}
        signal = scorer.score(event)
        assert signal.trader_context != ""
        assert "Ethereum" in signal.trader_context or "baseline" in signal.trader_context.lower()

    def test_trader_templates_exist(self):
        assert "TECH_EVENT" in TRADER_TEMPLATES
        assert "FINANCIAL" in TRADER_TEMPLATES
        assert "RISK_ALERT" in TRADER_TEMPLATES
        assert "REGULATORY" in TRADER_TEMPLATES
        assert "PARTNERSHIP" in TRADER_TEMPLATES
        assert "VISIBILITY" in TRADER_TEMPLATES

    def test_chain_trader_context_has_key_chains(self):
        assert "ethereum" in CHAIN_TRADER_CONTEXT
        assert "hyperliquid" in CHAIN_TRADER_CONTEXT
        assert "bitcoin" in CHAIN_TRADER_CONTEXT


class TestUrgencyScoring:
    """Test urgency calculations."""

    def test_risk_hack_urgency_3(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "hack", "subcategory": "hack"}
        signal = scorer.score(event)
        assert signal.urgency == 3

    def test_risk_exploit_urgency_3(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "exploit", "subcategory": "exploit"}
        signal = scorer.score(event)
        assert signal.urgency == 3

    def test_risk_outage_urgency_3(self, scorer):
        event = {"chain": "ethereum", "category": "RISK_ALERT", "description": "outage", "subcategory": "outage"}
        signal = scorer.score(event)
        assert signal.urgency == 3

    def test_high_impact_financial_urgency_2(self, scorer):
        event = {"chain": "ethereum", "category": "FINANCIAL", "description": "TVL milestone", "subcategory": "tvl_milestone"}
        signal = scorer.score(event)
        # impact=4 >= 4, so urgency=2
        assert signal.urgency == 2

    def test_governance_vote_urgency_2(self, scorer):
        event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "vote", "subcategory": "governance_vote"}
        signal = scorer.score(event)
        assert signal.urgency == 2

    def test_default_urgency_1(self, scorer):
        event = {"chain": "ethereum", "category": "VISIBILITY", "description": "podcast", "subcategory": "podcast"}
        signal = scorer.score(event)
        assert signal.urgency == 1


class TestTwitterScoring:
    """Test Twitter role-aware scoring tiers."""

    def test_official_twitter_is_p9(self, scorer):
        event = {
            "chain": "solana",
            "category": "VISIBILITY",
            "description": "Mainnet upgrade schedule released",
            "source": "twitter",
            "evidence": {"role": "official"},
        }
        signal = scorer.score(event)
        assert signal.impact == 9
        assert signal.urgency == 1
        assert signal.priority_score == 9

    def test_contributor_twitter_is_p6(self, scorer):
        event = {
            "chain": "ethereum",
            "category": "TECH_EVENT",
            "description": "New PR merged for rollup client",
            "source": "twitter",
            "evidence": {"role": "contributor"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 2
        assert signal.priority_score == 6

    def test_core_contributor_twitter_is_p6(self, scorer):
        event = {
            "chain": "monad",
            "category": "TECH_EVENT",
            "description": "Devnet reset completed",
            "source": "twitter",
            "evidence": {"role": "core contributor"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 2
        assert signal.priority_score == 6

    def test_engagement_only_twitter_is_p3(self, scorer):
        event = {
            "chain": "base",
            "category": "NEWS",
            "description": "GM 🚀🔥",
            "source": "twitter",
            "evidence": {"role": "unknown"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 1
        assert signal.priority_score == 3

    def test_empty_text_twitter_is_p3(self, scorer):
        event = {
            "chain": "arbitrum",
            "category": "NEWS",
            "description": "",
            "source": "twitter",
            "evidence": {"role": "community"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 1
        assert signal.priority_score == 3

    def test_short_nonsubstantive_twitter_is_p3(self, scorer):
        event = {
            "chain": "optimism",
            "category": "NEWS",
            "description": "Bullish AF",
            "source": "twitter",
            "evidence": {"role": "community"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 1
        assert signal.priority_score == 3

    def test_fallback_twitter_is_p3(self, scorer):
        event = {
            "chain": "polygon",
            "category": "NEWS",
            "description": "Some random thread about validators",
            "source": "twitter",
            "evidence": {"role": "community"},
        }
        signal = scorer.score(event)
        assert signal.impact == 3
        assert signal.urgency == 1
        assert signal.priority_score == 3

    def test_non_twitter_not_affected(self, scorer):
        event = {
            "chain": "ethereum",
            "category": "FINANCIAL",
            "description": "TVL milestone",
            "subcategory": "tvl_milestone",
            "source": "defillama",
        }
        signal = scorer.score(event)
        assert signal.impact == 4
        assert signal.urgency == 2
