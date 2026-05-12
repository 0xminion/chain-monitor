"""Twitter/X collector — X Search API via composable provider backends.

Replaces subprocess browser scraping with efficient API-based extraction.
Uses grok-4.3 x_search tool (5-20 tokens per tweet returned).
Token-optimized: shared system prompt, minimal user messages, JSON-only extraction.

Architecture:
  collector.py         TwitterCollector (pipeline interface)
  provider.py          XSearchProvider (abstract)
  direct_xai.py        DirectXAIProvider  (api.x.ai)
  antseed_provider.py  AntseedBuyerProvider (antseed P2P proxy)
  token_tracker.py     PipelineTokenTracker

To swap providers: set XSEARCH_PROVIDER env var to "direct_xai" or "antseed_buyer".
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

from collectors.base import BaseCollector
from collectors.twitter.provider import XSearchProvider
from collectors.twitter.token_tracker import PipelineTokenTracker
from config.loader import get_env

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
TWITTER_ACCOUNTS_PATH = REPO_ROOT / "config" / "twitter_accounts.yaml"
RAW_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "raw"
SUMMARY_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"

# Hard cap from xAI: allowed_x_handles ≤ 10
MAX_HANDLES_PER_CALL = 10


def _get_provider() -> XSearchProvider:
    """Factory: instantiate the configured X Search provider."""
    provider_name = os.environ.get("XSEARCH_PROVIDER", "antseed_buyer")

    if provider_name == "antseed_buyer":
        from collectors.twitter.antseed_provider import AntseedBuyerProvider
        return AntseedBuyerProvider()

    if provider_name == "surplus_intelligence":
        from collectors.twitter.surplus_provider import SurplusIntelligenceProvider
        return SurplusIntelligenceProvider()

    if provider_name == "direct_xai":
        from collectors.twitter.direct_xai import DirectXAIProvider
        return DirectXAIProvider()

    # Allow fully-qualified class path for custom providers
    # e.g. XSEARCH_PROVIDER=myapp.providers.MyProvider
    parts = provider_name.rsplit(".", 1)
    if len(parts) == 2:
        import importlib
        mod = importlib.import_module(parts[0])
        return getattr(mod, parts[1])()

    raise ValueError(f"Unknown XSEARCH_PROVIDER: {provider_name}")


class TwitterCollector(BaseCollector):
    """Collects tweets from chain accounts using X Search API.

    Config: config/twitter_accounts.yaml → {twitter_accounts: {chain: {official: [...], contributors: [...]}}}
    Env: XSEARCH_PROVIDER, XAI_API_KEY, ANSTEED_PROXY_URL
    """

    def __init__(
        self,
        provider: XSearchProvider | None = None,
        lookback_hours: int = 24,
    ):
        super().__init__(name="twitter")
        self._lookback_hours = lookback_hours
        self._provider = provider
        self._accounts: dict[str, dict] = {}
        self._token_tracker = PipelineTokenTracker()
        self._load_accounts()
        RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Provider lazy init (allows overriding in tests)
    # ------------------------------------------------------------------
    @property
    def provider(self) -> XSearchProvider:
        if self._provider is None:
            self._provider = _get_provider()
        return self._provider

    def _load_accounts(self):
        if not TWITTER_ACCOUNTS_PATH.exists():
            logger.warning(f"[twitter] Config not found: {TWITTER_ACCOUNTS_PATH}")
            return
        with open(TWITTER_ACCOUNTS_PATH) as f:
            data = yaml.safe_load(f) or {}
        self._accounts = data.get("twitter_accounts", {})
        total = sum(
            len(c.get("official", [])) + len(c.get("contributors", []))
            for c in self._accounts.values()
        )
        logger.info(
            f"[twitter] Loaded {len(self._accounts)} chains, {total} total accounts"
        )

    # ------------------------------------------------------------------
    # Main collection entry point
    # ------------------------------------------------------------------
    async def collect(self) -> list[dict]:
        """Run X Search extraction for all configured accounts.

        Returns:
            List of pipeline events (dicts) compatible with chain-monitor.
        """
        if not self._accounts:
            logger.warning("[twitter] No accounts configured — skipping")
            return []

        # Flatten all handles with chain + metadata
        all_handles: list[tuple[str, str, dict]] = []  # (chain, handle, account_cfg)
        for chain_name, cfg in self._accounts.items():
            for hdl in cfg.get("official", []):
                hdl.setdefault("role", "official")
                hdl.setdefault("reliability", 0.85)
                all_handles.append((chain_name, hdl["handle"].lstrip("@"), hdl))
            for hdl in cfg.get("contributors", []):
                hdl.setdefault("role", "contributor")
                hdl.setdefault("reliability", 0.70)
                all_handles.append((chain_name, hdl["handle"].lstrip("@"), hdl))

        if not all_handles:
            return []

        # Batch handles into groups of ≤10
        batches = self._batch_handles(all_handles)
        logger.info(
            f"[twitter] {len(all_handles)} handles → {len(batches)} batches "
            f"(max {MAX_HANDLES_PER_CALL}/call)"
        )

        # Compute date range
        now = datetime.now(timezone.utc)
        from_date = (now - timedelta(hours=self._lookback_hours)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        # Execute all batches concurrently
        start = time.time()

        async def _search_batch(batch):
            handles = [h for _, h, _ in batch]
            result = await self.provider.search(
                handles=handles,
                from_date=from_date,
                to_date=to_date,
            )
            self._token_tracker.record(result.usage, had_error=result.error is not None)
            return batch, result

        tasks = [asyncio.create_task(_search_batch(b)) for b in batches]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all tweets with chain/metadata attribution
        all_tweets: list[dict] = []
        for item in all_results:
            if isinstance(item, Exception):
                logger.error(f"[twitter] Batch failed with exception: {item}")
                continue
            batch, result = item
            if result.error:
                handles_str = ", ".join(h for _, h, _ in batch)
                logger.error(f"[twitter] Batch error ({handles_str}): {result.error}")
                continue

            # Attach chain + role metadata from our config
            chain_map = {h: (c, cfg) for c, h, cfg in batch}
            for tweet in result.tweets:
                handle = tweet.get("handle", "").lstrip("@")
                if handle in chain_map:
                    chain, cfg = chain_map[handle]
                    tweet["chain"] = chain
                    tweet["account_role"] = cfg.get("role", "official")
                    tweet["account_reliability"] = cfg.get("reliability", 0.75)
                    tweet["account_name"] = cfg.get("name", handle)
                else:
                    tweet["chain"] = "unknown"
                    tweet["account_role"] = "unknown"
                    tweet["account_reliability"] = 0.5
                    tweet["account_name"] = handle

            logger.info(
                f"[twitter] Batch ({len(batch)} handles): {len(result.tweets)} tweets"
            )
            all_tweets.extend(result.tweets)

        elapsed = time.time() - start
        logger.info(
            f"[twitter] Total: {len(all_tweets)} tweets in {elapsed:.1f}s "
            f"({self._token_tracker.summary()})"
        )

        if all_tweets:
            self.health.mark_success()
        else:
            logger.warning("[twitter] No tweets collected — check API key and date range")

        self._persist_raw(all_tweets)
        return self._tweets_to_events(all_tweets)

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------
    @staticmethod
    def _batch_handles(
        handles: list[tuple[str, str, dict]],
        max_per_batch: int = MAX_HANDLES_PER_CALL,
    ) -> list[list[tuple[str, str, dict]]]:
        batches = []
        for i in range(0, len(handles), max_per_batch):
            batches.append(handles[i : i + max_per_batch])
        return batches

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _persist_raw(self, tweets: list[dict]):
        if not tweets:
            return
        now = datetime.now(timezone.utc)
        file_name = f"tweets_{now.strftime('%Y%m%d_%H%M%S')}.json"
        path = RAW_OUT_DIR / file_name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)
        logger.info(f"[twitter] Raw tweets persisted: {path}")

        # Monthly summary markdown
        month_key = now.strftime("%Y-%m")
        summary_path = SUMMARY_OUT_DIR / f"twitter_summary_{month_key}.md"
        self._append_summary_md(summary_path, tweets, now)

    def _append_summary_md(self, path: Path, tweets: list[dict], now: datetime):
        new_lines = [f"\n## Run @ {now.isoformat()}\n", f"**Tweets collected:** {len(tweets)}\n"]
        for t in tweets:
            role = t.get("account_role", "unknown")
            chain = t.get("chain", "unknown")
            handle = t.get("handle", t.get("account_handle", ""))
            ts = t.get("created_at", "")
            text = t.get("text", "")
            is_rt = t.get("is_retweet", False)
            rt_author = t.get("retweeted_handle", "")
            badges = []
            if is_rt:
                badges.append(f"🔁 RT @{rt_author}" if rt_author else "🔁 RT")
            badge_str = f" [{' | '.join(badges)}]" if badges else ""
            new_lines.append(
                f"- **[{chain}]** @{handle} ({role}){badge_str} — {ts}\n"
                f"  > {text[:280]}{'...' if len(text) > 280 else ''}\n"
            )
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        logger.info(f"[twitter] Summary appended: {path}")

    # ------------------------------------------------------------------
    # Convert tweets → pipeline events
    # ------------------------------------------------------------------
    def _tweets_to_events(self, tweets: list[dict]) -> list[dict]:
        events = []
        for t in tweets:
            chain = t.get("chain", "unknown")
            text = t.get("text", "").strip()
            is_rt = t.get("is_retweet", False)
            rt_handle = t.get("retweeted_handle", "")
            handle = t.get("handle", t.get("account_handle", ""))
            role = t.get("account_role", "official")
            reliability = float(t.get("account_reliability", 0.75))
            ts = t.get("created_at", "")
            tweet_id = t.get("id", "")
            likes = t.get("likes", 0)
            retweet_count = t.get("retweets", 0)
            replies = t.get("replies", 0)

            # Build URL from tweet_id + handle
            url = f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else ""

            if is_rt and rt_handle:
                description = f"@{handle} reposted @{rt_handle}: {text}"
            else:
                description = text

            # Bump reliability if a contributor retweets official account
            if is_rt and role == "contributor":
                chain_cfg = self._accounts.get(chain, {})
                official_handles = {
                    h["handle"].lstrip("@").lower()
                    for h in chain_cfg.get("official", [])
                }
                if rt_handle.lower() in official_handles:
                    reliability = max(reliability, 0.95)

            evidence = {
                "tweet_id": tweet_id,
                "url": url,
                "author": handle,
                "role": role,
                "timestamp": ts,
                "likes": likes,
                "retweets": retweet_count,
                "replies": replies,
                "is_retweet": is_rt,
                "retweeted_handle": rt_handle,
            }

            events.append({
                "type": "twitter_post",
                "category": "NEWS",
                "chain": chain,
                "source_name": f"Twitter (@{handle})",
                "source": "twitter",
                "description": description[:500],
                "evidence": evidence,
                "timestamp": ts or datetime.now(timezone.utc).isoformat(),
                "reliability": reliability,
                "has_official_source": role == "official" or reliability >= 0.95,
            })
        return events

    # ------------------------------------------------------------------
    # Token tracking accessor
    # ------------------------------------------------------------------
    def get_token_summary(self) -> dict:
        """Return cumulative token usage for this run."""
        return self._token_tracker.summary()
