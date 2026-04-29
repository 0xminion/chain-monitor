"""Event-driven weekly digest — reads 7 days of daily digests and synthesizes.

v1.0: Replaces chain-driven format with LLM-generated thematic sections.
Sections are determined by the LLM (up to 10), not hardcoded by chain.
Example sections: Liquidity & Infrastructure, Political & Ecosystem Visibility,
Regulatory & Macro Sentiment, etc.
"""

import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from processors.llm_client import LLMClient, LLMError
from config.loader import get_env

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"

_WEEKLY_SYSTEM_PROMPT = """You are a senior crypto market strategist writing a weekly intelligence brief.
Your audience is traders, analysts, and builders who need to understand cross-chain themes in under 90 seconds.

Rules:
- Use Telegram Markdown: **bold** for emphasis. No # headers. No HTML tags.
- Never print raw URLs as plain text — use [title](url) markdown links.
- Group insights into **thematic sections**, NOT per-chain sections.
- Each section heading MUST start with a single relevant emoji and a space before the theme name. Example: "**🏦 Institutional Payment Rails**" or "**🔒 Privacy Infrastructure**". Never use generic numbering like "Section 1:".
- Section names should reflect market themes (e.g., "Liquidity & Infrastructure", "Political & Ecosystem Visibility", "Regulatory & Macro Sentiment", "ZK & Scaling Developments", "DeFi & Institutional Adoption").
- The LLM decides the section names AND the emoji (up to 10 sections). Be creative but precise.
- NEVER force a low-relevance item into a section where it does not belong just to fill space.
- If an item does not strongly match the core theme of any existing section, give it its own separate section with an accurate emoji, or omit it entirely. Do NOT aggregate loosely-related items.
- Within each section, mention specific chains, numbers, and evidence.
- Total length: 600-1200 words.
- Begin with a 2-sentence "🧠 Theme of the Week" summary.
- NO "👀 Watch" section at the end.
- ABSOLUTE RULE: If a URL is NOT explicitly present in the input daily digests, you MUST write the sentence WITHOUT any markdown link. Never fabricate URLs.
"""

_WEEKLY_PROMPT = """## Daily Digests from Past 7 Days

{daily_digests_text}

## Instructions
Synthesize the above daily digests into a single weekly intelligence brief.

Format:
📈 Weekly Intelligence Brief — {week_range}

🧠 Theme of the Week
[2-sentence summary of the single most important cross-chain theme]

**[Emoji] [Thematic Name]**
🔖 Chains: Chain1, Chain2, Chain3

- Chain1 [action](https://...) specific detail with numbers. Why it matters.

- Chain2 [action](https://...) specific detail with numbers. Why it matters.

[Continue for each chain that belongs to this theme, with one bullet per chain and a blank line between bullets.]

**[Emoji] [Thematic Name]**
[Same format: chain list on one line, then bullet-per-chain with blank lines between.]

[Continue up to 10 sections as appropriate. If fewer themes exist, use fewer sections.]

Rules:
- MAX 10 thematic sections.
- DO NOT create per-chain sections.
- Each section heading MUST start with a single relevant emoji followed by a space and the thematic name. Example: "**🏦 Institutional Payment Rails**" or "**🔒 Privacy Infrastructure**". Never use plain "Section 1:" labels.
- NEVER force a low-relevance item into a section where it does not belong just to fill space.
- If an item does not strongly match the core theme of any existing section, give it its own separate section with an accurate emoji, or omit it entirely. Do NOT aggregate loosely-related items.
- After each section heading, list ALL chains that appear in that section on one line: "Chains: Chain1, Chain2, Chain3".
- Each chain in a section gets its OWN bullet point starting with "- ChainName ...".
- Put a BLANK LINE between each bullet point.
- Every insight MUST trace back to a source with markdown links where the FIRST content-bearing word of the sentence is the link. Example: "Visa [activated](https://...) Polygon rails..."
- Never invent events not in the input.
- NO "👀 Watch" section at the end.
"""


