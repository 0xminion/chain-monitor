"""Tests for EventCategorizer — keyword-based classification."""

import pytest
from processors.categorizer import EventCategorizer


@pytest.fixture
def categorizer():
    return EventCategorizer()


class TestCategorize:
    """Test keyword-based categorize() method."""

    def test_risk_alert(self, categorizer):
        ev = categorizer.categorize({"description": "Protocol hack drained $5M from bridge", "evidence": {}})
        assert ev["category"] == "RISK_ALERT"

    def test_regulatory(self, categorizer):
        ev = categorizer.categorize({"description": "SEC issues wells notice to protocol", "evidence": {}})
        assert ev["category"] == "REGULATORY"

    def test_financial(self, categorizer):
        ev = categorizer.categorize({"description": "TVL surged to $2.5 billion", "evidence": {}})
        assert ev["category"] == "FINANCIAL"

    def test_partnership(self, categorizer):
        ev = categorizer.categorize({"description": "Protocol announces partnership with Chainlink", "evidence": {}})
        assert ev["category"] == "PARTNERSHIP"

    def test_tech_event(self, categorizer):
        ev = categorizer.categorize({"description": "Mainnet upgrade goes live with new EIP", "evidence": {}})
        assert ev["category"] == "TECH_EVENT"

    def test_visibility(self, categorizer):
        ev = categorizer.categorize({"description": "Founder keynote at conference about ecosystem", "evidence": {}})
        assert ev["category"] == "VISIBILITY"

    def test_default_category(self, categorizer):
        ev = categorizer.categorize({"description": "Something that matches no keywords", "evidence": {}})
        assert ev["category"] == "TECH_EVENT"  # default

    def test_preserves_existing_category(self, categorizer):
        ev = categorizer.categorize({"description": "TVL reached $1B", "category": "FINANCIAL", "evidence": {}})
        assert ev["category"] == "FINANCIAL"

    def test_price_noise_filtered(self, categorizer):
        ev = categorizer.categorize({
            "description": "Bitcoin price prediction: could hit $120K",
            "category": "NEWS",
            "source": "RSS",
            "evidence": {},
        })
        assert ev["category"] == "PRICE_NOISE"
        assert ev["_filtered_price_noise"] is True

    def test_defillama_not_filtered(self, categorizer):
        """DefiLlama TVL data should NEVER be filtered as price noise."""
        ev = categorizer.categorize({
            "description": "TVL surged 40% in 7 days",
            "category": "FINANCIAL",
            "source": "DefiLlama",
            "evidence": {"pct_change": 40},
        })
        assert ev["category"] == "FINANCIAL"

    def test_subcategory_detected(self, categorizer):
        ev = categorizer.categorize({
            "description": "Protocol upgrade goes live: EIP-4844 activation complete",
            "evidence": {},
        })
        assert ev["category"] == "TECH_EVENT"
        assert ev["subcategory"] == "upgrade"

    def test_description_fallback(self, categorizer):
        """description is primary text source when evidence.text is empty."""
        ev = categorizer.categorize({
            "description": "Critical vulnerability found in bridge contract",
            "evidence": {},
        })
        assert ev["category"] == "RISK_ALERT"
