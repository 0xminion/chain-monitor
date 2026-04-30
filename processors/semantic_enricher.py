"""Semantic enricher — agent-native.

No LLM calls. No keyword matching. Prepares tweet enrichment tasks for the running agent.

This module is kept for backward compatibility with standalone tweet enrichment workflows.
For the main pipeline, EventCategorizer handles all events (including tweets) in a single
agent checkpoint.
"""

import logging
from pathlib import Path
from typing import Optional

from processors.agent_native import save_agent_task, find_agent_output, load_agent_output
from processors.categorizer import (
    CATEGORY_ORDER,
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_MAP,
    TWITTER_NOISE_PHRASES,
)

logger = logging.getLogger(__name__)


class SemanticEnricher:
    """Agent-native semantic enrichment for tweets.

    Usage (standalone):
        enricher = SemanticEnricher()
        task_path = enricher.prepare_agent_task(tweets)
        # AGENT CHECKPOINT: running agent processes task and saves output
        results = enricher.try_load_results()
        enriched = enricher.apply_enrichment(tweets, results)
    """

    TASK_TYPE = "semantic_enrich"

    def enrich_tweets(self, tweets: list[dict]) -> list[dict]:
        """DEPRECATED — agent-native pipeline does not use automated enrichment.

        Raises RuntimeError with instructions for the agent-native flow.
        """
        raise RuntimeError(
            "SemanticEnricher is agent-native. Automated keyword/LLM enrichment has been removed.\n"
            "Use: prepare_agent_task() → agent processes → try_load_results() → apply_enrichment()\n"
            "For the main pipeline, EventCategorizer handles all events in a single checkpoint."
        )

    def enrich(self, event: dict) -> dict:
        """DEPRECATED — see enrich_tweets()."""
        raise RuntimeError(
            "SemanticEnricher is agent-native. Use prepare_agent_task() + try_load_results()."
        )

    # -- Agent task preparation ------------------------------------------------

    def prepare_agent_task(self, tweets: list[dict]) -> Path:
        """Build and save a tweet enrichment task for the running agent.

        Returns the path to the saved task file.
        """
        task_tweets = []
        for i, t in enumerate(tweets):
            task_tweets.append({
                "id": i,
                "chain": t.get("chain", "unknown"),
                "text": t.get("text", ""),
                "author": t.get("account_handle", ""),
                "role": t.get("account_role", "unknown"),
                "is_retweet": t.get("is_retweet", False),
                "original_author": t.get("original_author", ""),
                "is_quote_tweet": t.get("is_quote_tweet", False),
                "quoted_text": t.get("quoted_text", ""),
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
                "url": t.get("url", ""),
            })

        payload = {
            "instructions": self._build_agent_instructions(),
            "tweets": task_tweets,
            "output_format": self._build_output_format(),
        }
        return save_agent_task(self.TASK_TYPE, payload)

    def try_load_results(self, task_id: Optional[str] = None) -> Optional[list[dict]]:
        """Attempt to load agent enrichment results.

        Returns None if no output is available yet.
        """
        output_path = find_agent_output(self.TASK_TYPE, task_id=task_id)
        if output_path is None:
            return None
        try:
            data = load_agent_output(output_path)
            results = data.get("results", [])
            logger.info(f"[semantic] Loaded {len(results)} agent-enriched tweets from {output_path}")
            return results
        except Exception as exc:
            logger.warning(f"[semantic] Failed to load agent output: {exc}")
            return None

    def apply_enrichment(self, tweets: list[dict], enrichment_results: list[dict]) -> list[dict]:
        """Apply agent enrichment results to raw tweets.

        Returns a new list of tweet dicts with semantic annotations.
        """
        result_map = {r["id"]: r for r in enrichment_results if "id" in r}
        enriched = []

        for i, t in enumerate(tweets):
            t_copy = dict(t)
            if i in result_map:
                r = result_map[i]
                cat = r.get("category", "NEWS")
                sub = r.get("subcategory", "general")
                t_copy["semantic"] = {
                    "category": cat,
                    "subcategory": sub,
                    "confidence": 0.85,
                    "reasoning": r.get("reasoning", ""),
                    "is_noise": r.get("is_noise", False),
                    "primary_mentions": r.get("primary_mentions", []),
                }
            else:
                t_copy["semantic"] = {
                    "category": "NEWS",
                    "subcategory": "general",
                    "confidence": 0.0,
                    "reasoning": "Not enriched by agent",
                    "is_noise": False,
                    "primary_mentions": [],
                }
            enriched.append(t_copy)

        enriched_count = sum(1 for t in enriched if t.get("semantic", {}).get("confidence", 0) > 0)
        logger.info(f"[semantic] Applied agent enrichment to {enriched_count}/{len(tweets)} tweets")
        return enriched

    def get_health(self) -> dict:
        """Return health status for observability."""
        return {
            "available": True,
            "mode": "agent-native",
            "provider": "running-agent",
            "requires_checkpoint": True,
        }

    # -- Instruction builders --------------------------------------------------

    def _build_agent_instructions(self) -> str:
        cat_lines = []
        for cat in CATEGORY_ORDER:
            desc = CATEGORY_DESCRIPTIONS.get(cat, "")
            cat_lines.append(f"  - {cat}: {desc}")

        subcat_lines = []
        for cat, subcats in SUBCATEGORY_MAP.items():
            subcat_lines.append(f"  {cat}:")
            for sub, desc in subcats.items():
                subcat_lines.append(f"    - {sub}: {desc}")

        noise_lines = "\n    ".join(f"- '{phrase}'" for phrase in TWITTER_NOISE_PHRASES[:10])

        return (
            "You are an expert crypto-industry analyst. Classify each tweet into exactly one category and subcategory.\n\n"
            "Categories (ordered by priority):\n"
            f"{chr(10).join(cat_lines)}\n\n"
            "Subcategories:\n"
            f"{chr(10).join(subcat_lines)}\n\n"
            "Rules:\n"
            "1. Categorize by SEMANTIC CONTENT, not keyword presence.\n"
            "2. A retweet of official news inherits the original's category.\n"
            "3. Funding announcements with amounts >= $1M receive FINANCIAL.\n"
            "4. 'Audit complete' without findings → TECH_EVENT. 'Audit finding' → RISK_ALERT.\n"
            "5. Engagement bait, price predictions, memes → NOISE.\n"
            "6. For retweets: categorize based on ORIGINAL content, not reposter commentary.\n"
            "7. For quote tweets: categorize based on new commentary + quoted content combined.\n"
            "8. Short tweets (<30 chars) with only emojis → NOISE unless they contain substantive news.\n\n"
            "Common noise phrases (mark as NOISE if primarily these):\n"
            f"    {noise_lines}\n"
            "    ... and similar low-value phrases.\n"
        )

    def _build_output_format(self) -> str:
        return (
            "Return a JSON array of results, one per tweet, in the SAME ORDER as the input.\n"
            "Each result must be:\n"
            "{\n"
            '  "id": <tweet id from input>,\n'
            '  "category": "<CATEGORY>",\n'
            '  "subcategory": "<subcategory>",\n'
            '  "reasoning": "<1 sentence explaining the classification>",\n'
            '  "is_noise": <true/false>,\n'
            '  "primary_mentions": [<list of chain names mentioned, or []>]\n'
            "}\n\n"
            "CRITICAL: every tweet in the input must have a corresponding result with the correct id.\n"
            "Do not skip tweets. Do not return markdown fences.\n"
        )
