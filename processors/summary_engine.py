"""Summary engine — builds a rich agent prompt for daily digest synthesis.

No external LLM calls. The running agent reads the prompt and writes prose.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from processors.pipeline_types import ChainDigest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
AGENT_INPUT_DIR = REPO_ROOT / "storage" / "agent_input"


def _format_chain_for_prompt(digest: ChainDigest, idx: int) -> str:
    """Format a ChainDigest as rich markdown for the agent prompt."""
    lines = [
        f"\n### {idx + 1}. {digest.chain.upper()} "
        f"(Score: {digest.priority_score}, Sources: {digest.sources_seen}, Events: {digest.event_count})\n",
        f"Dominant topic: {digest.dominant_topic}\n",
    ]
    for ke in (digest.key_events or [])[:5]:
        if not isinstance(ke, dict):
            continue
        topic = ke.get("topic", "Event")
        cat = ke.get("category", "UNKNOWN")
        p = ke.get("priority", 0)
        detail = ke.get("detail", "")
        why = ke.get("why_it_matters", "")
        url = ke.get("url", "")
        sources = ", ".join(ke.get("sources", ["unknown"]))
        url_line = f" | URL: {url}" if url else ""
        lines.append(f"  - [{cat}] {topic} (P{p}, src: {sources}){url_line}")
        if detail:
            lines.append(f"    Detail: {detail}")
        if why:
            lines.append(f"    Why it matters: {why}")
    return "\n".join(lines)


def _build_daily_prompt(
    digests: list[ChainDigest],
    source_health: Optional[dict] = None,
    source_health_detail: Optional[dict] = None,
    date_str: Optional[str] = None,
) -> str:
    """Construct the full agent prompt for daily digest synthesis."""
    date_str = date_str or datetime.now(timezone.utc).strftime("%b %d, %Y")
    digests = sorted(digests, key=lambda d: -d.priority_score)
    active = [d for d in digests if d.priority_score > 0]

    # Health block
    health_lines = []
    if source_health:
        healthy = sum(
            1
            for h in source_health.values()
            if str(h.get("status", "")).lower() in ("healthy", "ok", "up")
        )
        total = len(source_health)
        degraded = sum(
            1
            for h in source_health.values()
            if str(h.get("status", "")).lower() == "degraded"
        )
        down = sum(
            1
            for h in source_health.values()
            if str(h.get("status", "")).lower() == "down"
        )
        health_lines.append(
            f"Collectors: {healthy}/{total} healthy | {degraded} degraded | {down} down"
        )
        if source_health_detail:
            feed_issues = [
                name
                for name, h in source_health_detail.items()
                if str(h.get("status", "")).lower() not in ("healthy", "ok", "up")
            ]
            if feed_issues:
                health_lines.append(
                    f"Feed issues ({len(feed_issues)}): {', '.join(feed_issues[:5])}"
                )

    # Chain block
    chain_parts = []
    for i, d in enumerate(active):
        chain_parts.append(_format_chain_for_prompt(d, i))
    chain_block = "\n".join(chain_parts)
    health_block = "\n".join(health_lines) if health_lines else "All collectors operational."

    prompt = f"""# Chain Monitor — Daily Digest Agent Prompt

## Date: {date_str}

## Source Health
{health_block}

## Active Chains ({len(active)})
{chain_block}

## Instructions
You are a senior crypto market analyst. Write the daily Chain Monitor digest for Telegram.

Output format:
📊 Chain Monitor — {date_str}

🧠 Today's theme
[1-2 sentences of the single most important cross-chain theme]

[For each chain with score ≥ 2, write a section:]

**ChainName (Score: X)**
[2-3 sentences synthesizing what's happening and why it matters. Be specific — mention partner names, funding amounts, version numbers when available.]
[If a URL is provided above, embed it as a markdown link using the FIRST content-bearing word: "Polygon [activated](url) Visa rails..." NOT "[source](url)".]
[If no URL is provided, write without any link.]

[For chains with score < 2, omit or use a single bullet.]

Rules:
- Use Telegram Markdown: **bold** for emphasis. No # headers. No HTML tags.
- Never use all-caps headings.
- Past tense for events ("announced", "secured", "launched").
- Do NOT invent events. Only use the data provided above.
- Do NOT fabricate URLs. Only use URLs explicitly listed above.
- Total length: 300-600 words.
"""
    return prompt


def save_agent_prompt(prompt: str, label: str) -> Path:
    """Save an agent prompt to disk for the running agent to read."""
    AGENT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = AGENT_INPUT_DIR / f"{label}_prompt_{ts}.md"
    path.write_text(prompt, encoding="utf-8")
    logger.info(f"[agent] Prompt saved: {path}")
    return path


async def synthesize_digest(
    digests: list[ChainDigest],
    source_health: Optional[dict] = None,
    source_health_detail: Optional[dict] = None,
    client=None,  # unused — kept for API compat
    date_str: Optional[str] = None,
) -> str:
    """Build agent prompt for daily digest synthesis.

    Returns the prompt string. The running agent should read this prompt
    and produce the final digest text.
    """
    if not digests:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")
        return (
            f"📊 Chain Monitor — {now}\n\n"
            "Quiet day across monitored chains. No significant events detected."
        )

    prompt = _build_daily_prompt(digests, source_health, source_health_detail, date_str)
    path = save_agent_prompt(prompt, "daily")

    return (
        f"🤖 Agent synthesis required\n\n"
        f"A rich prompt with {len([d for d in digests if d.priority_score > 0])} active chains "
        f"has been saved to:\n{path}\n\n"
        f"Read the prompt and produce the digest."
    )
