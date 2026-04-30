"""Daily digest formatter — agent-native.

The running agent reads the signals and writes the digest.
This module exists for backward compat and pipeline wiring only.
"""

import logging
from datetime import datetime, timezone
from processors.signal import Signal

logger = logging.getLogger(__name__)


class DailyDigestFormatter:
    """Backward-compat stub. The agent produces the digest."""

    def format(self, signals: list[Signal], source_health: dict = None, upcoming: list = None, source_health_detail: dict = None) -> str:
        if not signals:
            return "📊 Chain Monitor — No signals collected today. Agent digest deferred."

        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        count = len(signals)
        return (
            f"📊 Chain Monitor — {now}\n\n"
            f"{count} signal(s) collected.\n\n"
            "The running agent is responsible for writing the digest.\n"
            "Pass ctx.unique_events or ctx.chain_digests to your agent."
        )

    def should_send(self, signals: list[Signal]) -> bool:
        return True
