"""LLM-powered digest generator — produces narrative daily digests via LLM synthesis.

Replaces / augments the template-based formatter with prose summaries that
explain themes, draw connections, and surface actionable insights.
"""

import logging
from typing import Optional

from processors.llm_client import LLMClient, LLMError
from processors.signal import Signal
from config.loader import get_env

logger = logging.getLogger(__name__)


def _build_digest_prompt(
    date_str: str,
    signals: list[Signal],
    health: dict,
    source_health_detail: dict,
) -> str:
    """Build the structured prompt for daily digest synthesis."""

    # Filter and rank signals
    non_noise = [s for s in signals if s.category not in ("PRICE_NOISE", "NOISE")]
    critical = sorted([s for s in non_noise if s.priority_score >= 8], key=lambda x: -x.priority_score)
    high = sorted([s for s in non_noise if 5 <= s.priority_score < 8], key=lambda x: -x.priority_score)
    medium = sorted([s for s in non_noise if 3 <= s.priority_score < 5], key=lambda x: -x.priority_score)

    # Build signal summary list
    signal_lines = []
    for s in critical[:8]:
        line = _format_signal_for_llm(s, "CRITICAL")
        signal_lines.append(line)
    for s in high[:6]:
        line = _format_signal_for_llm(s, "HIGH")
        signal_lines.append(line)
    for s in medium[:4]:
        line = _format_signal_for_llm(s, "MEDIUM")
        signal_lines.append(line)

    signals_block = "\n".join(signal_lines) if signal_lines else "  No notable signals today."

    # Build health block
    total_sources = len(health) if health else 0
    healthy = sum(1 for h in health.values() if h.get("status", "").lower() in ("healthy", "ok", "up")) if health else 0
    degraded = sum(1 for h in health.values() if h.get("status", "").lower() == "degraded") if health else 0
    down = sum(1 for h in health.values() if h.get("status", "").lower() == "down") if health else 0
    health_block = (
        f"Collectors: {healthy}/{total_sources} healthy, "
        f"{degraded} degraded, {down} down"
    )

    prompt = f"""You are a senior crypto market analyst writing a daily intelligence brief.
Your audience is busy traders and analysts who need actionable insights in under 60 seconds.

## Input Data
Date: {date_str}
Total signals: {len(non_noise)}
Critical (≥8): {len(critical)}
High (5-7): {len(high)}
Medium (3-4): {len(medium)}

Signals:
{signals_block}

Source Health: {health_block}

## Output Rules
1. Write in Telegram Markdown. Use **bold** for emphasis, not # headers.
2. Start with a 2-sentence theme summary (e.g. "Today's theme: ...").
3. Group related signals under thematic headings (e.g. "Mainnet Launches", "Regulatory Pressure").
4. For each group, explain WHY it matters — not just WHAT happened.
5. End with a "Watch" section listing 2-3 upcoming items or follow-ups to monitor.
6. Total output: 200-400 words.
7. If no high-priority signals, say so and briefly mention any notable low-priority activity.
8. Do NOT include any raw URLs as text — embed them as [text](url) Markdown links.
   NEVER wrap URLs in double brackets like [text]([link](url)). Use only ONE layer of brackets.
9. Cover ALL signal categories present — not just regulatory. Include tech events, partnerships, and dev activity if they appear in the input.
10. Never use HTML tags. Never use all-caps headings.
11. Do not invent events. Only summarize the provided signals.
12. Do not mention health statistics in the digest body.

## Output Format (Telegram Markdown, no code fences)
📊 Chain Monitor — {date_str}

🧠 Today's theme
[2-sentence summary]

[Thematic group 1]
[2-3 signals with why they matter]

[Thematic group 2]
...

👀 Watch
[2-3 follow-ups to monitor]
"""
    return prompt


def _format_signal_for_llm(signal: Signal, tier: str) -> str:
    """Format a signal for inclusion in the LLM digest prompt."""
    chain = signal.chain.capitalize()
    cat = signal.category.lower().replace("_", " ")
    desc = signal.description[:150]
    ctx = signal.trader_context[:120] if signal.trader_context else ""
    url = _extract_url(signal)
    sources = ", ".join(set(a["source"] for a in signal.activity))
    lines = [
        f"- [{tier}] {chain} [{cat}] (score {signal.priority_score}): {desc}",
        f"  Sources: {sources}",
    ]
    if ctx:
        lines.append(f"  Context: {ctx}")
    if url:
        lines.append(f"  URL: {url}")
    return "\n".join(lines)


def _extract_url(signal: Signal) -> Optional[str]:
    """Extract URL from a signal for LLM digest linking."""
    if not signal.activity:
        return None
    evidence = signal.activity[0].get("evidence", {})
    if isinstance(evidence, dict):
        for key in ("html_url", "pr_url", "link", "feed_url", "url"):
            url = evidence.get(key)
            if url and isinstance(url, str) and url.startswith("http"):
                return url
        # Twitter URL from evidence
        if "evidence" in signal.activity[0] and isinstance(signal.activity[0]["evidence"], dict):
            ev = signal.activity[0]["evidence"]
            for key in ("html_url", "pr_url", "link", "feed_url", "url"):
                url = ev.get(key)
                if url and isinstance(url, str) and url.startswith("http"):
                    return url
    return None


