#!/usr/bin/env python3
"""Export Chrome persistent profile cookies to Playwright storage_state JSON.

Run this after logging into x.com in Chrome to refresh the collector's auth cookies.
"""
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

FLATPAK_PROFILE = Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome"
NATIVE_PROFILE = Path.home() / ".config" / "google-chrome"
OUTPUT = Path("/home/deck/chain-monitor/storage/twitter/cookies.json")


def _find_profile() -> Path | None:
    """Find first valid Chrome profile directory."""
    for base in (FLATPAK_PROFILE, NATIVE_PROFILE):
        if base.exists():
            defaults = list(base.glob("Default" if (base / "Default").exists() else "*"))
            for d in defaults:
                cookies_db = d / "Cookies"
                if cookies_db.exists() and cookies_db.stat().st_size > 512:
                    return d
    return None


def _copy_unlocked(src: Path) -> Path:
    """Copy Chrome profile to temp to avoid lock contention with running Chrome."""
    tmpdir = Path(tempfile.mkdtemp(prefix="chrome_export_"))
    copied = tmpdir / "Default"
    shutil.copytree(src, copied)
    return copied


def _extract_x_cookies(cookies_db: Path) -> list[dict]:
    """Extract all .x.com / .twitter.com cookies from Chrome SQLite."""
    rows = []
    try:
        conn = sqlite3.connect(str(cookies_db))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT name, value, host_key, path, expires_utc, is_secure, "
            "       is_httponly, samesite FROM cookies "
            "WHERE host_key LIKE '%x.com' OR host_key LIKE '%twitter.com'"
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        print(f"ERROR reading cookies DB: {exc}")
        return []

    cookies = []
    for r in rows:
        # Chrome epoch: microseconds since 1601-01-01 UTC
        # → seconds for Playwright (Unix epoch)
        expires = -1
        if r["expires_utc"] and r["expires_utc"] != 0:
            expires = (r["expires_utc"] - 11644473600000000) / 1_000_000

        same_map = {0: "None", 1: "Lax", 2: "Strict", -1: "Lax"}
        same = same_map.get(r["samesite"], "Lax")

        cookies.append({
            "name": r["name"],
            "value": r["value"],
            "domain": r["host_key"],
            "path": r["path"],
            "expires": expires,
            "httpOnly": bool(r["is_httponly"]),
            "secure": bool(r["is_secure"]),
            "sameSite": same,
        })
    return cookies


def main():
    profile = _find_profile()
    if not profile:
        print("ERROR: No Chrome profile found (checked Flatpak + native)")
        exit(1)

    print(f"Found Chrome profile: {profile}")
    copied = _copy_unlocked(profile)
    print(f"Copied to temp: {copied}")

    cookies = _extract_x_cookies(copied / "Cookies")
    if not cookies:
        print("WARNING: No x.com/twitter.com cookies found — are you logged in?")
        exit(1)

    auth_cookies = [c["name"] for c in cookies if c["name"] in ("auth_token", "ct0", "twid")]
    print(f"Total cookies extracted: {len(cookies)}")
    print(f"Auth cookies: {auth_cookies}")

    storage_state = {"cookies": cookies, "origins": []}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(storage_state, f, indent=2)
    print(f"Saved storage_state → {OUTPUT} ({OUTPUT.stat().st_size} bytes)")

    # Cleanup
    shutil.rmtree(copied.parent)


if __name__ == "__main__":
    main()
