"""LLM cache — file-backed cache with TTL for semantic enrichment results."""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "storage" / "llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL_HOURS = int(os.environ.get("LLM_CACHE_TTL_HOURS", "168"))


def _make_key(inputs: dict) -> str:
    """Deterministic cache key from input dict."""
    # Sort keys for determinism
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _is_expired(mtime: float, ttl_hours: int) -> bool:
    """Check if cache entry is older than TTL."""
    if ttl_hours <= 0:
        return True
    now = time.time()
    max_age = ttl_hours * 3600
    return (now - mtime) >= max_age


class LLMCache:
    """File-backed cache for LLM semantic enrichment results."""

    def __init__(self, ttl_hours: Optional[int] = None):
        self.ttl_hours = ttl_hours if ttl_hours is not None else DEFAULT_TTL_HOURS

    def get(self, chain: str, text: str, author: str, is_retweet: bool, quoted_text: str = "") -> Optional[dict]:
        """Check cache for existing enrichment result."""
        key = _make_key({
            "chain": chain,
            "text": text,
            "author": author,
            "is_retweet": is_retweet,
            "quoted_text": quoted_text,
        })
        path = _cache_path(key)
        if not path.exists():
            return None

        try:
            mtime = path.stat().st_mtime
            if _is_expired(mtime, self.ttl_hours):
                logger.debug(f"Cache expired for key {key[:8]}...")
                return None

            with open(path, encoding="utf-8") as f:
                cached = json.load(f)

            # Validate structure
            required = {"category", "subcategory", "confidence", "reasoning", "is_noise"}
            if not required.issubset(cached.keys()):
                logger.warning(f"Cache entry missing required keys: {path}")
                return None

            logger.debug(f"Cache HIT for key {key[:8]}...")
            return cached

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read cache {path}: {e}")
            return None

    def set(self, chain: str, text: str, author: str, is_retweet: bool, quoted_text: str, result: dict) -> None:
        """Store enrichment result in cache."""
        key = _make_key({
            "chain": chain,
            "text": text,
            "author": author,
            "is_retweet": is_retweet,
            "quoted_text": quoted_text,
        })
        path = _cache_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.debug(f"Cache SET for key {key[:8]}...")
        except OSError as e:
            logger.warning(f"Failed to write cache {path}: {e}")

    def clear_expired(self) -> int:
        """Remove expired cache entries. Returns count removed."""
        removed = 0
        for path in CACHE_DIR.glob("*.json"):
            try:
                mtime = path.stat().st_mtime
                if _is_expired(mtime, self.ttl_hours):
                    path.unlink()
                    removed += 1
            except OSError:
                pass
        if removed:
            logger.info(f"Cleared {removed} expired LLM cache entries")
        return removed

    def get_stats(self) -> dict:
        """Return cache statistics."""
        files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(p.stat().st_size for p in files)
        expired = sum(1 for p in files if _is_expired(p.stat().st_mtime, self.ttl_hours))
        return {
            "total_entries": len(files),
            "expired_entries": expired,
            "total_size_bytes": total_size,
            "ttl_hours": self.ttl_hours,
            "cache_dir": str(CACHE_DIR),
        }
