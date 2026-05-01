"""Twitter/X collector — monitors official chain accounts and key contributors.

Uses Playwright with existing browser session cookies for authentication.
Anti-detection strategy: Camoufox -> Chromium persistent context -> standard Chromium.

Author: 0xminion
"""

import json
import logging
import os
import random

import time
import concurrent.futures
import multiprocessing as mp
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from collectors.base import BaseCollector
from config.loader import get_env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
TWITTER_ACCOUNTS_PATH = REPO_ROOT / "config" / "twitter_accounts.yaml"
RAW_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "raw"
SUMMARY_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"

# ---------------------------------------------------------------------------
# NEW v0.2: Enrichment output dir
# ---------------------------------------------------------------------------
ENRICHED_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "enriched"


# ---------------------------------------------------------------------------
# JS script — extract timeline tweets  (works on x.com profile pages)
# ---------------------------------------------------------------------------
EXTRACT_TWEETS_JS = r"""
() => {
    const tweets = [];
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    const seen = new Set();

    articles.forEach(art => {
        const links = art.querySelectorAll('a[href*="/status/"]');
        let tweetUrl = '';
        let tweetId = '';
        for (const a of links) {
            const m = a.href.match(/\/status\/(\d+)/);
            if (m) { tweetId = m[1]; tweetUrl = a.href.split('?')[0]; break; }
        }
        if (!tweetId || seen.has(tweetId)) return;
        seen.add(tweetId);

        // Time
        const timeEl = art.querySelector('time');
        const timestamp = timeEl ? timeEl.getAttribute('datetime') : '';

        // Text — collect all tweetText divs, pick the longest (handles RTs with nested text)
        const allTextDivs = Array.from(art.querySelectorAll('div[data-testid="tweetText"]'));
        let text = '';
        for (const td of allTextDivs) {
            const candidate = td.innerText.trim();
            if (candidate.length > text.length) {
                text = candidate;
            }
        }

        // Metrics
        const replyBtn = art.querySelector('button[data-testid="reply"]');
        const retweetBtn = art.querySelector('button[data-testid="retweet"]');
        const likeBtn = art.querySelector('button[data-testid="like"]');
        const getCount = (el) => {
            if (!el) return 0;
            const txt = el.innerText.replace(/,/g, '');
            const n = parseFloat(txt);
            if (txt.includes('K')) return n * 1000;
            if (txt.includes('M')) return n * 1000000;
            return isNaN(n) ? 0 : n;
        };
        const replies = getCount(replyBtn);
        const retweets = getCount(retweetBtn);
        const likes = getCount(likeBtn);

        // Images / media
        const imgs = Array.from(art.querySelectorAll('img')).map(i => i.src).filter(s => s && !s.includes('profile_images'));

        // Detect retweet
        const rtLabel = art.querySelector('[data-testid="socialContext"]');
        const isRetweet = !!(rtLabel && rtLabel.innerText.toLowerCase().includes('reposted'));

        // Original author (for RT)
        let originalAuthor = '';
        if (isRetweet) {
            const rtLink = art.querySelector('a[role="link"][href^="/"]');
            if (rtLink) originalAuthor = rtLink.href.split('/').filter(Boolean)[0] || '';
        }

        // Detect quoted tweet
        const quoteContainer = art.querySelector('div[role="link"]');
        const isQuoteTweet = !!(quoteContainer && art.innerText.includes('Quoting'));
        let quotedText = '';
        if (isQuoteTweet) {
            const qText = quoteContainer.querySelector('div[data-testid="tweetText"]');
            quotedText = qText ? qText.innerText.trim() : '';
        }

        tweets.push({
            tweet_id: tweetId,
            url: tweetUrl,
            timestamp,
            text,
            is_retweet: isRetweet,
            original_author: originalAuthor,
            is_quote_tweet: isQuoteTweet,
            quoted_text: quotedText,
            replies,
            retweets,
            likes,
            media_urls: imgs.slice(0, 4),
        });
    });

    return tweets;
}
"""

# ---------------------------------------------------------------------------
# JS script for scrolling to load more
# ---------------------------------------------------------------------------
SCROLL_JS = """() => { window.scrollTo(0, document.body.scrollHeight); }"""


