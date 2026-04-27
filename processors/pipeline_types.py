"""Pipeline data types — contracts between all pipeline stages.

v2.0: Defines RawEvent, ChainDigest, and PipelineContext for the
6-stage chain-centric pipeline.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RawEvent:
    """A raw collected event before any processing."""

    chain: str
    category: str
    subcategory: str
    description: str
    source: str
    reliability: float
    evidence: dict = field(default_factory=dict)
    raw_url: Optional[str] = None
    published_at: Optional[datetime] = None
    semantic: Optional[dict] = None

    @property
    def fingerprint(self) -> str:
        """Deterministic content fingerprint for O(1) dedup lookups.

        Uses SHA-256 truncation for collision resistance at reasonable length.
        """
        raw = f"{self.chain}:{self.category}:{self.raw_url or ''}:{self.description[:200]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    @classmethod
    def from_collector_dict(cls, d: dict, source_name: str) -> "RawEvent":
        """Construct a RawEvent from a legacy collector dict.

        This adapter lets us migrate incrementally without rewriting every
        collector today.
        """
        evidence = d.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {"raw": str(evidence)}

        url: Optional[str] = None
        for key in ("link", "html_url", "pr_url", "feed_url", "url"):
            val = evidence.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                url = val
                break

        published: Optional[datetime] = None
        for key in ("published_at", "published"):
            val = evidence.get(key)
            if val:
                try:
                    published = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        chain_val = d.get("chain")
        chain_str = str(chain_val).lower().strip() if chain_val is not None else "unknown"

        reliability_val = d.get("reliability", 0.7)
        try:
            reliability_float = float(reliability_val) if reliability_val is not None else 0.7
        except (ValueError, TypeError):
            reliability_float = 0.7

        return cls(
            chain=chain_str,
            category=str(d.get("category", "TECH_EVENT")),
            subcategory=str(d.get("subcategory", "general")),
            description=str(d.get("description", "")),
            source=str(d.get("source", source_name)),
            reliability=reliability_float,
            evidence=evidence,
            raw_url=url,
            published_at=published,
            semantic=d.get("semantic"),
        )


@dataclass
class KeyEvent:
    """Single merged event observation within a chain digest."""

    topic: str
    category: str
    sources: list[str] = field(default_factory=list)
    priority: int = 0
    confidence: float = 0.0
    detail: str = ""
    why_it_matters: str = ""


@dataclass
class ChainDigest:
    """Per-chain LLM-synthesized summary."""

    chain: str
    chain_tier: int
    chain_category: str
    summary: str
    key_events: list[dict] = field(default_factory=list)
    priority_score: int = 0
    dominant_topic: str = ""
    sources_seen: int = 0
    event_count: int = 0
    confidence: float = 0.0

    def has_significant_activity(self) -> bool:
        """True if this chain has anything worth reporting."""
        return self.priority_score >= 3 or self.event_count >= 2 or self.key_events


@dataclass
class PipelineContext:
    """Shared mutable context passed through pipeline stages."""

    raw_events: list[RawEvent] = field(default_factory=list)
    unique_events: list[RawEvent] = field(default_factory=list)
    signals: list = field(default_factory=list)
    chain_digests: list[ChainDigest] = field(default_factory=list)
    final_digest: str = ""
    health: dict = field(default_factory=dict)
    feed_health: dict = field(default_factory=dict)
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def stats(self) -> dict:
        """Return pipeline statistics."""
        return {
            "raw_events": len(self.raw_events),
            "unique_events": len(self.unique_events),
            "signals": len(self.signals),
            "chain_digests": len(self.chain_digests),
            "chains_with_activity": sum(1 for d in self.chain_digests if d.has_significant_activity()),
            "digest_length": len(self.final_digest),
        }
