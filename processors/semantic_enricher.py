"""Semantic enricher — LLM-powered semantic categorization for unstructured events.

Handles tweets and event dicts.
Uses keyword fallback when LLM is unavailable.
Caches results per-tweet for 7 days.
Supports batched per-chain enrichment with parallel LLM calls.
"""

import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from processors.categorizer import CATEGORY_KEYWORDS, SUBCATEGORY_MAP
from processors.llm_client import LLMClient, LLMError
from processors.llm_cache import LLMCache
from config.loader import get_env

logger = logging.getLogger(__name__)

# Category list for the prompt (ordered by severity for LLM reasoning)
CATEGORY_ORDER = [
    "RISK_ALERT",
    "REGULATORY",
    "FINANCIAL",
    "PARTNERSHIP",
    "TECH_EVENT",
    "VISIBILITY",
    "NOISE",
    "NEWS",
]


def _build_prompt(
    text: str,
    chain: str,
    author: str,
    role: str,
    is_retweet: bool,
    original_author: str,
    quoted_text: str,
    thread_context: str = "",
) -> str:
    """Build the deterministic semantic categorization prompt."""

    subcat_lines = []
    for cat in CATEGORY_ORDER:
        if cat in SUBCATEGORY_MAP:
            subcats = ", ".join(SUBCATEGORY_MAP[cat].keys())
            subcat_lines.append(f"  - {cat}: {subcats}")

    subcat_block = "\n".join(subcat_lines)
    thread_block = f"\nThread context:\n{thread_context}" if thread_context else ""

    prompt = f"""You are an expert crypto-industry analyst. Given a tweet, classify it into exactly one category and subcategory.

Categories (ordered by priority):
{chr(10).join(f"  - {cat}" for cat in CATEGORY_ORDER)}

Subcategories per category:
{subcat_block}

Rules:
1. Categorize by SEMANTIC CONTENT, not keyword presence.
2. A "wen mainnet" reply to a mainnet announcement is VISIBILITY, not TECH_EVENT.
3. A retweet of official news inherits the original's category.
4. Funding announcements with amounts >= $1M receive FINANCIAL.
5. "Audit complete" without findings → TECH_EVENT. "Audit finding" → RISK_ALERT.
6. Engagement bait, price predictions, memes → NOISE.
7. Only return the specified JSON. No extra text.
8. If chain-agnostic (mentions no specific chain), set primary_mentions to [].

Input:
Chain: {chain}
Author: {author} ({role})
Is retweet: {is_retweet}
Original author: {original_author if original_author else "N/A"}
Quoted text: {quoted_text if quoted_text else "N/A"}
Text: {text}{thread_block}

Output format (STRICT JSON — no markdown fences, no extra text):
{{
  "category": "<CATEGORY>",
  "subcategory": "<subcategory>",
  "confidence": <0.0-1.0>,
  "reasoning": "<1 sentence explaining the classification>",
  "is_noise": <true/false>,
  "primary_mentions": [<list of chain names mentioned, or []>]
}}"""
    return prompt


