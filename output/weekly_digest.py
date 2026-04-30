"""Weekly digest formatter — builds a rich agent prompt for weekly thematic synthesis.

No external LLM calls. The running agent reads the prompt and writes prose.
Reads 7 days of persisted daily digests and builds a thematic synthesis prompt.
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"
AGENT_INPUT_DIR = REPO_ROOT / "storage" / "agent_input"


_WEEKLY_SYSTEM_INSTRUCTIONS = """## Instructions
You are a senior crypto market strategist writing a weekly intelligence brief.

Synthesize the daily digests into a single weekly report.

Format:
📈 Weekly Intelligence Brief — {week_range}

🧠 Theme of the Week
[2-sentence summary of the single most important cross-chain theme]

[**Emoji** **Thematic Section Name**]
💎 Chains: Chain1, Chain2, Chain3

- Chain1 [action](url) specific detail with numbers. Why it matters.

- Chain2 [action](url) specific detail with numbers. Why it matters.

[Continue up to 10 thematic sections. Group by theme, NOT by chain.]

Rules:
- Use Telegram Markdown: **bold** for emphasis. No # headers. No HTML tags.
- Never print raw URLs — use [title](url) markdown links.
- Group insights into **thematic sections**, NOT per-chain sections.
- Each section heading MUST start with a single relevant emoji and a space.
- NEVER force a low-relevance item into a section where it does not belong.
- If an item doesn't strongly match any section, give it its own section or omit it.
- Within each section, mention specific chains, numbers, and evidence.
- Total length: 600-1200 words.
- NO "👀 Watch" section at the end.
- ABSOLUTE RULE: If a URL is NOT explicitly present in the input, write WITHOUT any markdown link.
"""


def _load_last_7_days() -> list[str]:
    """Read the 7 most recent daily digest files."""
    if not DAILY_DIGEST_DIR.exists():
        return []

    files = sorted(
        list(DAILY_DIGEST_DIR.glob("daily_digest_*.txt"))
        + list(DAILY_DIGEST_DIR.glob("v2_digest_*.txt"))
        + list(DAILY_DIGEST_DIR.glob("standalone_summary_*.json")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    last_7 = files[:7]
    contents = []
    for p in last_7:
        try:
            if p.suffix == ".json":
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    text = (
                        d.get("final_digest")
                        or d.get("digest")
                        or d.get("generated_digest", "")
                    )
                except json.JSONDecodeError:
                    text = p.read_text(encoding="utf-8")
            else:
                text = p.read_text(encoding="utf-8")

            date_match = re.search(
                r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", p.name
            )
            if date_match:
                y, m, d, H, M, S = date_match.groups()
                header = f"--- Daily Digest: {y}-{m}-{d} ---"
            else:
                header = f"--- {p.name} ---"
            if text.strip():
                contents.append(f"{header}\n\n{text}\n")
        except Exception as e:
            logger.warning(f"Failed to read {p}: {e}")

    return contents


def _format_daily_digests(contents: list[str]) -> str:
    """Join daily digests for the prompt. Truncate if too long."""
    full_text = "\n".join(contents)
    max_chars = 200_000
    if len(full_text) > max_chars:
        logger.info(f"Truncating daily digests from {len(full_text)} to {max_chars} chars")
        full_text = full_text[:max_chars] + "\n\n[... truncated for length ...]"
    return full_text


def _save_agent_prompt(prompt: str, label: str) -> Path:
    AGENT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = AGENT_INPUT_DIR / f"{label}_prompt_{ts}.md"
    path.write_text(prompt, encoding="utf-8")
    logger.info(f"[agent] Prompt saved: {path}")
    return path


def _build_weekly_prompt(digest_text: str, week_range: str) -> str:
    """Construct the full agent prompt for weekly digest synthesis."""
    return f"""# Chain Monitor — Weekly Digest Agent Prompt

## Week Range: {week_range}

## Daily Digests from Past 7 Days

{digest_text}

{_WEEKLY_SYSTEM_INSTRUCTIONS.format(week_range=week_range)}
"""


async def synthesize_weekly_digest(
    client=None,  # unused — kept for API compat
    daily_digests: Optional[list[str]] = None,
) -> str:
    """Generate the weekly agent prompt from the last 7 daily digests."""
    contents = daily_digests or _load_last_7_days()
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")
    week_range = f"{week_start} – {week_end}"

    if not contents:
        return (
            f"📈 Weekly Intelligence Brief — {week_range}\n\n"
            "No daily digests found for the past 7 days. Run the pipeline first."
        )

    digest_text = _format_daily_digests(contents)
    prompt = _build_weekly_prompt(digest_text, week_range)
    path = _save_agent_prompt(prompt, "weekly")

    return (
        f"🤖 Agent synthesis required\n\n"
        f"A weekly synthesis prompt ({len(contents)} daily digests) "
        f"has been saved to:\n{path}\n\n"
        f"Read the prompt and produce the weekly digest."
    )


class WeeklyDigestFormatter:
    """Legacy compat wrapper. Delegates to prompt builder."""

    def format(
        self,
        signals: list,
        narrative_tracker=None,
        source_health: dict = None,
        client=None,
    ) -> str:
        """Generate weekly digest prompt from signals and narrative data."""
        import asyncio

        try:
            return asyncio.run(synthesize_weekly_digest(client=client))
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=7)).strftime("%b %d")
            week_end = now.strftime("%b %d, %Y")
            return (
                f"📈 Weekly Intelligence Brief — {week_start} – {week_end}\n\n"
                "Weekly synthesis unavailable."
            )


def _make_week_range() -> str:
    """Build a human-readable week range string."""
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    return f"{week_start} – {now.strftime('%b %d, %Y')}"
