"""Weekly digest formatter — agent-native.

The running agent reads 7 days of daily digests and produces the weekly summary.
"""

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).parent.parent


def _load_last_7_days() -> list[str]:
    digest_dir = REPO_ROOT / "storage" / "twitter" / "summaries"
    if not digest_dir.exists():
        return []
    files = sorted(digest_dir.glob("v2_digest_*.txt") , key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.read_text(encoding="utf-8") for p in files[:7]]


async def synthesize_weekly_digest(client=None, daily_digests: Optional[list[str]] = None) -> str:
    contents = daily_digests or _load_last_7_days()
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")

    if not contents:
        return (
            f"📈 Weekly Intelligence Brief — {week_start} – {week_end}\n\n"
            "No daily digests found. Run the pipeline + agent first."
        )

    return (
        f"📈 Weekly Intelligence Brief — {week_start} – {week_end}\n\n"
        f"{len(contents)} daily digest(s) loaded.\n\n"
        "The running agent is responsible for synthesizing the weekly report."
    )


class WeeklyDigestFormatter:
    def format(self, signals: list, narrative_tracker=None, source_health: dict = None, client=None) -> str:
        import asyncio
        try:
            return asyncio.run(synthesize_weekly_digest(client=client))
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            return "📈 Weekly Intelligence Brief — Agent synthesis deferred."
