"""Tests for EventCategorizer."""

import pytest
from processors.categorizer import EventCategorizer, CATEGORY_KEYWORDS, SUBCATEGORY_MAP


@pytest.fixture
def categorizer():
    return EventCategorizer()


class TestCategoryDetection:
    """Test primary category detection."""

    def test_hack_to_risk_alert(self, categorizer):
        event = {"description": "Protocol hack drained $5M", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_exploit_to_risk_alert(self, categorizer):
        event = {"description": "Exploit found in bridge contract", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_outage_to_risk_alert(self, categorizer):
        event = {"description": "Network outage halts transactions", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_vulnerability_to_risk_alert(self, categorizer):
        event = {"description": "Critical vulnerability disclosed", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_partnership_detected(self, categorizer):
        event = {"description": "Partnership announced with Chainlink", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "PARTNERSHIP"

    def test_integration_to_partnership(self, categorizer):
        event = {"description": "New integration with Uniswap", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "PARTNERSHIP"

    def test_sec_to_regulatory(self, categorizer):
        event = {"description": "SEC issues wells notice", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "REGULATORY"

    def test_enforcement_to_regulatory(self, categorizer):
        event = {"description": "Enforcement action filed by SEC", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "REGULATORY"

    def test_tvl_to_financial(self, categorizer):
        event = {"description": "TVL crosses $1B milestone", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "FINANCIAL"

    def test_funding_to_financial(self, categorizer):
        event = {"description": "Project raised $50M in Series B", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "FINANCIAL"

    def test_airdrop_to_financial(self, categorizer):
        event = {"description": "Airdrop announced for early users", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "FINANCIAL"

    def test_upgrade_to_tech_event(self, categorizer):
        event = {"description": "Mainnet upgrade scheduled", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "TECH_EVENT"

    def test_release_to_tech_event(self, categorizer):
        event = {"description": "New version v2.0 release", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "TECH_EVENT"

    def test_conference_to_visibility(self, categorizer):
        event = {"description": "Conference keynote at ETHDenver", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "VISIBILITY"

    def test_hired_to_visibility(self, categorizer):
        event = {"description": "New CTO hired for protocol", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "VISIBILITY"

    def test_podcast_to_visibility(self, categorizer):
        event = {"description": "Founder joins podcast interview panel", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "VISIBILITY"


class TestDefaultFallback:
    """Test default fallback to TECH_EVENT."""

    def test_unknown_event_defaults_to_tech(self, categorizer):
        event = {"description": "Something happened with the network", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "TECH_EVENT"

    def test_empty_description_defaults_to_tech(self, categorizer):
        event = {"description": "", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "TECH_EVENT"

    def test_missing_description_defaults_to_tech(self, categorizer):
        event = {}
        result = categorizer.categorize(event)
        assert result["category"] == "TECH_EVENT"


class TestSubcategoryDetection:
    """Test subcategory detection."""

    def test_hack_subcategory(self, categorizer):
        event = {"description": "Protocol hack drained funds", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "hack"

    def test_outage_subcategory(self, categorizer):
        event = {"description": "Network outage for 2 hours", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "outage"

    def test_critical_bug_subcategory(self, categorizer):
        event = {"description": "Critical bug found in consensus", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "critical_bug"

    def test_enforcement_subcategory(self, categorizer):
        event = {"description": "SEC enforcement action filed", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "enforcement"

    def test_license_subcategory(self, categorizer):
        event = {"description": "License approved by regulator", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "license"

    def test_tvl_milestone_subcategory(self, categorizer):
        event = {"description": "TVL crosses $5B milestone", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "tvl_milestone"

    def test_airdrop_subcategory(self, categorizer):
        event = {"description": "Airdrop token distribution announced", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "airdrop"

    def test_volume_breakout_subcategory(self, categorizer):
        event = {"description": "Volume at all-time high record breakout", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "volume_breakout"

    def test_funding_round_subcategory(self, categorizer):
        event = {"description": "Funding raised $20M round", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "funding_round"

    def test_upgrade_subcategory(self, categorizer):
        event = {"description": "Hard fork upgrade scheduled", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "upgrade"

    def test_governance_passed_subcategory(self, categorizer):
        event = {"description": "Proposal passed governance vote", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "governance_passed"

    def test_integration_subcategory(self, categorizer):
        event = {"description": "Integration with Aave deployed", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "integration"

    def test_keynote_subcategory(self, categorizer):
        event = {"description": "Keynote speaker at conference", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "keynote"

    def test_ama_subcategory(self, categorizer):
        event = {"description": "AMA with community call", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "ama"

    def test_hire_subcategory(self, categorizer):
        event = {"description": "New CTO hired for team", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "hire"

    def test_departure_subcategory(self, categorizer):
        event = {"description": "Lead dev departed from project", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["subcategory"] == "departure"

    def test_general_subcategory_fallback(self, categorizer):
        event = {"description": "Something regulatory happened", "evidence": ""}
        result = categorizer.categorize(event)
        # No specific subcategory match in REGULATORY -> general
        assert result["subcategory"] == "general"

    def test_evidence_field_also_searched(self, categorizer):
        event = {"description": "Update posted", "evidence": "Protocol hack confirmed by team"}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"
        assert result["subcategory"] == "hack"


class TestCategoryKeywordOrder:
    """Verify category keyword priority order."""

    def test_risk_takes_priority_over_tech(self, categorizer):
        # "halt" is RISK_ALERT, "upgrade" is TECH_EVENT
        # RISK_ALERT comes first in CATEGORY_KEYWORDS
        event = {"description": "Network halt during upgrade", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_regulatory_takes_priority_over_financial(self, categorizer):
        event = {"description": "SEC fine imposed on token sale", "evidence": ""}
        result = categorizer.categorize(event)
        assert result["category"] == "REGULATORY"
