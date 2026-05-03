---
name: chain-monitor-twitter-auth
description: "Twitter/X authentication strategy for Chain Monitor — Chrome profile, cookies.json, rate-limit management"
category: data-collection
author: 0xminion
---

# Chain Monitor — Twitter/X Authentication

## Overview

The Twitter collector requires an authenticated X.com session to scrape profiles. It uses a **tiered auth strategy**.

## Auth Tiers

| Tier | Source | Contains Auth? | Priority |
|------|--------|---------------|----------|
| 1 | Chrome/Chromium/Firefox persistent profile | ✅ `auth_token`, `ct0`, `twid` | Highest |
| 2 | `storage/twitter/cookies.json` (Playwright `storage_state`) | ✅ If exported from auth session | Fallback |
| 3 | Plain Chromium | ❌ Guest mode | Last resort |

## Flatpak Chrome (Steam Deck)

On SteamOS, Chrome is installed as a Flatpak. The profile lives at:

```
~/.var/app/com.google.Chrome/config/google-chrome/Default
```

The profile root (returned by `_find_chrome_profile()`) must be:

```
~/.var/app/com.google.Chrome/config/google-chrome
```

**Critical bug fixed:** `_find_chrome_profile()` previously returned `c.parent.parent` → `~/.var/app/com.google.Chrome/config`, which is **one directory too high**. Chromium couldn't find `Default/` and silently created a fresh anonymous profile. Always return `c.parent`.

## Profile Copy Strategy

Each worker needs an **independent copy** of the profile because:
1. Multiple Chromiums can't share the same `Cookies` SQLite DB (lock contention → corrupted reads)
2. X.com rate-limits per Chromium instance

**Current approach:**
1. Main process copies profile once → `/tmp/chain_monitor_profile_*/profile`
2. Each worker copies from that clean snapshot → `/tmp/profile_batch_N_*/profile`
3. Each worker launches Chromium against its own copy
4. Workers clean up their copies when done
5. Main process cleans up the shared snapshot when done

## Worker Rate Limiting

**10 parallel workers hit X.com from a single IP → rate limiting.** Symptoms:
- "3 empty scrolls, stopping"
- 0 tweets for most handles
- Some batches return tweets (e.g., batch-3: 7 tweets)

**Recommended:** `TWITTER_MAX_WORKERS=2-3` (Steam Deck, 16 GB RAM). Each Chromium ~200–400 MB.

## How to Refresh Auth

Run `scripts/export_cookies.py` to export the Flatpak Chrome cookie DB into Playwright-compatible `storage_state`:

```bash
cd /home/deck/chain-monitor
python3 scripts/export_cookies.py
```

## Verification

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('$HOME/.var/app/com.google.Chrome/config/google-chrome/Default/Cookies')
rows = db.execute(\"SELECT name FROM cookies WHERE host_key LIKE '%%.x.com'\").fetchall()
auth = [r[0] for r in rows if r[0] in ('auth_token', 'ct0', 'twid')]
print('Auth cookies:', auth)
"
```

Must see: `['auth_token', 'ct0', 'twid']`

## Scripts

- `scripts/export_cookies.py` — Export Chrome cookies to `storage/twitter/cookies.json`
- `scripts/test_twitter_auth.py` — Test a single handle

## Pitfalls

1. **Profile path bug:** `c.parent.parent` vs `c.parent` → broken auth
2. **SQLite lock:** Multiple workers reading same `Cookies` DB → corrupted results
3. **Rate limiting:** >3 workers from one IP → X.com serves empty pages
4. **OOM:** 10 Chromiums × 300MB = 3GB on a 16GB Steam Deck
