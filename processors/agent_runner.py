"""Agent digest runner — pure agent-native pipeline.

No LLM. No fallback. No external model calls. The running agent
reads the saved prompt and writes prose directly into the active chat.
This module persists prompts to disk so the agent can pick them up.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from processors.summary_engine import save_agent_prompt
from processors.pipeline_types import ChainDigest
from processors.pipeline_utils import safe_text_write

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "daily_digests"


class AgentDigestRunner:
    """Agent-native digest runner.

    1. Builds the agent prompt from chain digests.
    2. Persists the prompt for the running agent.
    3. Returns the prompt text (the agent synthesizes prose in-chat).
    """

    async def synthesize(
        self,
        digests: list[ChainDigest],
        source_health: Optional[dict] = None,
        source_health_detail: Optional[dict] = None,
        date_str: Optional[str] = None,
        prompt_text: Optional[str] = None,
    ) -> str:
        """Build and save the agent prompt. Return it for display/logging."""
        from processors.summary_engine import _build_daily_prompt

        if prompt_text is None:
            if not digests:
                now = datetime.now(timezone.utc).strftime("%b %d, %Y")
                return (
                    f"📊 Chain Monitor — {now}\n\n"
                    "Quiet day across monitored chains. No significant events detected."
                )
            prompt_text = _build_daily_prompt(digests, source_health, source_health_detail, date_str)

        # Persist prompt for the running agent
        save_agent_prompt(prompt_text, "daily")
        logger.info(f"[agent] Prompt saved ({len(prompt_text)} chars) — waiting for agent-native prose synthesis")
        return prompt_text

    async def synthesize_weekly(self) -> str:
        """Build weekly digest from cache; agent will write prose directly."""
        from output.weekly_digest import build_digest
        try:
            weekly_text = build_digest()
            logger.info(f"[agent] Weekly digest built ({len(weekly_text)} chars)")
            return weekly_text
        except Exception as exc:
            logger.error(f"[agent] Weekly digest failed: {type(exc).__name__}: {exc}")
            now = datetime.now(timezone.utc)
            from datetime import timedelta
            ws = (now - timedelta(days=7)).strftime("%b %d")
            we = now.strftime("%b %d, %Y")
            return f"📈 Weekly Intelligence Brief — {ws} – {we}\n\nWeekly synthesis unavailable."