class TwitterCollector(BaseCollector):
    """Collects tweets from chain official accounts and contributors via Playwright."""

    def __init__(self, standalone_mode: bool = False, lookback_hours: int | None = None,
                 max_workers: int = 1, num_batches: int = 1):
        """
        Args:
            standalone_mode: If True, skips dedup/reinforcement and writes to own JSON.
            lookback_hours: Override global default. Defaults to env TWITTER_LOOKBACK_HOURS (default 24).
            max_workers: Number of parallel Playwright workers.
            num_batches: Number of handle batches to split across workers.
        """
        super().__init__(name="twitter")
        self.standalone_mode = standalone_mode
        self.lookback_hours = lookback_hours or int(get_env("TWITTER_LOOKBACK_HOURS", "24"))
        self.max_workers = int(get_env("TWITTER_MAX_WORKERS", str(max_workers)))
        self.num_batches = int(get_env("TWITTER_NUM_BATCHES", str(num_batches)))
        self._playwright = None
        self._browser = None
        self._context = None
        self._accounts: dict[str, list[dict]] = {}  # chain -> list of handle configs        
        # Load accounts from YAML
        self._load_accounts()

        # Ensure output dirs exist
        RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_OUT_DIR.mkdir(parents=True, exist_ok=True)
        ENRICHED_OUT_DIR.mkdir(parents=True, exist_ok=True)

    def _load_accounts(self):
        """Load twitter_accounts.yaml."""
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
    # Browser lifecycle — anti-detection tiered fallback
    # -----------------------------------------------------------------------
    def _start_browser(self):
        """Launch browser with best available anti-detection strategy."""
        from playwright.sync_api import sync_playwright
        import multiprocessing

        in_forked_worker = multiprocessing.current_process().name != "MainProcess"
        if in_forked_worker:
            logger.info("[twitter] Running in forked worker — skipping Camoufox and persistent profile to avoid lock contention")

        self._playwright = sync_playwright().start()

        # --- Tier 1: Camoufox (anti-detect) — skip in forked workers -----------------
        if not in_forked_worker:
            try:
                from camoufox.sync_api import Camoufox
                logger.info("[twitter] Using Camoufox (anti-detect)")
                self._browser = Camoufox(headless=True).__enter__()
                self._context = self._browser
                return
            except Exception as e:
                logger.info(f"[twitter] Camoufox failed ({e}), trying Chromium persistent context")

        # --- Tier 2: Chromium persistent context with user profile — skip in workers --
        if not in_forked_worker:
            profile_path = self._find_chrome_profile()
            if profile_path:
                try:
                    logger.info(f"[twitter] Using Chromium persistent profile: {profile_path}")
                    self._context = self._playwright.chromium.launch_persistent_context(
                        profile_path,
                        headless=True,
                        viewport={"width": 1280, "height": 800},
                        locale="en-US",
                        args=["--disable-blink-features=AutomationControlled"],
                    )
                    self._browser = self._context
                    return
                except Exception as e:
                    logger.info(f"[twitter] Persistent context failed ({e}), falling back to plain Chromium")

        # --- Tier 3: Plain Chromium + storage state (safe for workers) ---------------
        storage_state = self._find_storage_state()
        ss = storage_state if storage_state else None
        if ss:
            logger.info(f"[twitter] Using Chromium with storage_state: {ss}")
        else:
            logger.info("[twitter] Using plain Chromium (no cookies — may hit login wall)")

        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--single-process",
                "--no-sandbox",
                "--no-zygote",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--max_old_space_size=256",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            storage_state=ss,
        )

    def _find_chrome_profile(self) -> Optional[Path]:
        """Find existing Chrome/Chromium profile path."""
        candidates = [
            Path.home() / ".config" / "google-chrome" / "Default",
            Path.home() / ".config" / "chromium" / "Default",
            Path.home() / ".config" / "BraveSoftware" / "Brave-Browser" / "Default",
            Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default",  # macOS
        ]
        for c in candidates:
            if c.exists():
                return c.parent.parent  # Return the *profile root* ( e.g. ~/.config/google-chrome )
        return None

    def _find_storage_state(self) -> Optional[str]:
        """Find exported storage_state.json for cookie injection."""
        candidates = [
            REPO_ROOT / "storage" / "twitter" / "cookies.json",
            REPO_ROOT / ".twitter_cookies.json",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def _cleanup(self):
        """Close browser resources and clean up any orphaned Chrome processes."""
        # Fast-path: kill Chrome tree with SIGTERM → wait → SIGKILL
        import signal
        our_pid = os.getpid()
        for sig, label in [(signal.SIGTERM, "TERM"), (signal.SIGKILL, "KILL")]:
            try:
                ps_out = subprocess.run(
                    ["ps", "-eo", "pid,ppid,comm"],
                    capture_output=True, text=True, check=False,
                )
                pid_to_ppid = {}
                pid_to_comm = {}
                for line in ps_out.stdout.strip().split("\n")[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            p, pp = int(parts[0]), int(parts[1])
                            pid_to_ppid[p] = pp
                            pid_to_comm[p] = parts[2]
                        except ValueError:
                            pass
                # Walk full tree from our PID
                descendants = set()
                stack = [our_pid]
                while stack:
                    cur = stack.pop()
                    for child_pid, ppid in pid_to_ppid.items():
                        if ppid == cur and child_pid not in descendants:
                            descendants.add(child_pid)
                            stack.append(child_pid)
                for pid in descendants:
                    if "chrome" in pid_to_comm.get(pid, "").lower():
                        try:
                            os.kill(pid, sig)
                        except (ProcessLookupError, PermissionError):
                            pass
            except Exception:
                pass
            if sig == signal.SIGTERM:
                time.sleep(0.5)

        # Graceful Playwright cleanup (may already be dead)
        try:
            if self._context and hasattr(self._context, "close"):
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser and hasattr(self._browser, "close"):
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Collection loop
    # -----------------------------------------------------------------------
    def collect(self) -> list[dict]:
        """Run Twitter collection with parallel batching.

        Splits handles into `num_batches` batches, spawns up to `max_workers`
        processes. Each worker gets its own browser context + one reused page.
        Workers are independent (no shared state).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        if not self._accounts:
            logger.warning("[twitter] No accounts configured -- skipping")
            return []

        # Flatten (chain_name, handle_cfg) tuples
        all_handles: list[tuple[str, dict]] = []
        for chain_name, cfg in self._accounts.items():
            for hdl in cfg.get("official", []) + cfg.get("contributors", []):
                all_handles.append((chain_name, hdl))

        if not all_handles:
            return []

        # Split into batches
        if self.num_batches >= len(all_handles):
            batches = [[h] for h in all_handles]
        else:
            batch_size = max(1, len(all_handles) // self.num_batches)
            batches = [
                all_handles[i:i + batch_size]
                for i in range(0, len(all_handles), batch_size)
            ]

        logger.info(
            f"[twitter] {len(all_handles)} handles into {len(batches)} batches, "
            f"max_workers={self.max_workers}"
        )

        # Run batches in parallel via ProcessPoolExecutor
        all_tweets: list[dict] = []
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers,
            ) as executor:
                futures = {
                    executor.submit(
                        TwitterCollector._run_batch,
                        batch_id,
                        batch,
                        self.lookback_hours,
                        self.standalone_mode,
                    ): batch_id
                    for batch_id, batch in enumerate(batches)
                }
                for future in concurrent.futures.as_completed(futures):
                    batch_id = futures[future]
                    try:
                        batch_tweets = future.result()
                        all_tweets.extend(batch_tweets)
                        logger.info(
                            f"[twitter] Batch-{batch_id} returned {len(batch_tweets)} tweets"
                        )
                    except Exception as exc:
                        logger.error(f"[twitter] Batch-{batch_id} failed: {exc}")
        except Exception as exc:
            logger.error(f"[twitter] Parallel execution failed: {exc}")
            logger.info("[twitter] Falling back to sequential collection...")
            all_tweets = self._collect_single_worker(all_handles, cutoff)

        logger.info(f"[twitter] Total tweets collected: {len(all_tweets)}")
        if all_tweets:
            self.health.mark_success()

        self._persist_raw(all_tweets)
        events = self._tweets_to_events(all_tweets)
        return events

    def _collect_single_worker(
        self, handles: list[tuple[str, dict]], cutoff: datetime
    ) -> list[dict]:
        """Sequential fallback: one browser context, one reused page."""
        all_tweets: list[dict] = []
        self._start_browser()
        page = self._context.new_page() if self._context else None
        try:
            for chain_name, hdl in handles:
                handle = hdl["handle"].lstrip("@")
                tweets = self._scrape_profile(
                    handle, hdl, chain_name, cutoff, page=page
                )
                all_tweets.extend(tweets)
                time.sleep(random.randint(3, 7))
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            self._cleanup()
        return all_tweets

    @classmethod
    def _run_batch(
        cls,
        batch_id: int,
        batch: list[tuple[str, dict]],
        lookback_hours: int,
        standalone_mode: bool,
    ) -> list[dict]:
        """Worker function for ProcessPoolExecutor.

        Each worker gets its own browser context + one reused page.
        Instantiates a fresh TwitterCollector with no shared state.
        """
        import logging

        worker_logger = logging.getLogger(f"twitter-batch-{batch_id}")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        collector = cls(
            standalone_mode=standalone_mode,
            lookback_hours=lookback_hours,
        )
        all_tweets: list[dict] = []

        try:
            collector._start_browser()
            page = collector._context.new_page() if collector._context else None
            for chain_name, hdl in batch:
                handle = hdl["handle"].lstrip("@")
                worker_logger.info(
                    f"[batch-{batch_id}] Scraping @{handle} for {chain_name}"
                )
                tweets = collector._scrape_profile(
                    handle, hdl, chain_name, cutoff, page=page
                )
                all_tweets.extend(tweets)
                worker_logger.info(
                    f"[batch-{batch_id}] @{handle}: {len(tweets)} tweets"
                )
                time.sleep(random.randint(3, 7))
        except Exception as exc:
            worker_logger.error(f"[batch-{batch_id}] Error: {exc}")
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            collector._cleanup()

        return all_tweets

    def _scrape_profile(self, handle: str, hdl_cfg: dict, chain_name: str, cutoff: datetime, page=None) -> list[dict]:
        """Open a profile, scroll, extract tweets within time window.
        If page is provided, reuses it instead of creating a new page each time.
        """
        if not self._context:
            return []

        new_page = page is None
        if new_page:
            page = self._context.new_page()
        try:
            url = f"https://x.com/{handle}"
            logger.info(f"[twitter] Navigating {url}")
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            # Hard wait for React initial render + first article mount
            page.wait_for_timeout(random.randint(4000, 7000))
            # Detect and mitigate SPA stale DOM: force a soft reload if fewer than 2 articles
            articles = page.query_selector_all('article[data-testid="tweet"]')
            if len(articles) < 2:
                page.wait_for_timeout(random.randint(3000, 5000))
                page.reload(wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(random.randint(4000, 6000))
            # Allow X's background data fetch to complete
            page.wait_for_timeout(random.randint(2000, 4000))

            # Check for login wall / suspension
            body_text = (page.inner_text("body") or "").lower()
            if "sign in" in body_text and "x" in body_text[:500]:
                logger.warning(f"[twitter] @{handle} — login wall detected (no valid session)")
                return []
            if "suspended" in body_text or "account suspended" in body_text:
                logger.warning(f"[twitter] @{handle} — account suspended")
                return []

            tweets: list[dict] = []
            last_count = 0
            scrolls_no_new = 0
            max_scrolls = 20 if self.lookback_hours > 48 else 12

            for scroll in range(max_scrolls):
                batch = page.evaluate(EXTRACT_TWEETS_JS)
                if not batch:
                    time.sleep(random.randint(1000, 2000) / 1000)
                    continue

                fresh_in_batch = 0
                for t in batch:
                    ts_str = t.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    # Skip empty-text tweets unless they have media (signal that X suppressed text via JS)
                    if not t.get("text", "").strip() and not t.get("media_urls"):
                        continue
                    if ts < cutoff:
                        # Too old — but keep scrolling a bit more to be sure we didn't miss anything
                        scrolls_no_new += 1
                        if scrolls_no_new >= 3:
                            logger.info(f"[twitter] @{handle} — reached cutoff after {scroll} scrolls")
                            break
                        continue

                    # Enrich tweet metadata
                    t["chain"] = chain_name
                    t["account_handle"] = handle
                    t["account_role"] = "official" if hdl_cfg in self._accounts.get(chain_name, {}).get("official", []) else "contributor"
                    t["account_name"] = hdl_cfg.get("name", handle)
                    t["account_reliability"] = hdl_cfg.get("reliability", 0.75)
                    t["scraped_at"] = datetime.now(timezone.utc).isoformat()

                    # Deduplicate within this run
                    if not any(existing["tweet_id"] == t["tweet_id"] for existing in tweets):
                        tweets.append(t)
                        fresh_in_batch += 1

                if scrolls_no_new >= 3:
                    break

                if len(tweets) == last_count:
                    scrolls_no_new += 1
                else:
                    scrolls_no_new = 0
                last_count = len(tweets)

                if len(tweets) >= 100:
                    logger.info(f"[twitter] @{handle} — hit 100 tweet cap")
                    break

                page.evaluate(SCROLL_JS)
                page.wait_for_timeout(random.randint(2000, 4500))

            logger.info(f"[twitter] @{handle}: {len(tweets)} tweets within window")
            return tweets

        except Exception as e:
            logger.error(f"[twitter] Error scraping @{handle}: {e}")
            return []
        finally:
            if new_page:
                try:
                    page.close()
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Persistence — JSON + Markdown summaries for trending analysis
    # -----------------------------------------------------------------------
    def _persist_raw(self, tweets: list[dict]):
        """Save raw tweets to JSON (append history)."""
        if not tweets:
            return
        now = datetime.now(timezone.utc)
        file_name = f"tweets_{now.strftime('%Y%m%d_%H%M%S')}.json"
        path = RAW_OUT_DIR / file_name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)
        logger.info(f"[twitter] Raw tweets persisted: {path}")

        # Monthly rolling summary markdown (for human browsing)
        month_key = now.strftime("%Y-%m")
        summary_path = SUMMARY_OUT_DIR / f"twitter_summary_{month_key}.md"
        self._append_summary_md(summary_path, tweets, now)

    def _append_summary_md(self, path: Path, tweets: list[dict], now: datetime):
        """Append tweets to a monthly Markdown summary file."""
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

    def _persist_enriched(self, tweets: list[dict]):
        """Save enriched tweets (with semantic annotations) to JSON."""
        enriched = [t for t in tweets if t.get("semantic")]
        if not enriched:
            return
        now = datetime.now(timezone.utc)
        file_name = f"enriched_{now.strftime('%Y%m%d_%H%M%S')}.json"
        path = ENRICHED_OUT_DIR / file_name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, indent=2, ensure_ascii=False)
        logger.info(f"[twitter] {len(enriched)} enriched tweets persisted: {path}")

    # -----------------------------------------------------------------------
    # Convert tweets to pipeline event dicts
    # -----------------------------------------------------------------------
    def _tweets_to_events(self, tweets: list[dict]) -> list[dict]:
        """Transform tweets into chain-monitor event dicts."""
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

            # Build description
            if is_rt and original_author:
                description = f"@{handle} reposted @{original_author}: {text}"
            elif is_q and quoted_text:
                description = f"@{handle} quoted: {text} — Quoting: {quoted_text}"
            else:
                description = text

            # For retweets of official accounts → boost reliability to official level
            if is_rt and role == "contributor":
                # Check if original_author is an official account for this chain
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
                "semantic": t.get("semantic"),  # v0.2: pass LLM semantic result through
            }

            event = {
                "type": "twitter_post",
                "category": "NEWS",  # categorizer will re-assign
                "chain": chain,
                "source_name": f"Twitter (@{handle})",
                "source": "twitter",
                "description": description[:500],
                "evidence": evidence,
                "timestamp": ts or datetime.now(timezone.utc).isoformat(),
                "reliability": reliability,
                "has_official_source": role == "official" or reliability >= 0.95,
            }
            events.append(event)

        return events

    # -----------------------------------------------------------------------
    # For standalone script: expose raw collector without pipeline conversion
    # -----------------------------------------------------------------------
    def collect_raw(self) -> list[dict]:
        """Run collection and return raw tweets (no event conversion)."""
        all_tweets: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        if not self._accounts:
            return []

        self._start_browser()
        try:
            for chain_name, cfg in self._accounts.items():
                handles = cfg.get("official", []) + cfg.get("contributors", [])
                for hdl in handles:
                    handle = hdl["handle"].lstrip("@")
                    tweets = self._scrape_profile(handle, hdl, chain_name, cutoff)
                    all_tweets.extend(tweets)
                    time.sleep(random.randint(3, 7))
        finally:
            self._cleanup()

        self._persist_raw(all_tweets)
        return all_tweets
