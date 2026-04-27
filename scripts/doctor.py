#!/usr/bin/env python3
"""Chain Monitor — Health check and auto-fix doctor.

Checks .env, Python deps, LLM connectivity, storage dirs, Telegram bot.
Attempts automated fixes where safe.

Usage:
    python3 scripts/doctor.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def check_env() -> list[tuple[str, bool, str]]:
    """Check .env and key variables. Returns list of (check_name, ok, message)."""
    results = []
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        results.append(("env_file", False, ".env missing — run: python3 scripts/setup.py"))
        return results

    content = env_path.read_text()
    required_keys = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "LLM_MODEL",
    ]
    for key in required_keys:
        if f"{key}=" not in content:
            results.append((key, False, f"{key} not configured in .env"))
        elif f"{key}=" in content and (f"{key}=***" in content or f"{key}=your_" in content):
            results.append((key, False, f"{key} has placeholder value"))
        else:
            results.append((key, True, f"{key} configured"))
    return results


def check_python_deps() -> list[tuple[str, bool, str]]:
    """Check required Python packages."""
    results = []
    required = [
        ("requests", "requests"),
        ("PyYAML", "yaml"),
        ("aiohttp", "aiohttp"),
        ("feedparser", "feedparser"),
        ("python-dotenv", "dotenv"),
        ("filelock", "filelock"),
    ]
    for pkg_name, import_name in required:
        try:
            __import__(import_name)
            results.append((f"pkg:{pkg_name}", True, f"{pkg_name} installed"))
        except ImportError:
            results.append((f"pkg:{pkg_name}", False, f"Missing {pkg_name} — run: pip install -r requirements.txt"))
    return results


def check_llm() -> list[tuple[str, bool, str]]:
    """Check LLM connectivity."""
    results = []
    from config.loader import get_env
    provider = get_env("LLM_PROVIDER", "ollama")

    if provider != "ollama":
        results.append(("llm_provider", True, f"Provider={provider}, skipping Ollama check"))
        return results

    host = get_env("OLLAMA_HOST", "http://localhost:11434")
    try:
        import requests
        resp = requests.get(f"{host}/api/tags", timeout=5)
        if resp.status_code != 200:
            results.append(("llm_connect", False, f"Ollama returned HTTP {resp.status_code}"))
            return results

        data = resp.json()
        models = {m.get("name", "") for m in data.get("models", [])}
        model = get_env("LLM_MODEL", "")
        fallback = get_env("LLM_FALLBACK_MODEL", "")

        if model:
            if model in models:
                results.append(("llm_primary", True, f"Model '{model}' available"))
            else:
                results.append(("llm_primary", False, f"Model '{model}' not pulled — run: ollama pull {model}"))
        if fallback:
            if fallback in models:
                results.append(("llm_fallback", True, f"Fallback '{fallback}' available"))
            else:
                results.append(("llm_fallback", False, f"Fallback '{fallback}' not pulled — run: ollama pull {fallback}"))
    except requests.exceptions.ConnectionError:
        results.append(("llm_connect", False, f"Cannot connect to Ollama at {host} — is it running?"))
    except Exception as exc:
        results.append(("llm_connect", False, f"LLM check error: {exc}"))
    return results


def check_storage() -> list[tuple[str, bool, str]]:
    """Check storage directories exist and are writable."""
    results = []
    for subdir in ("storage/events", "storage/health", "storage/narratives"):
        p = REPO_ROOT / subdir
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
                results.append((f"dir:{subdir}", True, f"Created {subdir}"))
            except Exception as exc:
                results.append((f"dir:{subdir}", False, f"Cannot create {subdir}: {exc}"))
        elif not os.access(p, os.W_OK):
            results.append((f"dir:{subdir}", False, f"{subdir} is not writable"))
        else:
            results.append((f"dir:{subdir}", True, f"{subdir} OK"))
    return results


def check_telegram() -> list[tuple[str, bool, str]]:
    """Check Telegram credentials."""
    results = []
    from config.loader import get_env
    token = get_env("TELEGRAM_BOT_TOKEN")
    if not token or token.startswith("your_"):
        results.append(("telegram_token", False, "TELEGRAM_BOT_TOKEN not set"))
        return results

    try:
        import requests
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                results.append(("telegram_api", True, f"Bot: @{data['result']['username']}"))
            else:
                results.append(("telegram_api", False, f"getMe error: {data}"))
        elif resp.status_code == 401:
            results.append(("telegram_api", False, "Telegram token invalid (401)"))
        else:
            results.append(("telegram_api", False, f"Telegram check returned {resp.status_code}"))
    except Exception as exc:
        results.append(("telegram_api", False, f"Telegram check failed: {exc}"))
    return results


def check_config_files() -> list[tuple[str, bool, str]]:
    """Check required YAML configs exist."""
    results = []
    for fname in ("chains.yaml", "sources.yaml", "baselines.yaml", "narratives.yaml"):
        p = REPO_ROOT / "config" / fname
        if p.exists():
            results.append((f"cfg:{fname}", True, f"{fname} OK"))
        else:
            results.append((f"cfg:{fname}", False, f"{fname} MISSING"))
    return results


def _run_checks() -> list[tuple[str, bool, str]]:
    """Run all check groups and flatten."""
    results = []
    for fn in (check_env, check_python_deps, check_llm, check_storage, check_telegram, check_config_files):
        results.extend(fn())
    return results


def main():
    print("🏥 Chain Monitor Doctor")
    print("=" * 50)

    results = _run_checks()
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)

    for name, ok, msg in results:
        prefix = "✓" if ok else "✗"
        print(f"  {prefix} {msg}")

    print(f"\n{'='*50}")
    print(f"Result: {passed}/{total} checks passed")
    if passed == total:
        print("✅ All checks passed. Chain Monitor is healthy.")
        return 0
    else:
        print("⚠️  Some checks failed. Review messages above and fix.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
