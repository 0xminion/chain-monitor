"""Tests for EventCategorizer — agent-native pass-through."""

import pytest
from processors.categorizer import EventCategorizer, VALID_CATEGORIES, validate_category


class TestAgentNativePassThrough:
    """Agent-native: categorizer validates but does NOT auto-classify."""

    def test_hack_event_preserved_as_is(self):
        c = EventCategorizer()
        event = {"description": "Protocol hack drained $5M", "category": "RISK_ALERT"}
        result = c.categorize(event)
        assert result["category"] == "RISK_ALERT"

    def test_invalid_category_normalized(self):
        c = EventCategorizer()
        event = {"description": "Something", "category": "BOGUS"}
        result = c.categorize(event)
        assert result["category"] == "NEWS"

    def test_unknown_category_defaults(self):
        c = EventCategorizer()
        event = {"description": "Something happened"}
        result = c.categorize(event)
        assert result["category"] == "NEWS"
        assert result["subcategory"] == "general"

    def test_valid_categories_set(self):
        assert "RISK_ALERT" in VALID_CATEGORIES
        assert "TECH_EVENT" in VALID_CATEGORIES
        assert "NOISE" in VALID_CATEGORIES

    def test_semantic_slot_reserved(self):
        c = EventCategorizer()
        event = {"chain": "ethereum", "description": "Mainnet launch"}
        result = c.categorize(event)
        assert "semantic" in result
        assert result["semantic"] is None  # agent fills this

    def test_subcategory_validated(self):
        c = EventCategorizer()
        event = {"description": "Test", "category": "TECH_EVENT", "subcategory": "upgrade"}
        result = c.categorize(event)
        assert result["subcategory"] == "upgrade"

    def test_subcategory_invalid_normalized(self):
        c = EventCategorizer()
        event = {"description": "Test", "category": "NEWS", "subcategory": "fake_sub"}
        result = c.categorize(event)
        assert result["subcategory"] == "general"
