"""Daily digest formatter — generates the daily Telegram digest."""

import logging
from datetime import datetime, timezone
from typing import Optional

from config.loader import get_chains
from processors.signal import Signal

logger = logging.getLogger(__name__)


class DailyDigestFormatter:
    """Formats signals into a daily Telegram digest."""

    def format(self, signals: list[Signal], source_health: dict = None, upcoming: list = None) -> str:
        """Format signals into daily digest text."""
        now = datetime.now(timezone.utc).strftime("%b %d, %Y")

        # Group by priority
        critical = [s for s in signals if s.priority_score >= 10]
        high = [s for s in signals if 8 <= s.priority_score < 10]
        notable = [s for s in signals if 6 <= s.priority_score < 8]

        sections = [
            f"📊 Chain Monitor — {now}",
            "",
        ]

        # Today's Theme
        theme = self._detect_theme(signals)
        if theme:
            sections.extend(["🧠 TODAY'S THEME", theme, ""])

        # Critical
        if critical:
            sections.append("🔴 CRITICAL (Score ≥10)")
            for s in sorted(critical, key=lambda x: -x.priority_score):
                sections.append(s.to_telegram())
                sections.append("")

        # High
        if high:
            sections.append("🟠 HIGH (Score 8-9)")
            for s in sorted(high, key=lambda x: -x.priority_score):
                sections.append(s.to_telegram())
                sections.append("")

        # Notable
        if notable:
            sections.append("🟡 NOTABLE (Score 6-7)")
            for s in sorted(notable, key=lambda x: -x.priority_score):
                sections.append(s.to_telegram())
                sections.append("")

        # No events
        if not critical and not high and not notable:
            sections.append("— No high-priority events today. Quiet day.")

        # Source Health
        if source_health:
            sections.extend(self._format_health(source_health))

        return "\n".join(sections)

    def should_send(self, signals: list[Signal]) -> bool:
        """Determine if digest should be sent (3+ events score ≥6)."""
        notable_count = sum(1 for s in signals if s.priority_score >= 6)
        return notable_count >= 3

    def _detect_theme(self, signals: list[Signal]) -> Optional[str]:
        """Detect the day's dominant theme."""
        if not signals:
            return None

        category_counts = {}
        for s in signals:
            category_counts[s.category] = category_counts.get(s.category, 0) + 1

        if not category_counts:
            return None

        dominant = max(category_counts, key=category_counts.get)
        chain_counts = {}
        for s in signals:
            if s.category == dominant:
                chain_counts[s.chain] = chain_counts.get(s.chain, 0) + 1

        top_chains = sorted(chain_counts, key=chain_counts.get, reverse=True)[:3]
        chain_str = ", ".join(c.capitalize() for c in top_chains)

        themes = {
            "TECH_EVENT": f"Protocol upgrades across {chain_str}. Building mode.",
            "FINANCIAL": f"Capital movements on {chain_str}. Money is flowing.",
            "PARTNERSHIP": f"Ecosystem expansion on {chain_str}. Partnerships forming.",
            "RISK_ALERT": f"Security incidents on {chain_str}. Check exposure.",
            "REGULATORY": f"Regulatory activity affecting {chain_str}. Watch closely.",
            "VISIBILITY": f"Visibility surge on {chain_str}. Marketing/hype mode.",
        }

        return themes.get(dominant, f"{dominant} activity across {chain_str}.")

    def _format_health(self, health: dict) -> list[str]:
        """Format source health summary."""
        lines = ["⚠️ Source Health"]

        # Normalize statuses: "ok" → "healthy", "error"/"down" → "down"
        def _norm(status: str) -> str:
            s = status.lower().strip()
            if s in ("healthy", "ok", "up"):
                return "healthy"
            if s in ("degraded", "slow", "partial"):
                return "degraded"
            return "down"

        healthy = sum(1 for h in health.values() if _norm(h.get("status", "")) == "healthy")
        degraded = sum(1 for h in health.values() if _norm(h.get("status", "")) == "degraded")
        down = sum(1 for h in health.values() if _norm(h.get("status", "")) == "down")
        total = len(health)

        lines.append(f"  Healthy: {healthy}/{total} | Degraded: {degraded} | Down: {down}")

        issues = [
            (name, h) for name, h in health.items()
            if _norm(h.get("status", "")) != "healthy"
        ]
        if issues:
            details = []
            for name, h in issues[:3]:
                details.append(f"{name} {h.get('status', 'unknown')} ({h.get('failures_24h', 0)} failures)")
            lines.append(f"  [{', '.join(details)}]")

        lines.append("")
        return lines
