"""Signal data model — the core data structure for all events."""


import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class ActivityEntry:
    """Single reinforcement activity entry."""
    timestamp: str
    source: str
    reliability: float
    evidence: str
    cluster: Optional[str] = None


@dataclass
class Signal:
    """A discrete event detected about a chain."""
    id: str
    chain: str
    category: str  # TECH_EVENT, PARTNERSHIP, REGULATORY, RISK_ALERT, VISIBILITY, FINANCIAL
    description: str
    trader_context: str = ""
    impact: int = 1  # 1-5
    urgency: int = 1  # 1-3
    priority_score: int | None = None
    detected_at: str = ""
    reinforced_at: str = ""
    source_count: int = 1
    composite_confidence: float = 0.0
    has_official_source: bool = False
    secondary_tags: list = field(default_factory=list)
    activity: list = field(default_factory=list)

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()
        if not self.reinforced_at:
            self.reinforced_at = self.detected_at
        if self.priority_score is None:
            self.priority_score = self.impact * self.urgency
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate deterministic ID from chain + category + description."""
        raw = f"{self.chain}:{self.category}:{self.description[:100]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def add_activity(self, source: str, reliability: float, evidence: str):
        """Add reinforcement activity."""
        entry = ActivityEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            reliability=reliability,
            evidence=evidence,
        )
        self.activity.append(asdict(entry))
        self.source_count = len(self.activity)
        self.reinforced_at = entry.timestamp
        self._recalculate_confidence()

    def _recalculate_confidence(self):
        """Recalculate composite confidence based on source count."""
        if not self.activity:
            return
        max_reliability = max(a["reliability"] for a in self.activity)
        multiplier = 1.0
        if self.source_count >= 3:
            multiplier = 1.25
        elif self.source_count >= 2:
            multiplier = 1.15
        if self.has_official_source:
            multiplier += 0.05
        self.composite_confidence = min(0.95, max_reliability * multiplier)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["priority_score"] = self.impact * self.urgency
        return d

    def to_markdown(self) -> str:
        """Format signal for markdown digest."""
        impact_labels = {1: "LOW", 2: "MODERATE", 3: "NOTABLE", 4: "HIGH", 5: "CRITICAL"}
        sources_str = ", ".join(set(a["source"] for a in self.activity))
        rein_str = f" — {self.source_count}x" if self.source_count > 1 else ""

        lines = [
            f"• {self.chain.capitalize()}: {self.description} [{sources_str}{rein_str}]",
            f"  {self.category} | Impact: {self.impact} ({impact_labels.get(self.impact, '?')}) | Urgency: {self.urgency}",
        ]
        if self.trader_context:
            lines.append(f"  → So what: {self.trader_context}")
        return "\n".join(lines)

    @staticmethod
    def generate_id(chain: str, category: str, description: str) -> str:
        raw = f"{chain}:{category}:{description[:100]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