def _build_batched_prompt(tweets: list[dict], chain: str) -> str:
    """Build a single LLM prompt for multiple tweets from the same chain."""
    subcat_lines = []
    for cat in CATEGORY_ORDER:
        if cat in SUBCATEGORY_MAP:
            subcats = ", ".join(SUBCATEGORY_MAP[cat].keys())
            subcat_lines.append(f"  - {cat}: {subcats}")
    subcat_block = "\n".join(subcat_lines)

    tweet_jsons = []
    for idx, t in enumerate(tweets):
        tweet_jsons.append(json.dumps({
            "id": idx,
            "chain": t.get("chain", chain),
            "text": t.get("text", ""),
            "author": t.get("account_handle", ""),
            "role": t.get("account_role", "contributor"),
            "is_retweet": t.get("is_retweet", False),
            "original_author": t.get("original_author", ""),
            "quoted_text": t.get("quoted_text", ""),
        }, ensure_ascii=False))

    prompt = f"""You are an expert crypto-industry analyst. Classify each tweet below into exactly one category and subcategory.

Categories (ordered by priority):
{chr(10).join(f"  - {cat}" for cat in CATEGORY_ORDER)}

Subcategories per category:
{subcat_block}

Rules:
1. Categorize by SEMANTIC CONTENT, not keyword presence.
2. A "wen mainnet" reply to a mainnet announcement is VISIBILITY, not TECH_EVENT.
3. A retweet of official news inherits the original's category.
4. Funding announcements with amounts >= $1M receive FINANCIAL.
5. "Audit complete" without findings → TECH_EVENT. "Audit finding" → RISK_ALERT.
6. Engagement bait, price predictions, memes → NOISE.
7. Only return the specified JSON array. No extra text, no markdown fences.
8. If chain-agnostic (mentions no specific chain), set primary_mentions to [].
9. Return EXACTLY one result per tweet, in the SAME ORDER as the input tweets.

Tweets to classify (index 0 to {len(tweets)-1}):
[
{chr(10).join(tweet_jsons)}
]

Output format — a single JSON array with {len(tweets)} elements. Element i corresponds to tweet i:
[
  {{"category": "<CATEGORY>", "subcategory": "<subcategory>", "confidence": <0.0-1.0>, "reasoning": "<1 sentence>", "is_noise": <true/false>, "primary_mentions": [<chain names or []>]}},
  ...
]"""
    return prompt


def _parse_batched_response(response: list, tweets: list[dict]) -> list[dict]:
    """Match LLM response array back to tweets. Returns enriched tweet copies."""
    enriched = []
    resp_len = len(response) if isinstance(response, list) else 0
    for idx, tweet in enumerate(tweets):
        tweet_copy = dict(tweet)
        if idx < resp_len and isinstance(response[idx], dict):
            sem = response[idx]
            is_valid, sanitized = _validate_enrichment(sem)
            if is_valid:
                tweet_copy["semantic"] = sanitized
            else:
                logger.warning(f"[semantic] Batch item {idx} failed validation")
        else:
            logger.warning(f"[semantic] Batch missing result for tweet {idx}")
        enriched.append(tweet_copy)
    return enriched


def _keyword_fallback(tweets: list[dict]) -> list[dict]:
    """Apply lightweight keyword-based semantic fallback when LLM is unavailable."""
    from processors.categorizer import _detect_subcategory_keyword
    enriched = []
    for t in tweets:
        text = t.get("text", "").lower()
        chain = t.get("chain", "unknown")
        tweet_copy = dict(t)
        category = "NEWS"
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                category = cat
                break
        subcat = _detect_subcategory_keyword(text, category)
        tweet_copy["semantic"] = {
            "category": category,
            "subcategory": subcat,
            "confidence": 0.4,
            "reasoning": "Keyword fallback (LLM unavailable)",
            "is_noise": category == "NOISE",
            "primary_mentions": [chain] if chain != "unknown" else [],
        }
        enriched.append(tweet_copy)
    return enriched