def _sanitize_digest(text: str) -> str:
    """Sanitize LLM output for Telegram Markdown compatibility.

    - Strip unsupported HTML tags
    - Ensure no double blank lines
    - Ensure no bare URLs (wrap in markdown links if possible)
    - Strip HTML entities
    """
    import html
    import re

    # 1. HTML-entity decode
    text = html.unescape(text)

    # 2. Strip HTML tags
    text = re.sub(r"<[^>]+?>", "", text)

    # 3. Collapse triple+ newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Fix double-wrapped markdown links [text]([link](url)) → [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(\[link\]\((https?://[^\s)]+)\)\)",
        r"[\1](\2)",
        text,
    )
    # 4b. If any bare URLs remain (LLM forgot to wrap), leave them alone —
    # Telegram handles them fine. Do NOT auto-wrap as [link] to avoid
    # conflict with existing markdown links.

    # 5. Strip ``` fences
    text = re.sub(r"^```\w*\n", "", text)
    text = re.sub(r"\n```\w*$", "", text)
    text = re.sub(r"```", "", text)

    # 6. Inject chain emojis for faster visual scanning
    text = _add_chain_emojis(text)

    return text.strip()


def _add_chain_emojis(text: str) -> str:
    """Prepend chain-specific emojis to chain names where missing.

    Matches common chain names at start of lines, after bullets, or after bold.
    """
    # Chain -> emoji mapping (same as daily_digest.py)
    EMOJIS = {
        "bitcoin": "🟠", "ethereum": "⬡", "solana": "⚡",
        "base": "🔵", "arbitrum": "🔷", "optimism": "🔴",
        "bnb chain": "🟡", "bsc": "🟡", "mantle": "🟢",
        "hyperliquid": "🟣", "ink": "🩵", "xlayer": "❌",
        "monad": "🔘", "zircuit": "⚪", "aptos": "🔺",
        "sui": "🔹", "starknet": "🦁", "movement": "🏃",
        "sei": "🌊", "berachain": "🐻", "corn": "🌽",
    }
    import re

    for chain, emoji in EMOJIS.items():
        # Case-insensitive match for chain name at line start, after bullet, or after **
        # e.g. "Bitcoin:", "• Bitcoin", "**Bitcoin**", "- BSC"
        pattern = re.compile(
            rf"(?P<prefix>^|\n)(?P<bullet>[\s]*•\s+|\s*-\s+|\*\*|__)?"
            rf"(?P<chain>\b{re.escape(chain)}\b)"
            rf"(?P<suffix>\s*:|\s+-|\*\*|__)?",
            re.IGNORECASE,
        )

        def repl(m: re.Match) -> str:
            # If emoji already present right before the chain, skip
            start = m.start()
            if start > 0 and text[start - 1 : start] == emoji:
                return m.group(0)
            bullet = m.group("bullet") or ""
            suffix = m.group("suffix") or ""
            return f"{m.group('prefix')}{bullet}{emoji} {m.group('chain').capitalize()}{suffix}"

        text = pattern.sub(repl, text)

    return text


class LLMDigestGenerator:
    """Generate daily digest via LLM narrative synthesis."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient.from_env()
        self.model = get_env("LLM_DIGEST_MODEL", "glm-5.1:cloud")
        self.temperature = float(get_env("LLM_DIGEST_TEMPERATURE", "0.4"))
        self.max_tokens = int(get_env("LLM_DIGEST_MAX_TOKENS", "1500"))
        self.timeout = float(get_env("LLM_DIGEST_TIMEOUT", "45"))

    def generate(
        self,
        signals: list[Signal],
        source_health: dict = None,
        source_health_detail: dict = None,
        date_str: Optional[str] = None,
    ) -> Optional[str]:
        """Generate LLM-powered digest.

        Returns digest Markdown string, or None on failure (caller falls back to template).
        """
        if not signals:
            return None

        date_str = date_str or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%b %d, %Y")

        prompt = _build_digest_prompt(
            date_str=date_str,
            signals=signals,
            health=source_health or {},
            source_health_detail=source_health_detail or {},
        )

        try:
            raw = self.client.generate(
                prompt=prompt,
                model=self.model,
                # temperature and timeout are set on client init, but allow override here
            )
        except LLMError as e:
            logger.warning(f"[digest-llm] Generation failed: {e}")
            return None

        sanitized = _sanitize_digest(raw)
        if not sanitized:
            logger.warning("[digest-llm] Sanitized digest is empty")
            return None

        # Ensure header is present
        if f"📊 Chain Monitor — {date_str}" not in sanitized:
            sanitized = f"📊 Chain Monitor — {date_str}\n\n" + sanitized

        return sanitized
