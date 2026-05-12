"""Chain digest summarizer — LLM-driven prose synthesis from signals.

Takes per-chain signal bundles (Twitter + RSS + DeFiLlama + SEC + events)
and produces a concise 2-3 sentence prose summary with markdown source links.

Uses antseed buyer proxy for cheap inference (grok-4.1-fast, no tools).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from processors.signal import Signal

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = (
    "You are a crypto intelligence analyst writing a daily digest. "
    "Below are signals for one blockchain from the past 24 hours, "
    "mixed from Twitter posts, news feeds, SEC filings, and on-chain data.\n\n"
    "Write 2-4 sentences synthesizing the most important developments. "
    "Merge related items into one sentence. Drop low-signal noise "
    "(reposts, emoji-only replies, generic engagement bait). "
    "Embed source URLs as markdown links inline — e.g., "
    '"[Clear Signing is now live](https://blog.ethereum.org/...)" — '
    "so readers can click through. Do NOT list items; write flowing prose. "
    "Do NOT prefix with chain name. Do NOT add commentary or analysis.\n\n"
    "Signals:\n"
)


async def summarize_chain(
    chain: str,
    signals: list[Signal],
    proxy_url: str | None = None,
    model: str = "grok-4.1-fast",
    timeout: float = 30.0,
) -> str:
    """Summarize all signals for one chain into prose.

    Args:
        chain: chain name (e.g. "ethereum", "solana")
        signals: mixed signal sources for this chain
        proxy_url: antseed buyer proxy (defaults to ANTSEED_PROXY_URL or localhost:8080)
        model: LLM model for summarization
        timeout: request timeout

    Returns:
        Prose summary like:
        "Solana activated the [Alpenglow upgrade](https://decrypt.co/...),
        announced a [compute futures market](https://...), and saw Beezie
        expand tokenized collectibles to Solana."
    """
    if not proxy_url:
        proxy_url = os.environ.get("ANTSEED_PROXY_URL", "http://localhost:8080")

    # Build signal text with URLs for the LLM
    signal_descriptions = _build_signal_text(signals)

    if not signal_descriptions.strip():
        return ""

    prompt = SUMMARIZE_PROMPT + signal_descriptions

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.post(
                f"{proxy_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
    except httpx.RequestError as e:
        logger.error(f"[summarizer] {chain}: connection error — {e}")
        return ""

    if resp.status_code != 200:
        logger.error(
            f"[summarizer] {chain}: HTTP {resp.status_code} — {resp.text[:200]}"
        )
        return ""

    try:
        data = resp.json()
    except json.JSONDecodeError:
        logger.error(f"[summarizer] {chain}: invalid JSON response")
        return ""

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    if not content:
        logger.warning(f"[summarizer] {chain}: empty response")
        return ""

    logger.info(f"[summarizer] {chain}: {len(content)} chars")
    return content.strip()


def _build_signal_text(signals: list[Signal]) -> str:
    """Convert signals to a compact text block for the LLM summarizer.

    Each signal gets one line with the description and any available URL.
    """
    lines = []
    for s in signals:
        desc = s.description.strip()
        if not desc:
            continue

        # Truncate very long descriptions
        if len(desc) > 300:
            desc = desc[:297] + "..."

        # Find best URL from evidence
        url = ""
        for act in s.activity:
            ev = act.get("evidence", {})
            if isinstance(ev, dict):
                for key in ("html_url", "url", "link", "feed_url"):
                    u = ev.get(key, "")
                    if u and u.startswith("http"):
                        url = u
                        break
            if url:
                break

        # Also check tweet URLs
        if not url:
            for act in s.activity:
                ev = act.get("evidence", {})
                if isinstance(ev, dict):
                    tweet_id = ev.get("tweet_id", "")
                    handle = ev.get("author", "")
                    if tweet_id and handle:
                        url = f"https://x.com/{handle}/status/{tweet_id}"
                        break

        if url:
            lines.append(f"- [{desc}]({url})")
        else:
            lines.append(f"- {desc}")

    return "\n".join(lines)
