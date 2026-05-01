#!/usr/bin/env python3
"""Standalone Twitter collector — sequential, stable, resource-capped.

Collects from configured accounts, outputs raw JSON for the v2.0 digest bridge.

Modes (determined by --workers):
  --workers 2 (default): Spawn-based parallel (2 fresh processes).
                         Each worker gets its own browser. Capped at 5.
                         Each worker gets a fresh isolated process + browser.
                         Safer than fork but heavier. Capped to max 3 workers.

Resource caps:
  - Per-worker RAM watched; killed + restarted if >80% available.
  - Per-worker handle cap: max 20 handles before browser restart.
  - Between accounts: 3-7s random delay.
  - Each profile: max 12 scrolls, 100 tweets.

Cleanup guarantees:
  - After every account: page.evaluate('window.stop()') to kill pending reqs.
  - After every N handles: page.close() + new_page() (fresh JS context).
  - After batch: full browser shutdown + zombie Chrome kill.

Usage:
  python scripts/run_twitter_standalone.py --hours 24 --workers 1 --batches 1
  python scripts/run_twitter_standalone.py --hours 24 --workers 2 --batches 10
"""

import argparse
import json
import logging
import multiprocessing as mp
import os
import random
import signal
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collectors.twitter_collector import TwitterCollector

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("twitter-standalone")

# ——— Resource limits ————————————————————————————————————————————————————————
MAX_WORKERS = 5          # Hard cap regardless of CLI arg
BATCH_HANDLE_CAP = 20    # Restart browser every N handles within a worker
RAM_KILL_PCT = 80      # Kill worker if RAM usage exceeds this % of available
WORKER_TIMEOUT = 600   # Seconds before a worker is considered hung


# ——— Graceful shutdown ———————————————————————————————————————————————————————
def _setup_sigterm():
    """Register SIGTERM handler for clean teardown."""
    def _handler(signum, frame):
        logger.warning(f"Received signal {signum} — shutting down")
        sys.exit(128 + signum)
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