def _load_last_7_days() -> list[str]:
    """Read the 7 most recent daily digest files."""
    if not DAILY_DIGEST_DIR.exists():
        return []

    # Accept both v2_digest_*.txt and daily_digest_*.txt
    files = sorted(
        list(DAILY_DIGEST_DIR.glob("v2_digest_*.txt"))
        + list(DAILY_DIGEST_DIR.glob("daily_digest_*.txt")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    last_7 = files[:7]
    contents = []
    for p in last_7:
        try:
            text = p.read_text(encoding="utf-8")
            date_match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", p.name)
            if date_match:
                y, m, d, H, M, S = date_match.groups()
                header = f"--- Daily Digest: {y}-{m}-{d} ---"
            else:
                header = f"--- {p.name} ---"
            contents.append(f"{header}\n\n{text}\n")
        except Exception as e:
            logger.warning(f"Failed to read {p}: {e}")

    return contents


def _format_daily_digests(contents: list[str]) -> str:
    """Join daily digests for the LLM prompt. Truncate if too long."""
    full_text = "\n".join(contents)
    # Hard cap at ~200k chars to stay within context window
    max_chars = 200_000
    if len(full_text) > max_chars:
        logger.info(f"Truncating daily digests from {len(full_text)} to {max_chars} chars")
        full_text = full_text[:max_chars] + "\n\n[... truncated for length ...]"
    return full_text


async def synthesize_weekly_digest(
    client: Optional[LLMClient] = None,
    daily_digests: Optional[list[str]] = None,
) -> str:
    """Generate the weekly event-driven digest from the last 7 daily digests.

    Args:
        client: Optional LLMClient (creates from env if None).
        daily_digests: Optional pre-loaded list of daily digest strings.

    Returns:
        Markdown string of the weekly digest.
    """
    contents = daily_digests or _load_last_7_days()
    if not contents:
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=7)).strftime("%b %d")
        return (
            f"📈 Weekly Intelligence Brief — {week_start} – {now.strftime('%b %d, %Y')}\n\n"
            "No daily digests found for the past 7 days. Run the pipeline first."
        )

    digest_text = _format_daily_digests(contents)

    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")
    week_range = f"{week_start} – {week_end}"

    prompt = _WEEKLY_PROMPT.format(
        daily_digests_text=digest_text,
        week_range=week_range,
    )

    llm_digest_enabled = get_env("WEEKLY_DIGEST_LLM_ENABLED", "true").lower() == "true"
    if not llm_digest_enabled:
        logger.info("[weekly-digest] LLM disabled, returning fallback")
        return _fallback_weekly(digest_text, week_range)

    client = client or LLMClient.from_env()
    try:
        raw = await asyncio.to_thread(
            lambda: client.generate(prompt, system_prompt=_WEEKLY_SYSTEM_PROMPT, num_predict=4096)
        )
    except LLMError as exc:
        logger.error(f"Weekly digest LLM failed: {exc}, using fallback")
        return _fallback_weekly(digest_text, week_range)
    except Exception as exc:
        logger.error(f"Unexpected error in weekly digest: {exc}")
        return _fallback_weekly(digest_text, week_range)

    # Sanitize
    raw = raw.strip()
    # De-duplicate emoji header if LLM already included it
    lines = raw.splitlines()
    if lines and lines[0].startswith("📈") and "Weekly Intelligence Brief" in lines[0]:
        # LLM included the header — keep it, just ensure consistent format
        pass
    elif "📈" not in raw.split("\n", 1)[0]:
        raw = f"📈 Weekly Intelligence Brief — {week_range}\n\n{raw}"

    # Inject source health footer
    raw += _format_health_footer()

    return raw


def _fallback_weekly(digest_text: str, week_range: str) -> str:
    """Pure-Python fallback when LLM is unavailable."""
    lines = [
        f"📈 Weekly Intelligence Brief — {week_range}",
        "",
        "🧠 Theme of the Week",
        "LLM synthesis unavailable — raw signals below.",
        "",
        "📊 Raw Signals (7-day aggregate)",
        "Daily digest data present but synthesis engine offline.",
        "",
    ]
    return "\n".join(lines)


def _format_health_footer() -> str:
    """Minimal health footer for weekly digest."""
    return "\n\n⚠️ Source health\n  Weekly digest: LLM-driven synthesis complete.\n"


async def main():
    """CLI entry point for testing the weekly digest generation."""
    logging.basicConfig(level=logging.INFO)
    digest = await synthesize_weekly_digest()
    print(digest)

    out_path = REPO_ROOT / "storage" / "twitter" / "summaries" / f"weekly_digest_{datetime.now(timezone.utc).strftime('%Y%m%d')}.txt"
    out_path.write_text(digest, encoding="utf-8")
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
