"""Twitter/X collector — monitors official chain accounts and key contributors.

Uses Playwright with existing browser session cookies for authentication.
Anti-detection strategy: Camoufox -> Chromium persistent context -> standard Chromium.

v0.2.0 — async refactor: ONE browser context + concurrent pages (semaphore).
   Replaces ProcessPoolExecutor (15 separate browser processes) with asyncio.

Author: 0xminion
"""

import json
import logging
import os
import random
import subprocess
import time
import asyncio
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
TWITTER_ACCOUNTS_PATH = REPO_ROOT / "config" / "twitter_accounts.yaml"
RAW_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "raw"
SUMMARY_OUT_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"

# ---------------------------------------------------------------------------
# NEW: Enrichment output dir (v0.1.0)
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
                 max_workers: int | None = None, num_batches: int | None = None):
        """
        Args:
            standalone_mode: If True, skips dedup/reinforcement and writes to own JSON.
            lookback_hours: Override global default. Defaults to env TWITTER_LOOKBACK_HOURS or config.
            max_workers: Number of concurrent Playwright pages (NOT processes). Defaults to config (15).
            num_batches: Ignored in v0.2.0+ (kept for API compat).
        """
        super().__init__(name="twitter")
        self.standalone_mode = standalone_mode
        self.lookback_hours = lookback_hours or int(get_env("TWITTER_LOOKBACK_HOURS",
                                                           str(get_pipeline_value("twitter.lookback_hours", 24))))
        self.max_workers = int(get_env("TWITTER_MAX_WORKERS",
                                       str(max_workers if max_workers is not None else get_pipeline_value("twitter.max_workers", 15))))
        # num_batches kept for API compat but unused in v0.2.0+
        self.num_batches = int(get_env("TWITTER_NUM_BATCHES",
                                       str(num_batches if num_batches is not None else get_pipeline_value("twitter.num_batches", 10))))
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
    # Browser lifecycle — kept for backward compat; collect() now uses async
    # -----------------------------------------------------------------------
    def _start_browser(self):
        """Launch browser with best available anti-detection strategy."""
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        # --- Tier 1: Camoufox (anti-detect) -----------------
        try:
            from camoufox.sync_api import Camoufox
            logger.info("[twitter] Using Camoufox (anti-detect)")
            self._browser = Camoufox(headless=True).__enter__()
            self._context = self._browser
            return
        except Exception as e:
            logger.info(f"[twitter] Camoufox failed ({e}), trying Chromium persistent context")

        # --- Tier 2: Chromium persistent context with user profile ---
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

        # --- Tier 3: Plain Chromium + storage state ---------------
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

    # =====================================================================
    # ASYNC BROWSER LIFECYCLE (v0.2.0+)
    # =====================================================================
    async def _start_browser_async(self):
        """Launch async browser with best available anti-detection strategy."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # --- Tier 1: Camoufox (anti-detect) -----------------
        try:
            # Note: camoufox async API may not exist; fall through to plain Chromium
            from camoufox.async_api import Camoufox
            logger.info("[twitter] Using Camoufox (anti-detect)")
            self._browser = Camoufox(headless=True).__enter__()
            self._context = self._browser
            return
        except Exception as e:
            logger.info(f"[twitter] Camoufox async not available ({e}), trying Chromium persistent context")

        # --- Tier 2: Chromium persistent context with user profile ---
        profile_path = self._find_chrome_profile()
        if profile_path:
            try:
                logger.info(f"[twitter] Using Chromium persistent profile: {profile_path}")
                self._context = await self._playwright.chromium.launch_persistent_context(
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

        # --- Tier 3: Plain Chromium + storage state ---------------
        storage_state = self._find_storage_state()
        ss = storage_state if storage_state else None
        if ss:
            logger.info(f"[twitter] Using Chromium with storage_state: {ss}")
        else:
            logger.info("[twitter] Using plain Chromium (no cookies — may hit login wall)")

        self._browser = await self._playwright.chromium.launch(
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
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            storage_state=ss,
        )

    async def _cleanup_async(self):
        """Close async browser resources and clean up any orphaned Chrome processes."""
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
                await asyncio.sleep(0.5)

        # Graceful Playwright cleanup
        try:
            if self._context and hasattr(self._context, "close"):
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser and hasattr(self._browser, "close"):
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

    # =====================================================================
    # ASYNC COLLECTION (v0.2.0+)
    # =====================================================================
    async def collect_async(self) -> list[dict]:
        """Run Twitter collection with async concurrent pages.

        Launches ONE browser context, then scrapes all handles concurrently
        using up to `max_workers` pages (controlled by semaphore).
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

        sem = asyncio.Semaphore(self.max_workers)
        all_tweets: list[dict] = []
        start_time = time.time()
        hard_deadline = start_time + 600  # 10 min total

        try:
            await self._start_browser_async()

            coros = [
                self._scrape_handle_async(chain_name, hdl, cutoff, sem)
                for chain_name, hdl in all_handles
            ]

            # Process results as they complete
            pending = set(asyncio.create_task(c) for c in coros)
            while pending:
                done, pending = await asyncio.wait(
                    pending, timeout=5.0, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    try:
                        tweets = task.result()
                        all_tweets.extend(tweets)
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        logger.error(f"[twitter] Handle scrape failed: {exc}")

                if time.time() > hard_deadline:
                    logger.error(f"[twitter] HARD DEADLINE ({600}s) — cancelling remaining")
                    for task in pending:
                        task.cancel()
                    break

        except Exception as exc:
            logger.error(f"[twitter] Async collection failed: {exc}")
        finally:
            await self._cleanup_async()

        logger.info(f"[twitter] Total tweets collected: {len(all_tweets)}")
        if all_tweets:
            self.health.mark_success()

        self._persist_raw(all_tweets)
        events = self._tweets_to_events(all_tweets)
        return events

    async def _scrape_handle_async(
        self,
        chain_name: str,
        hdl_cfg: dict,
        cutoff: datetime,
        sem: asyncio.Semaphore,
    ) -> list[dict]:
        """Scrape a single Twitter handle under a semaphore (one page)."""
        async with sem:
            handle = hdl_cfg["handle"].lstrip("@")
            return await self._scrape_profile_async(handle, hdl_cfg, chain_name, cutoff)

    def collect(self) -> list[dict]:
        """Sync entry point — delegates to collect_async."""
        return asyncio.run(self.collect_async())

    async def collect_raw_async(self) -> list[dict]:
        """Run collection and return raw tweets (no event conversion)."""
        all_tweets: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        if not self._accounts:
            return []

        sem = asyncio.Semaphore(self.max_workers)
        try:
            await self._start_browser_async()
            coros = [
                self._scrape_handle_async(chain_name, hdl, cutoff, sem)
                for chain_name, cfg in self._accounts.items()
                for hdl in cfg.get("official", []) + cfg.get("contributors", [])
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_tweets.extend(r)
        finally:
            await self._cleanup_async()

        self._persist_raw(all_tweets)
        return all_tweets

    def collect_raw(self) -> list[dict]:
        """Sync wrapper for collect_raw_async."""
        return asyncio.run(self.collect_raw_async())

    async def _scrape_profile_async(
        self,
        handle: str,
        hdl_cfg: dict,
        chain_name: str,
        cutoff: datetime,
    ) -> list[dict]:
        """Two-phase scrape: quick sniff (6-8s) then full scroll only if recent activity.

        Phase 1 — Quick sniff: load page, check newest tweet timestamp. If too old,
        bail immediately (~6s total) instead of scrolling 12 times.
        Phase 2 — Full scroll: only if Phase 1 finds recent tweets in window.
        """
        if not self._context:
            return []

        page = await self._context.new_page()
        try:
            url = f"https://x.com/{handle}"
            t0 = time.time()
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3500)  # Hydration wait (reduced for sniff)

            # Check for login wall / suspension
            body_text = (await page.inner_text("body") or "").lower()
            if "sign in" in body_text and "x" in body_text[:500]:
                logger.warning(f"[twitter] @{handle} — login wall detected (no valid session)")
                return []
            if "suspended" in body_text or "account suspended" in body_text:
                logger.warning(f"[twitter] @{handle} — account suspended")
                return []

            # ── PHASE 1: Quick sniff — grab timestamps of visible tweets ──
            timestamps_js = """() => {
                const times = document.querySelectorAll('article[data-testid="tweet"] time');
                return Array.from(times).map(t => t.getAttribute('datetime')).filter(Boolean);
            }"""
            ts_list = await page.evaluate(timestamps_js)
            newest_ts = None
            for ts_str in ts_list:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if newest_ts is None or ts > newest_ts:
                        newest_ts = ts
                except ValueError:
                    continue

            # If newest visible tweet is older than cutoff → no need to scroll
            if newest_ts is not None and newest_ts < cutoff:
                logger.info(f"[twitter] @{handle} — reached cutoff after 0 scrolls")
                return []

            # If no timestamps found at all, try one reload then give up
            if newest_ts is None:
                await page.wait_for_timeout(3000)
                ts_list = await page.evaluate(timestamps_js)
                for ts_str in ts_list:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if newest_ts is None or ts > newest_ts:
                            newest_ts = ts
                    except ValueError:
                        continue
                if newest_ts is None or newest_ts < cutoff:
                    logger.info(f"[twitter] @{handle} — no recent tweets after reload")
                    return []

            # ── PHASE 2: Full scroll-extract only if Phase 1 found recent tweets ──
            tweets: list[dict] = []
            last_count = 0
            scrolls_no_new = 0
            max_scrolls = 8 if self.lookback_hours > 48 else 5  # Reduced from 12

            # First batch already on page from Phase 1; use JS to extract full data
            batch = await page.evaluate(EXTRACT_TWEETS_JS)
            if batch:
                for t in batch:
                    ts_str = t.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if not t.get("text", "").strip() and not t.get("media_urls"):
                        continue
                    if ts < cutoff:
                        scrolls_no_new += 1
                        continue
                    # Enrich
                    t["chain"] = chain_name
                    t["account_handle"] = handle
                    t["account_role"] = "official" if hdl_cfg in self._accounts.get(chain_name, {}).get("official", []) else "contributor"
                    t["account_name"] = hdl_cfg.get("name", handle)
                    t["account_reliability"] = hdl_cfg.get("reliability", 0.75)
                    t["scraped_at"] = datetime.now(timezone.utc).isoformat()
                    if not any(existing["tweet_id"] == t["tweet_id"] for existing in tweets):
                        tweets.append(t)
                if scrolls_no_new >= 3:
                    logger.info(f"[twitter] @{handle}: {len(tweets)} tweets within window")
                    return tweets
                scrolls_no_new = 0

            last_count = len(tweets)

            for scroll in range(max_scrolls):
                await page.evaluate(SCROLL_JS)
                await page.wait_for_timeout(random.randint(1500, 3000))  # faster scroll
                batch = await page.evaluate(EXTRACT_TWEETS_JS)
                if not batch:
                    await asyncio.sleep(random.randint(500, 1000) / 1000)
                    continue

                fresh_in_batch = 0
                for t in batch:
                    ts_str = t.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if not t.get("text", "").strip() and not t.get("media_urls"):
                        continue
                    if ts < cutoff:
                        scrolls_no_new += 1
                        if scrolls_no_new >= 3:
                            logger.info(f"[twitter] @{handle} — reached cutoff after {scroll} scrolls")
                            break
                        continue
                    t["chain"] = chain_name
                    t["account_handle"] = handle
                    t["account_role"] = "official" if hdl_cfg in self._accounts.get(chain_name, {}).get("official", []) else "contributor"
                    t["account_name"] = hdl_cfg.get("name", handle)
                    t["account_reliability"] = hdl_cfg.get("reliability", 0.75)
                    t["scraped_at"] = datetime.now(timezone.utc).isoformat()
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

            elapsed = time.time() - t0
            logger.info(f"[twitter] @{handle}: {len(tweets)} tweets within window ({elapsed:.1f}s)")
            return tweets

        except Exception as e:
            logger.error(f"[twitter] Error scraping @{handle}: {e}")
            return []
        finally:
            try:
                await page.close()
            except Exception:
                pass

    def _scrape_profile(self, handle: str, hdl_cfg: dict, chain_name: str, cutoff: datetime, page=None) -> list[dict]:
        """DEPRECATED: Sync wrapper for backward compat. Prefer _scrape_profile_async."""
        return asyncio.run(self._scrape_profile_async(handle, hdl_cfg, chain_name, cutoff))

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
                "semantic": t.get("semantic"),  # pass semantic result through
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
