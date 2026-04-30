"""Summary engine — synthesize chain digests into final Telegram digest.

Uses LLM prose for high-priority chains (≥5) and structured bullets for
low-priority chains (<5) — hybrid approach per user specification.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from processors.pipeline_types import ChainDigest
from processors.llm_client import LLMClient, LLMError
from config.loader import get_env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_DIGEST_SYSTEM_PROMPT = """You are a senior crypto market analyst writing the daily Chain Monitor intelligence brief for delivery via Telegram.

Your audience is busy traders and analysts who need actionable insight in under 60 seconds.
Rules:
- Use Telegram Markdown: **bold** for emphasis. No # headers. No HTML tags.
- Never use all-caps headings.
- Do NOT print raw URLs as plain text.
- URL LINKING RULE: Look at the `key_event.url` field provided in the prompt. If a URL is present, embed the first content-bearing word of the sentence as a markdown link. Example: "Polygon [announced](https://x.com/...) a Visa integration..." — NOT "[source](url)". If NO url is provided in key_event.url, write the sentence WITHOUT any markdown link.
- Be precise. Do not invent events that are not in the input data.
- Do NOT hallucinate URLs. Only use URLs explicitly given in the key_event data. If no URL is given, do not include a link.
- Explain WHY an event matters, not just WHAT happened.
- Group related chains thematically if they share a story (e.g., "ZK Ecosystem Upgrades").
- TENSE RULE: All events happened in the past 24h. Use past tense throughout ("went live", "secured", "announced", "patched").
  Exception: forward-looking "Watch" bullets may use present tense for upcoming items.
- WATCH BULLETS: Maximum 12-15 words each. Tight, specific, no filler.
- CHAIN EMOJIS: Use ⚡ for Solana, 🔵 for Base, ⬡ for Ethereum, 🟠 for Bitcoin, 💧 for Sui, etc.
- For chains with priority >= 2, write a full 2-3 sentence paragraph with embedded links, NOT just a bullet.
- For chains with priority >= 2, you MUST include the URL from at least one key_event as a markdown link in the FIRST content-bearing word of a sentence. Example: "BSC [hosted](url) a Miami event..." NOT "BSC hosted a Miami event [source](url)".
- Every claim should trace back to a source. Only include links when a real URL is present in key_events.
- SCORE ≥2 FORMAT: Each score≥2 chain paragraph MUST contain: (1) a one-sentence summary of the dominant topic, (2) a one-sentence explanation of why it matters to traders, and (3) an embedded markdown link using the first content-bearing word, if a URL is provided.
"""

_DIGEST_PROMPT = """## Date: {date_str}

## Chain-level summaries (priority desc):
{chain_block}

## Instructions
Write the daily Chain Monitor digest.

Output format:
📊 Chain Monitor — {date_str}

🧠 Today's theme
[1-2 sentences of the single most important market theme across all chains]

[Then for each chain with priority >= 2, write a prose paragraph:]