# ——— RAM monitor —————————————————————————————————————————————————————————————
def _ram_usage_pct() -> float:
    """Return current process RAM usage as % of system available."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    parts = line.split()
                    kb = int(parts[1])
                    total_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
                    used_gb = kb / (1024 ** 2)
                    return (used_gb / total_gb) * 100 if total_gb else 0
    except Exception:
        pass
    return 0.0


def _kill_zombie_chrome():
    """Kill any chrome/chromium processes in our FULL process tree (including orphans)."""
    try:
        import subprocess
        our_pid = os.getpid()
        # Build full PID tree from ps
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
        # Walk tree from our PID
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
                    os.kill(pid, 9)
                    logger.debug(f"Killed zombie chrome pid={pid}")
                except (ProcessLookupError, PermissionError):
                    pass
    except Exception:
        pass


def _kill_stale_chrome():
    """Pre-flight: kill any orphaned chrome/chromium processes from previous runs.

    Targets:
      - chrome with PPID=1 (re-parented to init)
      - chrome whose parent python process has been alive >30 minutes (stale worker)
    """
    try:
        import subprocess
        # Get PID→PPID→comm and PID→elapsed mapping
        ps_out = subprocess.run(
            ["ps", "-eo", "pid,ppid,comm,etime"],
            capture_output=True, text=True, check=False,
        )
        pid_to_info: dict[int, tuple[int, str, str]] = {}
        for line in ps_out.stdout.strip().split("\n")[1:]:
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    p, pp = int(parts[0]), int(parts[1])
                    comm = parts[2]
                    etime = parts[3]
                    pid_to_info[p] = (pp, comm, etime)
                except (ValueError, IndexError):
                    pass

        stale_parent_pids = set()
        for pid, (ppid, comm, etime) in pid_to_info.items():
            if ppid == 1 and comm == "python":
                # Parse etime: MM:SS or HH:MM:SS or DD-HH:MM:SS
                total_minutes = _parse_etime(etime)
                if total_minutes > 30:
                    stale_parent_pids.add(pid)

        killed = 0
        for pid, (ppid, comm, _) in pid_to_info.items():
            if "chrome" not in comm.lower():
                continue
            # Kill if orphaned to init, or parent is stale python
            if ppid == 1:
                stale = True
            elif ppid in stale_parent_pids:
                stale = True
            else:
                stale = False
            if stale:
                try:
                    os.kill(pid, 9)
                    killed += 1
                except (ProcessLookupError, PermissionError):
                    pass
        if killed:
            logger.warning(f"[twitter-standalone] Pre-flight killed {killed} stale chrome processes")
    except Exception:
        pass


def _parse_etime(etime: str) -> int:
    """Convert ps etime to total minutes."""
    try:
        # Formats: MM:SS, HH:MM:SS, DD-HH:MM:SS
        if "-" in etime:
            days, rest = etime.split("-")
            parts = rest.split(":")
        else:
            days = 0
            parts = etime.split(":")
        days = int(days) if isinstance(days, str) else days
        if len(parts) == 2:  # MM:SS
            mins, secs = int(parts[0]), int(parts[1])
            return days * 1440 + mins
        elif len(parts) == 3:  # HH:MM:SS
            hrs, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
            return days * 1440 + hrs * 60 + mins
    except (ValueError, IndexError):
        pass
    return 9999  # assume stale


# ——— Core worker —————————————————————————————————————————————————————————————
def run_batch(batch_id: int, handles: list[tuple], lookback_hours: int) -> list[dict]:
    """Worker: scrape a batch of handles, clean up aggressively per N handles.

    Each worker gets its own browser. Browser is restarted every BATCH_HANDLE_CAP
    handles to prevent JS heap / network leakage.
    """
    _setup_sigterm()
    worker_logger = logging.getLogger(f"twitter-batch-{batch_id}")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    collector: Optional[TwitterCollector] = None
    page = None
    all_raw: list[dict] = []
    handle_idx = 0

    def _start_browser():
        nonlocal collector, page
        if collector:
            try:
                collector._cleanup()  # kills own chrome tree via full ps-tree walk
            except Exception:
                pass
        # Also nuke any stale chrome from previous crashed runs (orphaned PPID=1)
        _kill_stale_chrome()
        time.sleep(1)
        collector = TwitterCollector(standalone_mode=True, lookback_hours=lookback_hours)
        collector._start_browser()
        page = collector._context.new_page() if collector._context else None
        worker_logger.info(f"[batch-{batch_id}] Browser started (page={page is not None})")

    try:
        _start_browser()

        for chain_name, hcfg in handles:
            handle = hcfg["handle"].lstrip("@")

            # Restart browser every N handles
            if handle_idx > 0 and handle_idx % BATCH_HANDLE_CAP == 0:
                worker_logger.info(
                    f"[batch-{batch_id}] Restarting browser after {handle_idx} handles (RAM cap)"
                )
                _start_browser()

            # RAM guard
            ram = _ram_usage_pct()
            if ram > RAM_KILL_PCT:
                worker_logger.warning(
                    f"[batch-{batch_id}] RAM {ram:.0f}% — restarting browser mid-batch"
                )
                _start_browser()

            try:
                worker_logger.info(f"[batch-{batch_id}] Scraping @{handle} for {chain_name}")
                tweets = collector._scrape_profile(handle, hcfg, chain_name, cutoff, page=page)
                all_raw.extend(tweets)
                worker_logger.info(f"[batch-{batch_id}] @{handle}: {len(tweets)} tweets")

                # Aggressive page reset to free JS heap
                if page:
                    try:
                        page.evaluate("window.stop()")
                        page.evaluate("document.body.innerHTML = ''")
                    except Exception:
                        pass

            except Exception as e:
                worker_logger.error(f"[batch-{batch_id}] @{handle} error: {e}")
                # Fatal browser errors — restart
                if "browser" in str(e).lower() or "context" in str(e).lower():
                    worker_logger.warning(f"[batch-{batch_id}] Restarting browser after error")
                    _start_browser()

            # Rate limit
            time.sleep(random.randint(3, 7))
            handle_idx += 1

    except Exception as e:
        worker_logger.error(f"[batch-{batch_id}] Worker fatal: {e}")
        traceback.print_exc()
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass
        if collector:
            try:
                collector._cleanup()
            except Exception:
                pass
        # Aggressive final cleanup: kill every chrome descendant of this worker
        _kill_zombie_chrome()

    # Persist batch immediately so partial work isn't lost
    if all_raw:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = REPO_ROOT / "storage" / "twitter" / "raw"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"tweets_{ts}_batch{batch_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(all_raw, f, indent=2, ensure_ascii=False)
        worker_logger.info(f"[batch-{batch_id}] Persisted {len(all_raw)} to {path}")

    return all_raw


# ——— Sequential mode (default) ———————————————————————————————————————————————
def run_sequential(handles: list[tuple], lookback_hours: int) -> list[dict]:
    """Sequential collection: one browser, one page, no fork/thread overhead."""
    logger.info(f"Sequential mode: {len(handles)} handles, 1 worker")
    return run_batch(batch_id=0, handles=handles, lookback_hours=lookback_hours)


# ——— Parallel mode (spawn) ———————————————————————————————————————————————————
def run_parallel_spawn(handles: list[tuple], lookback_hours: int, workers: int, num_batches: int) -> list[dict]:
    """Parallel via multiprocessing spawn context.

    Each worker is a completely fresh process — no inherited Playwright state,
    no Camoufox/asyncio corruption.
    """
    workers = min(workers, MAX_WORKERS)
    batch_size = max(1, len(handles) // num_batches)
    batches = [handles[i:i + batch_size] for i in range(0, len(handles), batch_size)]
    logger.info(f"Spawn mode: {len(handles)} handles → {len(batches)} batches, {workers} workers")

    # Use spawn context to avoid forked-state inheritance
    ctx = mp.get_context("spawn")
    all_tweets: list[dict] = []

    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
        futures = {
            executor.submit(run_batch, i, batch, lookback_hours): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_id = futures[future]
            try:
                # Hard timeout per worker
                result = future.result(timeout=WORKER_TIMEOUT)
                all_tweets.extend(result)
                logger.info(f"Batch-{batch_id} completed: {len(result)} tweets")
            except Exception as exc:
                logger.error(f"Batch-{batch_id} failed: {exc}")

    return all_tweets


# ——— Merge & digest helpers ——————————————————————————————————————————————————
def _merge_batches() -> list[dict]:
    """Merge all batch files into a single deduped list."""
    raw_dir = REPO_ROOT / "storage" / "twitter" / "raw"
    all_tweets: list[dict] = []
    seen = set()
    for path in sorted(raw_dir.glob("tweets_*_batch*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            batch = data if isinstance(data, list) else data.get("tweets", [])
            for t in batch:
                tid = t.get("tweet_id") or t.get("url", "")
                if tid and tid not in seen:
                    seen.add(tid)
                    all_tweets.append(t)
        except Exception as e:
            logger.warning(f"Merge error for {path}: {e}")
    return all_tweets


def _build_digest(tweets: list[dict]) -> str:
    """Build plain-text digest from raw tweets."""
    lines = ["# Twitter Summary — Standalone Collection", ""]
    by_chain = {}
    for t in tweets:
        by_chain.setdefault(t.get("chain", "unknown"), []).append(t)
    for chain, c_tweets in sorted(by_chain.items()):
        lines.append(f"\n## {chain}")
        for tw in c_tweets[:7]:
            handle = tw.get("account_handle", "")
            role = tw.get("account_role", "")
            text = tw.get("text", "")
            url = tw.get("url", "")
            ts = tw.get("timestamp", "")[:16].replace("T", " ")
            badges = []
            if tw.get("is_retweet"):
                badges.append("🔁")
            if tw.get("is_quote_tweet"):
                badges.append("💬")
            badge_str = f" [{' '.join(badges)}]" if badges else ""
            display_text = text.replace("@", "").replace("https://", "").replace("http://", "")
            lines.append(f"- **@{handle}** ({role}){badge_str} — [{ts}]({url})")
            lines.append(f"  > {display_text[:220]}{'...' if len(display_text) > 220 else ''}")
    return "\n".join(lines)


# ——— Main ——————————————————————————————————————————————————————————————————————
def main():
    _setup_sigterm()
    parser = argparse.ArgumentParser(description="Standalone Twitter collector")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours")
    parser.add_argument("--chains", type=str, default="", help="Comma-separated chain names")
    parser.add_argument("--telegram", action="store_true", help="Send digest via TelegramSender")
    parser.add_argument("--json-only", action="store_true", help="Skip Telegram, save files only")
    parser.add_argument("--dry-run", action="store_true", help="Test auth without saving")
    parser.add_argument("--workers", type=int, default=2, help="Parallel workers (1=sequential, max 5)")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches")
    args = parser.parse_args()

    hours = args.hours
    chains_filter = [c.strip() for c in args.chains.split(",")] if args.chains else []
    workers = max(1, min(args.workers, MAX_WORKERS))
    num_batches = max(1, args.batches)

    logger.info("=" * 60)
    logger.info("Twitter Standalone Collector v2.1")
    logger.info(f"Lookback: {hours}h | Workers: {workers} | Batches: {num_batches}")
    logger.info("=" * 60)

    # ★★★ Pre-flight: slaughter orphaned Chrome from previous crashed runs ★★★
    _kill_stale_chrome()

    # Load accounts
    import yaml
    config_path = REPO_ROOT / "config" / "twitter_accounts.yaml"
    if not config_path.exists():
        logger.error("No twitter_accounts.yaml found")
        return
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    accounts = data.get("twitter_accounts", {})
    if not accounts:
        logger.error("No chains configured")
        return

    if chains_filter:
        accounts = {k: v for k, v in accounts.items() if k in chains_filter}
        if not accounts:
            logger.error(f"No matching chains: {chains_filter}")
            return

    flat_handles = []
    for chain_name, cfg in accounts.items():
        for h in cfg.get("official", []) + cfg.get("contributors", []):
            flat_handles.append((chain_name, h))
    if not flat_handles:
        logger.error("No handles found")
        return
    logger.info(f"Total handles: {len(flat_handles)}")

    # Dry run
    if args.dry_run:
        logger.info("DRY RUN — testing auth...")
        try:
            collector = TwitterCollector(standalone_mode=True, lookback_hours=hours)
            collector._start_browser()
            page = collector._context.new_page()
            test_url = "https://x.com/solana"
            page.goto(test_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(4)
            articles = page.query_selector_all('article[data-testid="tweet"]')
            logger.info(f"DRY RUN success: {len(articles)} articles on {test_url}")
            page.close()
            collector._cleanup()
            _kill_zombie_chrome()
            logger.info("DRY RUN complete")
        except Exception as e:
            logger.error(f"DRY RUN failed: {e}")
            traceback.print_exc()
        return

    # Run collection
    t0 = time.perf_counter()
    if workers == 1:
        all_tweets = run_sequential(flat_handles, hours)
    else:
        all_tweets = run_parallel_spawn(flat_handles, hours, workers, num_batches)
    elapsed = time.perf_counter() - t0

    logger.info(f"=== Collection done in {elapsed:.1f}s | Raw tweets: {len(all_tweets)} ===")

    # Merge + persist
    if all_tweets:
        logger.info(f"Total raw tweets: {len(all_tweets)}")
        # Also merge any persisted batch files for dedup
        merged = _merge_batches()
        logger.info(f"Merged unique tweets: {len(merged)}")

        digest = _build_digest(merged)
        summary_dir = REPO_ROOT / "storage" / "twitter" / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        json_path = summary_dir / f"standalone_summary_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"tweets": merged, "digest": digest}, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON summary: {json_path}")

        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        md_path = summary_dir / f"twitter_summary_{month_key}.md"
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(f"\n## Standalone Run @ {ts}\n\n")
            f.write(digest + "\n")
        logger.info(f"Markdown appended: {md_path}")

        if args.telegram and not args.json_only:
            try:
                from output.telegram_sender import TelegramSender
                sender = TelegramSender()
                sent = sender.send(digest[:4000])
                logger.info(f"Telegram: {sent}")
            except Exception as e:
                logger.error(f"Telegram failed: {e}")
    else:
        logger.warning("No tweets collected")


if __name__ == "__main__":
    main()
