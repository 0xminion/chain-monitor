"""Weekly digest formatter — generates the weekly strategic report.

v2.0: Fully agent-native. Reads 7 days of persisted daily digests and produces
a deterministic weekly summary via template-based formatting. No LLM calls, no
external APIs, no tokens required.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"


def _load_last_7_days() -> list[str]:
    """Read the 7 most recent daily digest files."""
    if not DAILY_DIGEST_DIR.exists():
        return []

    files = sorted(
        list(DAILY_DIGEST_DIR.glob("v2_digest_*.txt"))
        + list(DAILY_DIGEST_DIR.glob("daily_digest_*.txt"))
        + list(DAILY_DIGEST_DIR.glob("standalone_summary_*.json")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    last_7 = files[:7]
    contents = []
    import json
    for p in last_7:
        try:
            if p.suffix == ".json":
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    text = d.get("final_digest") or d.get("digest") or d.get("generated_digest", "")
                except json.JSONDecodeError:
                    text = p.read_text(encoding="utf-8")
            else:
                text = p.read_text(encoding="utf-8")

            date_match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", p.name)
            if date_match:
                y, m, day, H, M, S = date_match.groups()
                header = f"--- Daily Digest: {y}-{m}-{day} ---"
            else:
                header = f"--- {p.name} ---"
            if text.strip():
                contents.append(f"{header}\n\n{text}\n")
        except Exception as e:
            logger.warning(f"Failed to read {p}: {e}")

    return contents


def _format_daily_digests(contents: list[str]) -> str:
    """Join daily digests. Truncate if too long."""
    full_text = "\n".join(contents)
    max_chars = 200_000
    if len(full_text) > max_chars:
        logger.info(f"Truncating daily digests from {len(full_text)} to {max_chars} chars")
        full_text = full_text[:max_chars] + "\n\n[... truncated for length ...]"
    return full_text


def _extract_chain_signals(daily_text: str) -> dict[str, list[dict]]:
    """Extract chain signal lines from daily digest text. Agent-native parser."""
    chain_signals: dict[str, list[dict]] = {}
    current_chain = None
    for line in daily_text.splitlines():
        # Detect chain headers like "**SOLANA (Score: 5)**"
        m = re.search(r"^\*\*\s*(?:[\U0001F300-\U0001F9FF]\s*)?(\w+)\s*\(Score:\s*(\d+)\)\*\*", line)
        if m:
            current_chain = m.group(1).lower()
            continue
        # Detect bullet lines like "• something" while in a chain section
        if current_chain and line.startswith("•"):
            chain_signals.setdefault(current_chain, []).append({"text": line.strip(), "url": ""})
            # Try to extract URL
            url_match = re.search(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', line)
            if url_match:
                chain_signals[current_chain][-1]["url"] = url_match.group(2)
    return chain_signals


def _build_weekly_digest(daily_text: str, week_range: str) -> str:
    """Build weekly digest from daily digest text — fully agent-native."""
    lines = [
        f"📈 Weekly Intelligence Brief — {week_range}",
        "",
        "🧠 Theme of the Week",
    ]

    if not daily_text.strip():
        lines.append("No daily digests found for the past 7 days. Run the pipeline first.")
        return "\n".join(lines)

    # Extract all unique chain mentions
    chain_signals = _extract_chain_signals(daily_text)
    if not chain_signals:
        lines.append("Signals collected but no chain-level activity parsed. Monitor next week.")
        return "\n".join(lines)

    # Theme: most mentioned chain
    top_chain = max(chain_signals, key=lambda c: len(chain_signals[c]))
    lines.append(f"Most active chain: {top_chain.capitalize()} with {len(chain_signals[top_chain])} signal(s).")
    lines.append("")

    # Section 1: Top chains by activity
    lines.append("**🔥 Chain Activity Summary**")
    sorted_chains = sorted(chain_signals.items(), key=lambda kv: -len(kv[1]))
    for chain, sigs in sorted_chains[:10]:
        lines.append(f"\n{chain.capitalize()}: {len(sigs)} signal(s)")
        for s in sigs[:3]:
            text = s.get("text", "Activity")
            url = s.get("url", "")
            if url:
                # Rebuild with markdown link on first word
                words = text.lstrip("• ").split()
                if words:
                    linked = f"[{words[0]}]({url}) {' '.join(words[1:])}".strip()
                    lines.append(f"  • {linked}")
                else:
                    lines.append(f"  • {text}")
            else:
                lines.append(f"  • {text}")
    lines.append("")

    # Section 2: Any chain with 4+ signals
    hot_chains = [c for c, s in sorted_chains if len(s) >= 4]
    if hot_chains:
        lines.append("**🔥 Hot Chains This Week**")
        for chain in hot_chains[:5]:
            count = len(chain_signals[chain])
            lines.append(f"• {chain.capitalize()}: {count} signals — sustained activity.")
        lines.append("")

    lines.extend(["👀 Watch", "Monitor for follow-up signals next week."])
    return "\n".join(lines)


async def synthesize_weekly_digest(
    client=None,  # ignored — agent-native
    daily_digests: Optional[list[str]] = None,
) -> str:
    """Generate the weekly event-driven digest from the last 7 daily digests."""
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

    raw_output = _build_weekly_digest(digest_text, week_range)
    raw_output += _format_health_footer()
    return raw_output


def _format_health_footer() -> str:
    return "\n\n⚠️ Source health\n  Weekly digest: agent-native synthesis complete.\n"


# Legacy class kept for backward compat; delegates to new function
class WeeklyDigestFormatter:
    """Formats signals into a weekly strategic report."""

    def format(
        self,
        signals: list,
        narrative_tracker=None,
        source_health: dict = None,
        client=None,
    ) -> str:
        """Generate weekly digest from signals and narrative data."""
        import asyncio
        try:
            return asyncio.run(synthesize_weekly_digest(client=client))
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            return _fallback_weekly("", _make_week_range())


def _fallback_weekly(digest_text: str, week_range: str) -> str:
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


def _make_week_range() -> str:
    """Build a human-readable week range string."""
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    return f"{week_start} – {now.strftime('%b %d, %Y')}"
