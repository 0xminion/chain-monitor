#!/usr/bin/env python3
"""Chain Monitor — Management CLI.

All-in-one management tool for setup, health checks, chain config,
digest execution, and cron scheduling.

Usage:
    python3 scripts/chain_monitor_cli.py setup
    python3 scripts/chain_monitor_cli.py doctor
    python3 scripts/chain_monitor_cli.py chains list
    python3 scripts/chain_monitor_cli.py chains add monad --category high_tps --tier 2
    python3 scripts/chain_monitor_cli.py chains remove monad
    python3 scripts/chain_monitor_cli.py digest --dry-run
    python3 scripts/chain_monitor_cli.py cron install --hour 9
    python3 scripts/chain_monitor_cli.py cron remove
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

__version__ = "0.1.0"

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml
from config.loader import get_active_chains, get_chain, load_yaml


def cmd_setup(args) -> int:
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "setup.py")]).returncode


def cmd_doctor(args) -> int:
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "doctor.py")]).returncode


def cmd_chains_list(args) -> int:
    chains = sorted(get_active_chains())
    print(f"Monitored chains ({len(chains)}):")
    for c in chains:
        cfg = get_chain(c) or {}
        tier = cfg.get("tier", "?")
        cat = cfg.get("category", "?")
        slug = cfg.get("defillama_slug") or cfg.get("coingecko_id") or "—"
        print(f"  • {c:<15} tier={tier}  category={cat:<18}  slug={slug}")
    return 0


def cmd_chains_add(args) -> int:
    chains_path = REPO_ROOT / "config" / "chains.yaml"
    config = load_yaml("chains.yaml")
    if args.name in config:
        print(f"Chain '{args.name}' already exists.")
        return 1

    config[args.name] = {
        "category": args.category or "others",
        "tier": args.tier or 3,
        "coingecko_id": args.coingecko_id,
        "defillama_slug": args.defillama_slug,
        "github_repos": args.github_repos.split(",") if args.github_repos else [],
        "blog_rss": args.blog_rss,
        "youtube_channel": args.youtube_channel,
        "status_page": None,
        "governance_forum": None,
    }

    with open(chains_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"✅ Added chain '{args.name}' to chains.yaml")
    print("  Next: edit config/chains.yaml to add feeds and sources")
    return 0


def cmd_chains_remove(args) -> int:
    chains_path = REPO_ROOT / "config" / "chains.yaml"
    config = load_yaml("chains.yaml")
    if args.name not in config:
        print(f"Chain '{args.name}' not found.")
        return 1
    del config[args.name]
    with open(chains_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"✅ Removed chain '{args.name}' from chains.yaml")
    return 0


def cmd_digest(args) -> int:
    """Run the full pipeline."""
    import asyncio
    from main import run_pipeline

    if args.dry_run:
        print("🧪 Dry run — disabling Telegram send...")
        os.environ["TELEGRAM_BOT_TOKEN"] = ""

    ctx = asyncio.run(run_pipeline())

    stats = ctx.stats()
    print("\n📊 Pipeline Stats")
    print(f"  Raw events:       {stats['raw_events']}")
    print(f"  Unique events:    {stats['unique_events']}")
    print(f"  Signals scored:   {stats['signals']}")
    print(f"  Chains analyzed:  {stats['chain_digests']}")
    print(f"  Active chains:    {stats['chains_with_activity']}")
    print(f"  Digest length:    {stats['digest_length']} chars")

    if ctx.chain_digests:
        top = sorted(ctx.chain_digests, key=lambda d: -d.priority_score)[0]
        print(f"\n🔝 Top chain: {top.chain.upper()} (score {top.priority_score})")
        print(f"   Topic: {top.dominant_topic}")

    if args.preview:
        print(f"\n{'─'*40}\n{ctx.final_digest[:1200]}\n{'─'*40}")

    if args.json:
        out = {
            "stats": stats,
            "digests": [
                {
                    "chain": d.chain,
                    "priority_score": d.priority_score,
                    "dominant_topic": d.dominant_topic,
                    "summary": d.summary,
                    "confidence": d.confidence,
                    "event_count": d.event_count,
                }
                for d in ctx.chain_digests
            ],
        }
        dump_path = (
            REPO_ROOT / "storage" / "health"
            / f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dump_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n📝 JSON dump: {dump_path}")

    return 0


def cmd_cron_install(args) -> int:
    hour = args.hour if args.hour is not None else 9
    repo_path = str(REPO_ROOT.resolve())
    python = sys.executable
    cmdline = f"{python} {repo_path}/main.py >> {repo_path}/storage/health/cron.log 2>&1"
    cron_entry = f"0 {hour} * * * cd {repo_path} && {cmdline}\n"

    # Remove old entries and append new
    try:
        result = subprocess.run(
            "crontab -l 2>/dev/null | grep -v 'chain-monitor' || true",
            shell=True, capture_output=True, text=True, check=False,
        )
        existing = result.stdout or ""
        new_crontab = existing.rstrip("\n") + "\n" + cron_entry + "\n"
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            capture_output=True,
        )
        if proc.returncode == 0:
            print(f"✅ Cron job installed: daily at {hour}:00 UTC")
            print(f"   Command: {cron_entry.strip()}")
            return 0
        print(f"✗ crontab install failed: {proc.stderr}")
        return 1
    except Exception as exc:
        print(f"✗ Cron install error: {exc}")
        return 1


def cmd_cron_remove(args) -> int:
    try:
        result = subprocess.run(
            "crontab -l 2>/dev/null | grep -v 'chain-monitor' || true",
            shell=True, capture_output=True, text=True, check=False,
        )
        new = result.stdout or ""
        proc = subprocess.run(["crontab", "-"], input=new, text=True, capture_output=True)
        if proc.returncode == 0:
            print("✅ Chain Monitor cron job removed")
            return 0
        print(f"✗ crontab update failed: {proc.stderr}")
        return 1
    except Exception as exc:
        print(f"✗ Cron remove error: {exc}")
        return 1


def cmd_config_edit(args) -> int:
    config_dir = REPO_ROOT / "config"
    print(f"Config directory: {config_dir}")
    for p in sorted(config_dir.glob("*.yaml")):
        print(f"  • {p.name}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="chain-monitor",
        description="Chain Monitor v0.1.0 — crypto chain intelligence pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    # setup
    subparsers.add_parser("setup", help="Interactive setup wizard")

    # doctor
    subparsers.add_parser("doctor", help="Health check + auto-fix")

    # chains
    chains_p = subparsers.add_parser("chains", help="Manage monitored chains")
    chains_sub = chains_p.add_subparsers(dest="chains_cmd")
    chains_sub.add_parser("list", help="List all monitored chains")

    add_p = chains_sub.add_parser("add", help="Add a new chain")
    add_p.add_argument("name")
    add_p.add_argument("--category", default="others")
    add_p.add_argument("--tier", type=int, default=3)
    add_p.add_argument("--coingecko-id")
    add_p.add_argument("--defillama-slug")
    add_p.add_argument("--github-repos")
    add_p.add_argument("--blog-rss")
    add_p.add_argument("--youtube-channel")

    rm_p = chains_sub.add_parser("remove", help="Remove a chain")
    rm_p.add_argument("name")

    # digest
    digest_p = subparsers.add_parser("digest", help="Run the full digest pipeline")
    digest_p.add_argument("--dry-run", action="store_true", help="Run without sending Telegram")
    digest_p.add_argument("--preview", action="store_true", help="Print digest to stdout")
    digest_p.add_argument("--json", action="store_true", help="Dump JSON output to storage/health/")

    # cron
    cron_p = subparsers.add_parser("cron", help="Manage cron scheduling")
    cron_sub = cron_p.add_subparsers(dest="cron_cmd")
    install_p = cron_sub.add_parser("install", help="Install daily cron job")
    install_p.add_argument("--hour", type=int, default=9)
    cron_sub.add_parser("remove", help="Remove daily cron job")

    # config
    subparsers.add_parser("config", help="Show config files")

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "version":
        print(f"Chain Monitor v{__version__}")
        return 0
    if args.command == "config":
        return cmd_config_edit(args)

    dispatch = {
        ("setup", None): cmd_setup,
        ("doctor", None): cmd_doctor,
        ("chains", "list"): cmd_chains_list,
        ("chains", "add"): cmd_chains_add,
        ("chains", "remove"): cmd_chains_remove,
        ("digest", None): cmd_digest,
        ("cron", "install"): cmd_cron_install,
        ("cron", "remove"): cmd_cron_remove,
    }

    key = (args.command, getattr(args, "chains_cmd", None) or getattr(args, "cron_cmd", None))
    fn = dispatch.get(key)
    if not fn:
        parser.print_help()
        return 1
    rc = fn(args) or 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
