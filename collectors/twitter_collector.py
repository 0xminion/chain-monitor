"""Twitter/X collector — monitors official chain accounts and key contributors.

Subprocess-based architecture (v0.2 fix for SteamOS stability):
  - Each handle is scraped by a standalone `scripts/twitter_worker.py` subprocess.
  - Zero multiprocessing / ProcessPoolExecutor — avoids Playwright EPIPE crashes.
  - Concurrency controlled by asyncio.Semaphore.

Author: 0xminion
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_env, get_pipeline_value

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
WORKER_SCRIPT = REPO_ROOT / "scripts" / "twitter_worker.py"

# Detect project venv python for subprocess workers
_VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
WORKER_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable
TWITTER_ACCOUNTS_PATH = REPO_ROOT / "config" / "twitter_accounts.yaml"
RAW_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "raw"
SUMMARY_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"
ENRICHED_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "enriched"
COOKIES_PATH = REPO_ROOT / "storage" / "twitter" / "cookies.json"

MAX_SCROLLS = 6  # ~6 scrolls per handle × ~10 handles per batch = reasonable context lifetime
WORKER_TIMEOUT = 300  # seconds per batch (batch reuses browser context)


class TwitterCollector(BaseCollector):
    """Collects tweets from chain official accounts and contributors via subprocess workers."""

    def __init__(self, standalone_mode: bool = False, lookback_hours: int | None = None,
                 max_workers: int | None = None, num_batches: int | None = None):
        super().__init__(name="twitter")
        self.standalone_mode = standalone_mode
        self.lookback_hours = lookback_hours or int(get_env(
            "TWITTER_LOOKBACK_HOURS",
            str(get_pipeline_value("twitter.lookback_hours", 24))
        ))
        self.max_workers = int(get_env(
            "TWITTER_MAX_WORKERS",
            str(max_workers if max_workers is not None else get_pipeline_value("twitter.max_workers", 15))
        ))
        self.num_batches = int(get_env(
            "TWITTER_NUM_BATCHES",
            str(num_batches if num_batches is not None else get_pipeline_value("twitter.num_batches", 10))
        ))
        self._accounts: dict[str, dict] = {}
        self._load_accounts()
        RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_OUT_DIR.mkdir(parents=True, exist_ok=True)
        ENRICHED_OUT_DIR.mkdir(parents=True, exist_ok=True)

    def _load_accounts(self):
        import yaml
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
        logger.info(f"[twitter] Loaded {len(self._accounts)} chains, {total} total accounts")

    # -----------------------------------------------------------------------
    # Collection — subprocess-based
    # -----------------------------------------------------------------------
    async def collect(self) -> list[dict]:
        if not WORKER_SCRIPT.exists():
            logger.error(f"[twitter] Worker script missing: {WORKER_SCRIPT}")
            return []

        if not self._accounts:
            logger.warning("[twitter] No accounts configured — skipping")
            return []

        # Flatten
        all_handles: list[tuple[str, dict]] = []
        for chain_name, cfg in self._accounts.items():
            for hdl in cfg.get("official", []) + cfg.get("contributors", []):
                all_handles.append((chain_name, hdl))

        if not all_handles:
            return []

        cookies = str(COOKIES_PATH) if COOKIES_PATH.exists() else None
        # Batch handles into groups for context-reuse, respecting num_batches config
        if self.num_batches > 0:
            batch_size = max(1, (len(all_handles) + self.num_batches - 1) // self.num_batches)
        else:
            batch_size = 10
        batches: list[list[tuple[str, dict]]] = []
        for i in range(0, len(all_handles), batch_size):
            batches.append(all_handles[i:i + batch_size])

        sem = asyncio.Semaphore(self.max_workers)

        # Timeout per handle: 90s base + 30s per handle in the batch
        batch_timeout = max(120, 90 + 30 * max(len(b) for b in batches))

        async def _scrape_batch(batch: list[tuple[str, dict]]) -> list[dict]:
            async with sem:
                return await self._run_worker_batch(batch, cookies, batch_timeout)

        start = time.time()
        logger.info(
            f"[twitter] {len(all_handles)} handles in {len(batches)} batches, "
            f"batch_size={batch_size}, max_workers={self.max_workers}, "
            f"lookback={self.lookback_hours}h, timeout={batch_timeout}s"
        )

        tasks = [asyncio.create_task(_scrape_batch(b)) for b in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_tweets: list[dict] = []
        for batch, res in zip(batches, results):
            if isinstance(res, Exception):
                handles_str = ", ".join(h.get("handle","") for _, h in batch)
                logger.error(f"[twitter] Batch failed ({handles_str}): {res}")
            else:
                for t in res:
                    handle = t.get("account_handle", "")
                    chain = t.get("chain", "unknown")
                    hdl_obj = next((h for _, h in batch if h.get("handle","").lstrip("@") == handle), None)
                    if hdl_obj:
                        chain_cfg = self._accounts.get(chain, {})
                        role = "official" if hdl_obj in chain_cfg.get("official", []) else "contributor"
                        t["account_role"] = role
                        t["account_name"] = hdl_obj.get("name", handle)
                        t["account_reliability"] = hdl_obj.get("reliability", 0.75)
                        t["scraped_at"] = datetime.now(timezone.utc).isoformat()
                if res:
                    logger.info(f"[twitter] Batch ({len(batch)} handles): {len(res)} tweets")
                all_tweets.extend(res)

        elapsed = time.time() - start
        logger.info(f"[twitter] Total: {len(all_tweets)} tweets in {elapsed:.1f}s")
        if all_tweets:
            self.health.mark_success()

        self._persist_raw(all_tweets)
        return self._tweets_to_events(all_tweets)

    async def _run_worker_batch(self, batch: list[tuple[str, dict]], cookies: Optional[str], timeout: int) -> list[dict]:
        """Spawn one subprocess worker that reuses a single browser context for a batch of handles."""
        handles_csv = ",".join(hdl.get("handle", "").lstrip("@") for _, hdl in batch)
        chains_csv = ",".join(chain for chain, _ in batch)

        args = [
            str(WORKER_SCRIPT),
            "--handles", handles_csv,
            "--chains", chains_csv,
            "--lookback", str(self.lookback_hours),
            "--max-scrolls", str(MAX_SCROLLS),
        ]
        if cookies:
            args += ["--cookies", cookies]

        proc = await asyncio.create_subprocess_exec(
            WORKER_PYTHON, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"[twitter] Batch timed out after {timeout}s — killing")
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.terminate()
            return []

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            logger.warning(f"[twitter] Batch exit={proc.returncode}: {err}")
            return []

        tweets: list[dict] = []
        for line in stdout.decode("utf-8", errors="ignore").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                tweets.append(t)
            except json.JSONDecodeError:
                continue

        return tweets

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------
    def _persist_raw(self, tweets: list[dict]):
        if not tweets:
            return
        now = datetime.now(timezone.utc)
        file_name = f"tweets_{now.strftime('%Y%m%d_%H%M%S')}.json"
        path = RAW_OUT_DIR / file_name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)
        logger.info(f"[twitter] Raw tweets persisted: {path}")

        month_key = now.strftime("%Y-%m")
        summary_path = SUMMARY_OUT_DIR / f"twitter_summary_{month_key}.md"
        self._append_summary_md(summary_path, tweets, now)

    def _append_summary_md(self, path: Path, tweets: list[dict], now: datetime):
        new_lines = [
            f"\n## Run @ {now.isoformat()}\n",
            f"**Tweets collected:** {len(tweets)}\n",
        ]
        for t in tweets:
            role = t.get("account_role", "unknown")
            chain = t.get("chain", "unknown")
            handle = t.get("account_handle", "")
            ts = t.get("timestamp", "")
            text = t.get("text", "")
            url = t.get("url", "")
            is_rt = t.get("is_retweet", False)
            is_q = t.get("is_quote_tweet", False)
            badges = []
            if is_rt:
                badges.append("🔁 RT")
            if is_q:
                badges.append("💬 Quote")
            badge_str = f" [{' | '.join(badges)}]" if badges else ""
            new_lines.append(
                f"- **[{chain}]** @{handle} ({role}){badge_str} — [{ts}]({url})\n"
                f"  > {text[:280]}{'...' if len(text) > 280 else ''}\n"
            )
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        logger.info(f"[twitter] Summary appended: {path}")

    # -----------------------------------------------------------------------
    # Convert tweets → pipeline events
    # -----------------------------------------------------------------------
    def _tweets_to_events(self, tweets: list[dict]) -> list[dict]:
        events = []
        for t in tweets:
            chain = t.get("chain", "unknown")
            text = t.get("text", "").strip()
            is_rt = t.get("is_retweet", False)
            is_q = t.get("is_quote_tweet", False)
            quoted_text = t.get("quoted_text", "")
            original_author = t.get("original_author", "")
            handle = t.get("account_handle", "")
            role = t.get("account_role", "official")
            reliability = float(t.get("account_reliability", 0.75))
            url = t.get("url", "")
            ts = t.get("timestamp", "")
            likes = t.get("likes", 0)
            retweet_count = t.get("retweets", 0)

            if is_rt and original_author:
                description = f"@{handle} reposted @{original_author}: {text}"
            elif is_q and quoted_text:
                description = f"@{handle} quoted: {text} — Quoting: {quoted_text}"
            else:
                description = text

            if is_rt and role == "contributor":
                chain_cfg = self._accounts.get(chain, {})
                official_handles = {h["handle"].lstrip("@").lower() for h in chain_cfg.get("official", [])}
                if original_author.lower() in official_handles:
                    reliability = max(reliability, 0.95)

            evidence = {
                "tweet_id": t.get("tweet_id"),
                "url": url,
                "author": handle,
                "role": role,
                "timestamp": ts,
                "likes": likes,
                "retweets": retweet_count,
                "is_retweet": is_rt,
                "is_quote": is_q,
                "original_author": original_author,
                "quoted_text": quoted_text,
                "media_urls": t.get("media_urls", []),
                "semantic": t.get("semantic"),
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
