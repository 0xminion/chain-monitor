"""Summary engine — agent-native stub.

The agent reads the ChainDigests and writes the digest.
This module exists for pipeline wiring only.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from processors.pipeline_types import ChainDigest

logger = logging.getLogger(__name__)


async def synthesize_digest(
    digests: list[ChainDigest],
    source_health: Optional[dict] = None,
    source_health_detail: Optional[dict] = None,
    client=None,
    date_str: Optional[str] = None,
) -> str:
    """Agent-native synthesize stub.

    Returns a message telling the agent to read the digests and produce prose.
    Override this function or replace the caller to plug in your own agent.
    """
    if not digests:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        return (
            f"📊 Chain Monitor — {now}\n\n"
            "Quiet day across monitored chains. No events detected."
        )

    date_str = date_str or datetime.now(timezone.utc).strftime("%b %d, %Y")

    lines = [
        f"📊 Chain Monitor — {date_str}",
        "",
        "🤖 Agent mode active",
        "",
        "The running agent is responsible for synthesizing this digest.",
        "Pass the chain digests (see ctx.chain_digests) to your agent.",
        "",
        f"Chains with data: {len([d for d in digests if d.event_count > 0])}",
        f"Total key events: {sum(len(d.key_events) for d in digests)}",
        "",
        "Use processors.agent_bridge.events_to_agent_prompt() to build a rich prompt.",
    ]

    if source_health:
        healthy = sum(1 for h in source_health.values() if str(h.get("status", "")).lower() in ("healthy", "ok", "up"))
        total = len(source_health)
        lines.append(f"\n⚠️ Source health: {healthy}/{total} healthy")

    return "\n".join(lines)
