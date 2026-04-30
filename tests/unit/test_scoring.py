"""Tests for SignalScorer — agent-native stubs.

The real semantic assessment is deferred to the running agent.
These tests verify the scorer produces valid Signal objects.
"""

import pytest
from processors.scoring import SignalScorer, AgentStubSignal


@pytest.fixture
def scorer():
    return SignalScorer()


def test_score_returns_signal(scorer):
    event = {"chain": "ethereum", "category": "TECH_EVENT", "description": "Mainnet upgrade"}
    signal = scorer.score(event)
    assert signal.chain == "ethereum"
    assert signal.category == "TECH_EVENT"
    assert signal.description == "Mainnet upgrade"


def test_stub_scores(scorer):
    event = {"chain": "solana", "category": "RISK_ALERT", "description": "Hack"}
    signal = scorer.score(event)
    assert signal.impact == AgentStubSignal.default_impact
    assert signal.urgency == AgentStubSignal.default_urgency
    assert signal.priority_score == AgentStubSignal.default_priority


def test_signal_has_activity(scorer):
    event = {"chain": "base", "category": "PARTNERSHIP", "description": "Integration", "source": "RSS", "reliability": 0.8}
    signal = scorer.score(event)
    assert len(signal.activity) == 1
    assert signal.activity[0]["source"] == "RSS"


class TestStubDefaults:
    def test_default_impact(self):
        assert AgentStubSignal.default_impact == 3

    def test_default_urgency(self):
        assert AgentStubSignal.default_urgency == 2

    def test_default_priority(self):
        assert AgentStubSignal.default_priority == 6