**ChainName (Score: X)**
[2-3 sentences synthesizing what's happening and why it matters. Embed [source](url) links using the FIRST content-bearing word of a sentence.]

[For chains with priority < 2, use bullet format:]
• ChainName: dominant_topic (score: X)

👀 Watch
[2-3 specific follow-ups or upcoming events to monitor]

Total length: 400-800 words.
No code fences. No markdown # headings.
"""


def _format_chain_for_digest(digest: ChainDigest, idx: int) -> str:
    """Format a ChainDigest for inclusion in the LLM prompt.

    v1.2: Includes URLs in key_events AND formats them as markdown link examples
    so the LLM learns by demonstration.
    """
    lines = [
        f"\n### {idx+1}. {digest.chain.upper()} (Priority: {digest.priority_score}, Confidence: {digest.confidence:.0%})\n",
        f"Topic: {digest.dominant_topic or 'No dominant topic'}\n",
        f"Summary: {digest.summary}\n",
    ]
    for ke in (digest.key_events or [])[:5]:
        if isinstance(ke, dict):
            topic = ke.get("topic", "Event")
            cat = ke.get("category", "UNKNOWN")
            p = ke.get("priority", 0)
            c = ke.get("confidence", 0.0)
            detail = ke.get("detail", "")
            why = ke.get("why_it_matters", "")
            url = ke.get("url", "")
            url_line = f" | url: {url}" if url else ""
            # Show markdown link example in prompt to teach by demonstration
            if url:
                words = topic.split()
                if words:
                    link_example = f"  📎 LINK EXAMPLE: [{words[0]}]({url}) {' '.join(words[1:])}"
                else:
                    link_example = f"  📎 LINK EXAMPLE: [{topic}]({url})"
                url_line += f"\n{link_example}"
            lines.append(f"  - [{cat}] {topic} (P{p}, {c:.0%} conf): {detail}{url_line}")
            if why:
                lines.append(f"    → {why}")
    return "".join(lines)


def _extract_url(line: str) -> str:
    """Pull a markdown [text](url) or bare URL out of a line."""
    import re
    m = re.search(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', line)
    if m:
        return m.group(2)
    m2 = re.search(r'(https?://[^\s)\]\n]+)', line)
    if m2:
        return m2.group(1)
    return ""


def _fallback_digest(digests: list[ChainDigest], date_str: str) -> str:
    """Structured fallback when LLM synthesis fails. Pure Python, no LLM."""
    lines = [
        f"📊 Chain Monitor — {date_str}",
        "",
        "🧠 Today's theme",
        "Signals collected but synthesis engine unavailable.",
        "",
    ]

    high = [d for d in digests if d.priority_score >= 2]
    low = [d for d in digests if 0 < d.priority_score < 2]

    if high:
        lines.append("🔴 High Priority")
        for d in sorted(high, key=lambda x: -x.priority_score):
            lines.append(f"\n**{d.chain.upper()} (Score: {d.priority_score})**")
            lines.append(f"{d.summary}")
            for ke in (d.key_events or [])[:3]:
                if isinstance(ke, dict):
                    topic = ke.get("topic", "Event")
                    why = ke.get("why_it_matters", "")
                    url = ke.get("url", "")
                    # Embed the URL in the topic text using first-word markdown link style
                    if url:
                        words = topic.split()
                        if words:
                            linked_topic = f"[{words[0]}]({url}) {' '.join(words[1:])}".strip()
                            lines.append(f"• {linked_topic}")
                        else:
                            lines.append(f"• {topic}")
                    else:
                        lines.append(f"• {topic}")
                    if why:
                        lines.append(f"  → {why}")

    if low:
        lines.append("\n🟡 Other Chains")
        for d in sorted(low, key=lambda x: -x.priority_score):
            url = ""
            if d.key_events and isinstance(d.key_events[0], dict):
                url = d.key_events[0].get("url", "")
                topic = d.key_events[0].get("topic", d.dominant_topic or "Activity")
            else:
                topic = d.dominant_topic or "Activity"
            if url:
                words = topic.split()
                if words:
                    lines.append(f"• {d.chain.upper()}: [{words[0]}]({url}) {' '.join(words[1:])} (score {d.priority_score})")
                else:
                    lines.append(f"• {d.chain.upper()}: {topic} (score {d.priority_score})")
            else:
                lines.append(f"• {d.chain.upper()}: {topic} (score {d.priority_score})")

    if not high and not low:
        lines.append("— Quiet day across monitored chains.")

    lines.extend(["", "👀 Watch", "Monitor for follow-up signals tomorrow."])
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
    client: Optional[LLMClient] = None,
    date_str: Optional[str] = None,
) -> str:
    """Synthesize chain digests into final Telegram digest.

    Uses LLM prose for high-priority chains (≥5), bullet fallback for low-priority.
    Falls back to pure Python formatting if LLM fails.
    """
    if not digests:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        return (
            f"📊 Chain Monitor — {now}\n\n"
            "Quiet day across monitored chains. No significant events detected."
        )

    date_str = date_str or datetime.now(timezone.utc).strftime("%b %d, %Y")

    # Sort by priority desc for consistent prompt ordering
    digests = sorted(digests, key=lambda d: -d.priority_score)
    high_priority = [d for d in digests if d.priority_score >= 2]
    low_priority = [d for d in digests if 0 < d.priority_score < 2]

    # Build chain block for LLM
    chain_block_parts = []
    for i, d in enumerate(high_priority):
        chain_block_parts.append(_format_chain_for_digest(d, i))
    for i, d in enumerate(low_priority):
        chain_block_parts.append(
            f"\n### {len(high_priority)+i+1}. {d.chain.upper()} (Priority: {d.priority_score})\n"
            f"  Bullet: {d.dominant_topic or 'No notable activity'}\n"
        )
    chain_block = "".join(chain_block_parts)

    prompt = _DIGEST_PROMPT.format(
        date_str=date_str,
        chain_block=chain_block,
    )

    llm_digest_enabled = get_env("LLM_DIGEST_ENABLED", "true").lower() == "true"
    raw_output = ""

    if llm_digest_enabled:
        client = client or LLMClient.from_env()
        try:
            raw_output = await asyncio.to_thread(
                client.generate, prompt, system_prompt=_DIGEST_SYSTEM_PROMPT
            )
        except LLMError as exc:
            logger.error(f"Digest synthesis LLM failed: {exc}, using fallback")
            raw_output = ""
        except Exception as exc:
            logger.error(f"Unexpected error in digest synthesis: {exc}")
            raw_output = ""

    if not raw_output:
        raw_output = _fallback_digest(digests, date_str)

    # Sanitize
    raw_output = raw_output.strip()

    # Ensure header if missing
    if "📊 Chain Monitor" not in raw_output:
        raw_output = f"📊 Chain Monitor — {date_str}\n\n{raw_output}"

    # Append health footer
    if source_health:
        raw_output += _format_health_footer(source_health, source_health_detail)

    return raw_output
