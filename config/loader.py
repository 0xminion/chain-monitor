"""Configuration loader — loads YAML configs and env vars."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / ".env")

CONFIG_DIR = Path(__file__).parent


def load_yaml(filename: str) -> dict:
    """Load a YAML config file."""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


# Singleton configs
_chains = None
_baselines = None
_narratives = None
_sources = None
_twitter_accounts = None
_pipeline = None


def get_chains() -> dict:
    global _chains
    if _chains is None:
        _chains = load_yaml("chains.yaml")
    return _chains


def get_baselines() -> dict:
    global _baselines
    if _baselines is None:
        _baselines = load_yaml("baselines.yaml")
    return _baselines


def get_narratives() -> dict:
    global _narratives
    if _narratives is None:
        _narratives = load_yaml("narratives.yaml")
    return _narratives


def get_sources() -> dict:
    global _sources
    if _sources is None:
        _sources = load_yaml("sources.yaml")
    return _sources


def get_twitter_accounts() -> dict:
    """Get Twitter account configuration."""
    global _twitter_accounts
    if _twitter_accounts is None:
        _twitter_accounts = load_yaml("twitter_accounts.yaml")
    return _twitter_accounts


def get_pipeline_config() -> dict:
    """Get pipeline configuration with typed defaults."""
    global _pipeline
    if _pipeline is None:
        try:
            _pipeline = load_yaml("pipeline.yaml")
        except FileNotFoundError:
            _pipeline = {}
    return _pipeline


def get_pipeline_value(key_path: str, default):
    """Get a nested value from pipeline config via dot-path.

    Examples:
        get_pipeline_value("pipeline.max_concurrent_collectors", 4)
        get_pipeline_value("twitter.max_workers", 15)
    """
    cfg = get_pipeline_config()
    parts = key_path.split(".")
    for part in parts:
        if isinstance(cfg, dict) and part in cfg:
            cfg = cfg[part]
        else:
            return default
    return default if cfg is None else cfg


def get_chain(chain_name: str) -> Optional[dict]:
    """Get config for a specific chain."""
    return get_chains().get(chain_name)


def get_baseline(chain_name: str) -> Optional[dict]:
    """Get baseline thresholds for a specific chain."""
    return get_baselines().get(chain_name)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable."""
    return os.environ.get(key, default)


def get_active_chains() -> list[str]:
    """Get list of all active chain names."""
    return list(get_chains().keys())


def get_chains_by_tier(tier: int) -> list[str]:
    """Get chains filtered by tier."""
    return [name for name, cfg in get_chains().items() if cfg.get("tier") == tier]


def get_chains_by_category(category: str) -> list[str]:
    """Get chains filtered by category."""
    return [name for name, cfg in get_chains().items() if cfg.get("category") == category]


def reload_configs():
    """Force reload all configs (useful for dynamic updates)."""
    global _chains, _baselines, _narratives, _sources, _twitter_accounts, _pipeline
    _chains = None
    _baselines = None
    _narratives = None
    _sources = None
    _twitter_accounts = None
    _pipeline = None
