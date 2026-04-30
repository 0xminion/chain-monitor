"""Summary engine — synthesize chain digests into final Telegram digest.

v2.0: Fully agent-native. Uses structured deterministic formatting — no LLM calls,
no external APIs, no tokens required. Anyone can clone and run this without any API keys.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from processors.pipeline_types import ChainDigest

logger = logging.getLogger(__name__)


# ── Chain emoji mapping ──────────────────────────────────────────────────────
_CHAIN_EMOJIS = {
    "solana": "⚡",
    "base": "🔵",
    "ethereum": "⬡",
    "bitcoin": "🟠",
    "sui": "💧",
    "aptos": "🅰️",
    "arbitrum": "🔷",
    "optimism": "🔴",
    "hyperliquid": "⚗️",
    "monad": "🔮",
    "xlayer": "❌",
    "bsc": "🟡",
    "polkadot": "🔘",
    "cosmos": "🌌",
    "cardano": "🔷",
    "algorand": "△",
    "near": "🌑",
    "starknet": "🦁",
    "zksync": "💎",
    "mantle": "🟤",
}


def _chain_emoji(chain: str) -> str:
    """Return emoji prefix for a chain name."""
    return _CHAIN_EMOJIS.get(chain.lower(), "🔗")


def _fmt_event_link(ke: dict) -> str:
    """Build a markdown link on the first content-bearing word if URL exists."""
    topic = ke.get("topic", "Event")
    url = ke.get("url", "")
    if not url:
        return topic
    words = topic.split()
    if not words:
        return topic
    return f"[{words[0]}]({url}) {' '.join(words[1:])}".strip()


def _build_digest(digests: list[ChainDigest], date_str: str) -> str:
    """Agent-native digest builder: deterministic, no LLM, no external API."""
    lines = [
        f"📊 Chain Monitor — {date_str}",
        "",
        "🧠 Today's theme",
    ]

    if not digests:
        lines.append("Quiet day across monitored chains. No significant events detected.")
        return "\n".join(lines)

    digests = sorted(digests, key=lambda d: -d.priority_score)

    # Theme: pick top chain's topic as the theme
    top = digests[0]
    if top.priority_score >= 2:
        theme = f"{top.chain.capitalize()}: {top.dominant_topic or 'Activity detected'}"
        lines.append(f"{theme}")
    else:
        lines.append("Signals collected but nothing above baseline activity.")
    lines.append("")

    high = [d for d in digests if d.priority_score >= 2]
    low = [d for d in digests if 0 < d.priority_score < 2]

    if high:
        lines.append("🔴 High Priority")
        for d in sorted(high, key=lambda x: -x.priority_score):
            emoji = _chain_emoji(d.chain)
            lines.append(f"\n**{emoji} {d.chain.capitalize()} (Score: {d.priority_score})**")
            lines.append(f"{d.summary}")
            for ke in (d.key_events or [])[:3]:
                if isinstance(ke, dict):
                    topic = _fmt_event_link(ke)
                    why = ke.get("why_it_matters", "")
                    lines.append(f"• {topic}")
                    if why:
                        lines.append(f"  → {why}")

    if low:
        lines.append("\n🟡 Other Chains")
        for d in sorted(low, key=lambda x: -x.priority_score):
            emoji = _chain_emoji(d.chain)
            ke = (d.key_events or [])[0] if d.key_events else None
            if isinstance(ke, dict):
                topic = _fmt_event_link(ke)
                lines.append(f"• {emoji} {d.chain.capitalize()}: {topic} (score {d.priority_score})")
            else:
                lines.append(f"• {emoji} {d.chain.capitalize()}: {d.dominant_topic or 'Activity'} (score {d.priority_score})")

    if not high and not low:
        lines.append("— Quiet day across monitored chains.")

    lines.append("")
    lines.append("👀 Watch")
    lines.append("Monitor for follow-up signals tomorrow.")
    return "\n".join(lines)


def _format_health_footer(health: dict, detail: dict | None = None) -> str:
    """Format source health as a brief Telegram footer."""
    if not health:
        return ""
    lines = ["", "⚠️ Source health"]
    healthy = sum(
        1 for h in health.values()
        if str(h.get("status", "")).lower() in ("healthy", "ok", "up")
    )
    degraded = sum(
        1 for h in health.values()
        if str(h.get("status", "")).lower() == "degraded"
    )
    down = sum(
        1 for h in health.values()
        if str(h.get("status", "")).lower() == "down"
    )
    total = len(health)
    lines.append(f"  Collectors: {healthy}/{total} healthy | {degraded} degraded | {down} down")

    if detail:
        feed_issues = [
            name for name, h in detail.items()
            if str(h.get("status", "")).lower() not in ("healthy", "ok", "up")
        ]
        if feed_issues:
            lines.append(f"  Feeds with issues ({len(feed_issues)}): {', '.join(feed_issues[:5])}")
            if len(feed_issues) > 5:
                lines.append(f"  ... and {len(feed_issues) - 5} more")

    return "\n".join(lines)


async def synthesize_digest(
    digests: list[ChainDigest],
    source_health: Optional[dict] = None,
    source_health_detail: Optional[dict] = None,
    client=None,  # ignored — agent-native
    date_str: Optional[str] = None,
) -> str:
    """Synthesize chain digests into final Telegram digest.

    v2.0: Fully agent-native — deterministic formatting, no LLM.
    """
    if not digests:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        return (
            f"📊 Chain Monitor — {now}\n\n"
            "Quiet day across monitored chains. No significant events detected."
        )

    date_str = date_str or datetime.now(timezone.utc).strftime("%b %d, %Y")
    raw_output = _build_digest(digests, date_str)

    # Append health footer
    if source_health:
        raw_output += _format_health_footer(source_health, source_health_detail)

    return raw_output
