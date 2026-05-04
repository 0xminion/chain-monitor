#!/home/deck/chain-monitor/.venv/bin/python3
"""Camoufox-powered Twitter/X worker — batch handles with context reuse.

One browser context scrapes multiple handles sequentially.

Usage:
    python3 twitter_worker.py --handles Base,BuildOnBase --chain base --lookback 24 --max-scrolls 5 --cookies cookies.json

Outputs newline-delimited JSON.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DISPLAY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(processName)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("tw-worker")

EXTRACT_JS = r"""
() => {
    const tweets = [];
    const seen = new Set();
    document.querySelectorAll('article[data-testid="tweet"]').forEach(art => {
        const links = art.querySelectorAll('a[href*="/status/"]');
        let tweetId = '', tweetUrl = '';
        for (const a of links) {
            const href = a.getAttribute('href');
            const m = href.match(/\/status\/(\d+)/);
            if (m) { tweetId = m[1]; tweetUrl = 'https://x.com' + href.split('?')[0]; break; }
        }
        if (!tweetId || seen.has(tweetId)) return;
        seen.add(tweetId);
        const timeEl = art.querySelector('time');
        const timestamp = timeEl ? timeEl.getAttribute('datetime') : '';
        const allTextDivs = Array.from(art.querySelectorAll('div[data-testid="tweetText"]'));
        let text = '';
        for (const td of allTextDivs) { const c = td.innerText.trim(); if (c.length > text.length) text = c; }
        const imgs = Array.from(art.querySelectorAll('img')).map(i=>i.src).filter(s=>s && !s.includes('profile_images'));
        // Detect RT / Quote via labels or social context
        const socialCtx = art.querySelector('[data-testid="socialContext"]');
        const label = (socialCtx && socialCtx.innerText) || '';
        const isRetweet = label.toLowerCase().includes('reposted') || label.toLowerCase().includes('retweeted');
        const isQuote = !!art.querySelector('[role="link"][href*="/status/"] div[data-testid="tweetText"]') && !isRetweet;
        let originalAuthor = '';
        if (isRetweet || isQuote) {
            const quoted = art.querySelector('div[role="link"] a[role="link"][href^="/"]');
            if (quoted) {
                const h = quoted.getAttribute('href');
                const hm = h.match(/^\/([^\/]+)/);
                if (hm) originalAuthor = hm[1];
            }
        }
        const quotedEls = art.querySelectorAll('div[role="link"] div[data-testid="tweetText"]');
        let quotedText = '';
        for (const qd of quotedEls) { const c = qd.innerText.trim(); if (c.length > quotedText.length) quotedText = c; }
        // Engagement
        const likeBtn = art.querySelector('button[data-testid="like"], button[aria-label*="Like"]');
        let likes = 0;
        if (likeBtn) {
            const val = likeBtn.innerText.replace(/[^0-9]/g, '');
            if (val) likes = parseInt(val, 10);
        }
        const rtBtn = art.querySelector('button[data-testid="retweet"], button[aria-label*="Repost"]');
        let retweets = 0;
        if (rtBtn) {
            const val = rtBtn.innerText.replace(/[^0-9]/g, '');
            if (val) retweets = parseInt(val, 10);
        }
        tweets.push({
            tweet_id: tweetId,
            url: tweetUrl,
            timestamp,
            text,
            media_urls: imgs.slice(0,4),
            is_retweet: isRetweet,
            is_quote_tweet: isQuote,
            original_author: originalAuthor,
            quoted_text: quotedText,
            likes,
            retweets,
        });
    });
    return tweets;
}
"""


def _scrape_one_handle(page, handle: str, cutoff: datetime, max_scrolls: int) -> list[dict]:
    url = f"https://x.com/{handle}"
    logger.info(f"@{handle} navigating {url}")

    for attempt in range(2):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as exc:
            logger.warning(f"@{handle} navigate failed (attempt {attempt + 1}): {exc}")
            if attempt == 0:
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                continue
            return []

        # Progressive wait — cap at 8 rounds (~20s) to avoid hanging on dead handles
        found = False
        for wait_round in range(8):
            page.wait_for_timeout(random.randint(1500, 2500))
            articles = page.query_selector_all('article[data-testid="tweet"]')
            logger.info(f"@{handle} — wait round {wait_round}: {len(articles)} articles")
            if len(articles) >= 2:
                found = True
                break
        if not found:
            # No articles after reasonable wait — likely login wall / dead account.
            # Don't waste time on reload; just abort.
            body = (page.inner_text("body") or "").lower()
            if "sign in" in body and "x" in body[:500]:
                logger.warning(f"@{handle} — login wall")
            elif "suspended" in body or "account suspended" in body:
                logger.warning(f"@{handle} — suspended")
            elif "something went wrong" in body:
                logger.warning(f"@{handle} — 'Something went wrong'")
                if attempt == 0:
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass
                    continue
            else:
                logger.warning(f"@{handle} — no tweets found after waiting")
            return []

        # Detect blocking
        body = (page.inner_text("body") or "").lower()
        if "sign in" in body and "x" in body[:500]:
            logger.warning(f"@{handle} — login wall")
            return []
        if "suspended" in body or "account suspended" in body:
            logger.warning(f"@{handle} — suspended")
            return []
        if "something went wrong" in body:
            logger.warning(f"@{handle} — 'Something went wrong'")
            if attempt == 0:
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                continue
            return []

        break  # nav succeeded

    seen_ids: set[str] = set()
    empty_scrolls = 0
    tweets: list[dict] = []

    for scroll in range(max_scrolls):
        batch = page.evaluate(EXTRACT_JS)
        if not batch:
            empty_scrolls += 1
            if empty_scrolls >= 3:
                logger.info(f"@{handle} — 3 empty scrolls, stopping")
                break
            continue

        fresh = 0
        for t in batch:
            ts_str = t.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if not t.get("text", "").strip() and not t.get("media_urls"):
                continue
            if ts < cutoff:
                continue
            tid = t.get("tweet_id")
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            t["scraped_at"] = datetime.now(timezone.utc).isoformat()
            tweets.append(t)
            fresh += 1

        if fresh > 0:
            empty_scrolls = 0
        else:
            empty_scrolls += 1
            if empty_scrolls >= 3:
                logger.info(f"@{handle} — cutoff after {scroll} scrolls ({len(tweets)} tweets)")
                break

        if scroll < max_scrolls - 1:
            page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight); }")
            page.wait_for_timeout(random.randint(2500, 5000))

    logger.info(f"@{handle}: {len(tweets)} tweets")
    return tweets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handles", required=True, help="Comma-separated handles")
    parser.add_argument("--chains", default=None, help="Comma-separated chain names (1:1 with handles)")
    parser.add_argument("--cookies")
    parser.add_argument("--lookback", type=int, default=24)
    parser.add_argument("--max-scrolls", type=int, default=8)
    args = parser.parse_args()

    handles = [h.strip().lstrip("@") for h in args.handles.split(",") if h.strip()]
    if args.chains:
        chains = [c.strip() for c in args.chains.split(",")]
    else:
        chains = ["unknown"] * len(handles)
    # Pad if shorter
    while len(chains) < len(handles):
        chains.append("unknown")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.lookback)
    cookies_path = args.cookies

    import camoufox
    from playwright.sync_api import sync_playwright

    total_tweets = 0
    sp = None
    browser = None
    context = None
    page = None

    try:
        sp = sync_playwright().start()
        browser = camoufox.NewBrowser(
            sp,
            headless=True,
            window=(1366, 768),
            block_webgl=False,
            humanize=True,
            os=("windows",),
        )

        ctx_kwargs = {}
        if cookies_path and Path(cookies_path).exists():
            ctx_kwargs["storage_state"] = cookies_path
            logger.info(f"Using storage_state from {cookies_path}")
        else:
            logger.warning("No cookies found — may hit login wall")

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        for idx, handle in enumerate(handles):
            tweets = _scrape_one_handle(page, handle, cutoff, args.max_scrolls)
            chain = chains[idx] if idx < len(chains) else "unknown"
            for t in tweets:
                t["chain"] = chain
                t["account_handle"] = handle
                print(json.dumps(t, ensure_ascii=False))
            total_tweets += len(tweets)
            sys.stdout.flush()

            if handle != handles[-1]:
                time.sleep(random.uniform(3.0, 7.0))

    except Exception as exc:
        logger.error(f"Worker error: {exc}")
    finally:
        for obj in (page, context, browser, sp):
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass

    logger.info(f"Worker complete: {total_tweets} tweets from {len(handles)} handles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