def _validate_enrichment(result: dict) -> tuple[bool, dict]:
    """Validate LLM enrichment result. Returns (is_valid, sanitized_result)."""
    required = {"category", "subcategory", "confidence", "reasoning", "is_noise"}
    if not required.issubset(result.keys()):
        missing = required - result.keys()
        logger.warning(f"Semantic enrichment missing keys: {missing}")
        return False, {}

    category = result.get("category", "")
    if category not in CATEGORY_ORDER:
        logger.warning(f"LLM returned unknown category: {category}")
        return False, {}

    subcategory = result.get("subcategory", "")
    valid_subcats = set(SUBCATEGORY_MAP.get(category, {}).keys()) | {"general"}
    if subcategory not in valid_subcats:
        logger.warning(f"LLM returned unknown subcategory '{subcategory}' for {category}")

    try:
        confidence = float(result.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    is_noise = bool(result.get("is_noise", False))
    primary_mentions = result.get("primary_mentions", [])
    if not isinstance(primary_mentions, list):
        primary_mentions = []

    sanitized = {
        "category": category,
        "subcategory": subcategory,
        "confidence": confidence,
        "reasoning": str(result.get("reasoning", "")),
        "is_noise": is_noise,
        "primary_mentions": primary_mentions,
    }
    return True, sanitized


class SemanticEnricher:
    """Enrich raw events (especially tweets) with LLM semantic categorization."""

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        cache: Optional[LLMCache] = None,
        threshold_high: float = 0.75,
        threshold_low: float = 0.50,
    ):
        self.client = client or LLMClient.from_env()
        self.cache = cache or LLMCache()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self._llm_available = True
        self._failures = 0
        self._max_failures_before_disable = 3

    def enrich_tweets(self, tweets: list[dict], max_batch_size: int = 15, max_workers: int = 4) -> list[dict]:
        """Batch enrichment for scraped tweet dicts — batched per-chain with parallel LLM calls.

        Groups tweets by chain, batches {max_batch_size} per LLM call, and runs up to
        {max_workers} concurrent LLM requests.
        """
        if not self._llm_available:
            logger.warning("[semantic] LLM unavailable — using keyword fallback for all tweets")
            return _keyword_fallback(tweets)

        # Group tweets by chain
        by_chain: dict[str, list[dict]] = {}
        for t in tweets:
            chain = t.get("chain", "unknown")
            by_chain.setdefault(chain, []).append(t)

        # Build work units
        work_units = []
        for chain, chain_tweets in by_chain.items():
            for i in range(0, len(chain_tweets), max_batch_size):
                batch = chain_tweets[i:i + max_batch_size]
                work_units.append((chain, batch))

        enriched_map: dict[int, dict] = {}

        def _process_batch(chain: str, batch: list[dict]) -> None:
            """Process one batch, storing results in enriched_map keyed by id(t)."""
            uncached = []
            uncached_ids = []
            idx_map = {}
            for t in batch:
                t_id = id(t)
                idx_map[t_id] = t
                text = t.get("text", "").strip()
                author = t.get("account_handle", "")
                is_retweet = t.get("is_retweet", False)
                quoted_text = t.get("quoted_text", "")
                cached = self.cache.get(
                    chain=chain, text=text, author=author,
                    is_retweet=is_retweet, quoted_text=quoted_text,
                )
                if cached:
                    t_copy = dict(t)
                    t_copy["semantic"] = cached
                    enriched_map[t_id] = t_copy
                else:
                    uncached.append(t)
                    uncached_ids.append(t_id)

            if not uncached:
                return

            prompt = _build_batched_prompt(uncached, chain)
            try:
                raw = self.client.generate_json(prompt)
            except LLMError as e:
                self._failures += 1
                if self._failures >= self._max_failures_before_disable:
                    self._llm_available = False
                    logger.warning(f"LLM disabled after {self._failures} consecutive failures")
                logger.warning(f"[semantic] Batch LLM call failed: {e}")
                fallback = _keyword_fallback(uncached)
                for t_id, fb_tweet in zip(uncached_ids, fallback):
                    enriched_map[t_id] = fb_tweet
                return

            if not isinstance(raw, list):
                logger.warning(f"[semantic] Batch LLM returned non-list: {type(raw).__name__}")
                fallback = _keyword_fallback(uncached)
                for t_id, fb_tweet in zip(uncached_ids, fallback):
                    enriched_map[t_id] = fb_tweet
                return

            parsed = _parse_batched_response(raw, uncached)
            for t_id, p_tweet in zip(uncached_ids, parsed):
                sem = p_tweet.get("semantic")
                orig = idx_map.get(t_id)
                if sem and orig:
                    self.cache.set(
                        chain=chain,
                        text=orig.get("text", ""),
                        author=orig.get("account_handle", ""),
                        is_retweet=orig.get("is_retweet", False),
                        quoted_text=orig.get("quoted_text", ""),
                        result=sem,
                    )
                enriched_map[t_id] = p_tweet

        # Execute in parallel
        if max_workers <= 1 or len(work_units) <= 1:
            for chain, batch in work_units:
                _process_batch(chain, batch)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_process_batch, ch, b): (ch, b)
                    for ch, b in work_units
                }
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        chain, batch = futures[future]
                        logger.error(f"[semantic] Parallel batch failed for {chain}: {e}")

        # Re-assemble in original order
        enriched = []
        for t in tweets:
            t_id = id(t)
            enriched.append(enriched_map.get(t_id, dict(t)))

        enriched_count = sum(1 for t in enriched if "semantic" in t)
        logger.info(
            f"[semantic] Enriched {enriched_count}/{len(tweets)} tweets "
            f"({len(work_units)} batches, {max_workers} workers)"
        )
        return enriched

    def enrich(self, event: dict) -> dict:
        """Enrich a single event dict (backward compat for pipeline events)."""
        source = event.get("source", "") or event.get("source_name", "")
        text = event.get("description", "").strip()

        if not text or "twitter" not in source.lower():
            return event

        chain = event.get("chain", "unknown")
        evidence = event.get("evidence", {}) or {}
        author = evidence.get("author", "")
        role = evidence.get("role", "contributor")
        is_retweet = evidence.get("is_retweet", False)
        original_author = evidence.get("original_author", "")
        quoted_text = evidence.get("quoted_text", "")

        semantic = self._enrich_text(
            text=text,
            chain=chain,
            author=author,
            role=role,
            is_retweet=is_retweet,
            original_author=original_author,
            quoted_text=quoted_text,
        )

        if semantic:
            event = dict(event)
            event["semantic"] = semantic

        return event

    def _enrich_text(
        self,
        text: str,
        chain: str,
        author: str,
        role: str,
        is_retweet: bool,
        original_author: str,
        quoted_text: str,
        thread_context: str = "",
    ) -> Optional[dict]:
        """Core enrichment: check cache, call LLM, validate, store cache."""

        if not self._llm_available:
            logger.debug("LLM disabled due to repeated failures — skipping enrichment")
            return None

        cached = self.cache.get(
            chain=chain,
            text=text,
            author=author,
            is_retweet=is_retweet,
            quoted_text=quoted_text,
        )
        if cached:
            return cached

        prompt = _build_prompt(
            text=text,
            chain=chain,
            author=author,
            role=role,
            is_retweet=is_retweet,
            original_author=original_author,
            quoted_text=quoted_text,
            thread_context=thread_context,
        )

        try:
            result = self.client.generate_json(prompt)
        except LLMError as e:
            self._failures += 1
            if self._failures >= self._max_failures_before_disable:
                self._llm_available = False
                logger.warning(f"LLM disabled after {self._failures} consecutive failures")
            logger.warning(f"Semantic enrichment LLM call failed: {e}")
            return None

        is_valid, semantic = _validate_enrichment(result)
        if not is_valid:
            self._failures += 1
            logger.warning("Semantic enrichment produced invalid result")
            return None

        self._failures = max(0, self._failures - 1)

        self.cache.set(
            chain=chain,
            text=text,
            author=author,
            is_retweet=is_retweet,
            quoted_text=quoted_text,
            result=semantic,
        )
        return semantic

    def get_health(self) -> dict:
        """Return health status for observability."""
        return {
            "llm_available": self._llm_available,
            "failures": self._failures,
            "threshold_high": self.threshold_high,
            "threshold_low": self.threshold_low,
            "provider": self.client.provider,
            "model": self.client.model,
        }
