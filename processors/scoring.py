"""Signal scorer — agent-native. The agent decides priority, not formulas.

The pipeline still creates Signal objects for backward compat, but scores
are stubs (impact=3, urgency=2, priority=6) that the agent rewrites after
reading.
"""

import logging
from processors.signal import Signal

logger = logging.getLogger(__name__)


class AgentStubSignal:
    """Stub signal with placeholder scores.

    The agent replaces these after semantic analysis.
    """
    default_impact: int = 3
    default_urgency: int = 2
    default_priority: int = 6


class SignalScorer:
    def __init__(self):
        logger.info("[scorer] Agent-native mode — scores deferred to agent")

    def score(self, event: dict) -> Signal:
        chain = event.get("chain", "unknown")
        category = event.get("category", "NEWS")
        description = event.get("description", "")
        source = event.get("source", "unknown")
        reliability = event.get("reliability", 0.7)
        evidence = event.get("evidence", description)

        signal = Signal(
            id=Signal.generate_id(chain, category, description),
            chain=chain,
            category=category,
            description=description,
            trader_context="",  # agent fills this
            impact=AgentStubSignal.default_impact,
            urgency=AgentStubSignal.default_urgency,
            priority_score=AgentStubSignal.default_priority,
        )
        signal.add_activity(source, reliability, evidence)
        return signal
