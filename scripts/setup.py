#!/usr/bin/env python3
"""Interactive setup wizard for Chain Monitor v2.0 agent-native pipeline.

Generates .env interactively. No LLM required.

Usage:
    python3 scripts/setup.py
"""

import os
import sys
from pathlib import Path
from getpass import getpass


REPO_ROOT = Path(__file__).parent.parent


def prompt(msg: str, default: str = "") -> str:
    """Prompt for input with default value."""
    full = f"{msg} [{default}]: " if default else f"{msg}: "
    val = input(full).strip()
    return val or default


def prompt_bool(msg: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    val = input(f"{msg} [{default_str}]: ").strip().lower()
    if not val:
        return default
    return val.startswith("y")


def main():
    print("🔧 Chain Monitor v2.0 Setup Wizard (Agent-Native)")
    print("=" * 50)
    print("\n  No LLM setup required.")
    print("  Pipeline runs entirely within your agent via deterministic Python.\n")

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        print(f"\n⚠️  {env_path} already exists.")
        if not prompt_bool("Overwrite existing .env?"):
            print("Setup cancelled.")
            return 0

    # ── Data Source APIs (optional) ────────────────────────────────────────
    print("\n🔑 Data Source APIs (optional, press Enter to skip)")
    cryptorank = getpass("  CryptoRank API key: ") or ""
    coingecko = getpass("  CoinGecko API key: ") or ""
    youtube = getpass("  YouTube Data API key: ") or ""
    github = getpass("  GitHub token: ") or ""

    # ── Telegram ────────────────────────────────────────────────
    print("\n📬 Telegram Delivery (required):")
    tg_token = getpass("  Telegram bot token: ")
    tg_chat = prompt("  Telegram chat ID")

    # ── Optional settings ─────────────────────────────────────
    print("\n⚙️  Optional Settings")
    log_level = prompt("  Log level", "INFO")
    retention = prompt("  Data retention (days)", "90")

    # ── Build .env ────────────────────────────────────────────
    lines = [
        "# Chain Monitor v2.0 — Environment Variables",
        "# Fully agent-native: no LLM keys required",
        "",
    ]

    if cryptorank:
        lines.append(f"CRYPTORANK_API_KEY={cryptorank}")
    if coingecko:
        lines.append(f"COINGECKO_API_KEY={coingecko}")
    if youtube:
        lines.append(f"YOUTUBE_API_KEY={youtube}")
    if github:
        lines.append(f"GITHUB_TOKEN={github}")

    lines.extend([
        "",
        f"TELEGRAM_BOT_TOKEN={tg_token}",
        f"TELEGRAM_CHAT_ID={tg_chat}",
        "",
        f"LOG_LEVEL={log_level}",
        f"DATA_RETENTION_DAYS={retention}",
        "",
        "# Twitter settings",
        "TWITTER_LOOKBACK_HOURS=24",
        "TWITTER_THREAD_DEPTH=0",
    ])

    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n✅ Wrote {env_path}")

    # ── Reload env for validation ─────────────────────────────
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            os.environ[key] = val

    # ── Validate storage ──────────────────────────────────────
    print("\n📁 Checking storage...")
    for subdir in ("storage/events", "storage/health", "storage/narratives"):
        p = REPO_ROOT / subdir
        p.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {subdir}")

    # ── Validate Telegram ───────────────────────────────────────
    print("\n📬 Validating Telegram...")
    try:
        import requests
        resp = requests.get(
            f"https://api.telegram.org/bot{tg_token}/getMe",
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            bot_name = resp.json()["result"]["username"]
            print(f"  ✓ Bot connected: @{bot_name}")
        else:
            print(f"  ✗ Telegram validation failed: {resp.status_code}")
    except Exception as exc:
        print(f"  ✗ Telegram validation failed: {exc}")

    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("  1. python3 scripts/doctor.py")
    print("  2. python3 scripts/chain_monitor_cli.py digest --dry-run")
    print("  3. python3 main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
