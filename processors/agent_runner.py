"""Agent digest runner — closes the agent-native loop by feeding the saved
prompt to the running agent and returning prose.

If the LLM is unavailable or disabled, returns the prompt as-is (fallback).
"""

import logging
from pathlib import Path
from typing import Optional

from processors.llm_client import LLMClient, LLMError
from processors.summary_engine import save_agent_prompt
from processors.pipeline_types import ChainDigest
from processors.pipeline_utils import safe_text_write
from config.loader import get_env, get_pipeline_value

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "daily_digests"

# System prompt for digest synthesis — tight constraints to avoid hallucination
_DIGEST_SYSTEM_PROMPT = (
    "You are a senior crypto market analyst writing Chain Monitor digests for Telegram. "
    "You write ONLY from the provided data. NEVER invent events, URLs, or dollar amounts. "
    "Follow the output format exactly. Past tense only."
)


class AgentDigestRunner:
    """Runs the agent-native synthesis loop.

    1. Takes a ChainDigest list or existing prompt text.
    2. Builds (or reuses) the agent prompt.
    3. Optionally calls an LLM to turn the prompt into prose.
    4. Returns prose digest, or prompt if LLM is unavailable.
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client
        self._enabled = self._detect_enabled()

    def _detect_enabled(self) -> bool:
        """Check whether LLM synthesis is enabled."""
        # Priority: config, then env, then presence of client
        cfg_enabled = get_pipeline_value("pipeline.llm_digest_enabled", None)
        if cfg_enabled is not None:
            return bool(cfg_enabled)
        env_enabled = get_env("LLM_DIGEST_ENABLED", "false").lower()
        if env_enabled in ("true", "1", "yes", "on"):
            return True
        return self.client is not None

    def _get_client(self) -> Optional[LLMClient]:
        """Return LLM client, creating from env if needed."""
        if self.client is not None:
            return self.client
        try:
            return LLMClient.from_env()
        except Exception as exc:
            logger.info(f"[agent] LLM client unavailable: {exc}")
            return None

    async def synthesize(
        self,
        digests: list[ChainDigest],
        source_health: Optional[dict] = None,
        source_health_detail: Optional[dict] = None,
        date_str: Optional[str] = None,
        prompt_text: Optional[str] = None,
    ) -> str:
        """Synthesize a prose digest from chain digests.

        If LLM is enabled and available, calls the LLM to generate prose.
        Otherwise, returns the prompt text (which IS the digest artifact).
        """
        from processors.summary_engine import _build_daily_prompt

        # Build prompt if not provided
        if prompt_text is None:
            if not digests:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).strftime("%b %d, %Y")
                return (
                    f"📊 Chain Monitor — {now}\n\n"
                    "Quiet day across monitored chains. No significant events detected."
                )
            prompt_text = _build_daily_prompt(digests, source_health, source_health_detail, date_str)

        # Save prompt for manual agent review regardless
        save_agent_prompt(prompt_text, "daily")

        # If LLM disabled, return prompt as-is (agent-native manual mode)
        if not self._enabled:
            logger.info("[agent] LLM synthesis disabled — returning prompt for manual agent review")
            return prompt_text

        client = self._get_client()
        if client is None:
            logger.info("[agent] No LLM client available — returning prompt for manual agent review")
            return prompt_text

        # Call LLM
        try:
            max_tokens = get_pipeline_value("pipeline.llm_digest_max_tokens", 2048)
            temperature = get_pipeline_value("pipeline.llm_digest_temperature", 0.4)
            timeout = get_pipeline_value("pipeline.llm_digest_timeout", 45)

            # Configure client for this call
            client.temperature = float(temperature)
            client.timeout = float(timeout)

            logger.info(f"[agent] Calling LLM ({client.model}) for digest synthesis...")
            prose = client.generate(prompt_text, system_prompt=_DIGEST_SYSTEM_PROMPT, num_predict=max_tokens)

            if prose and len(prose.strip()) > 100:
                logger.info(f"[agent] LLM synthesis complete ({len(prose)} chars)")
                # Persist the prose digest
                DAILY_DIGEST_DIR.mkdir(parents=True, exist_ok=True)
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                prose_path = DAILY_DIGEST_DIR / f"daily_digest_{ts}.md"
                safe_text_write(prose_path, prose)
                logger.info(f"[agent] Prose digest saved: {prose_path}")
                return prose
            else:
                logger.warning(f"[agent] LLM returned too-short prose ({len(prose) if prose else 0} chars) — falling back to prompt")
                return prompt_text
        except LLMError as exc:
            logger.warning(f"[agent] LLM synthesis failed: {exc} — falling back to prompt")
            return prompt_text
        except Exception as exc:
            logger.error(f"[agent] Unexpected error during synthesis: {type(exc).__name__}: {exc}")
            return prompt_text

    async def synthesize_weekly(self) -> str:
        """Generate weekly digest from cache using the weekly builder."""
        from output.weekly_digest import build_digest
        try:
            weekly_text = build_digest()
            logger.info(f"[agent] Weekly digest built ({len(weekly_text)} chars)")
            return weekly_text
        except Exception as exc:
            logger.error(f"[agent] Weekly digest failed: {type(exc).__name__}: {exc}")
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            ws = (now - timedelta(days=7)).strftime("%b %d")
            we = now.strftime("%b %d, %Y")
            return f"📈 Weekly Intelligence Brief — {ws} – {we}\n\nWeekly synthesis unavailable."
