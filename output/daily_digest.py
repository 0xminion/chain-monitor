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

        # Theme — show tech events first, not TVL data
        theme = self._detect_theme(signals)
        if theme:
            sections.extend(["🧠 Today's theme", theme, ""])

        # Critical
        if critical:
            sections.append("🔴 Critical (Score ≥10)")
            for s in sorted(critical, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s, show_reason=True))
                sections.append("")

        # High
        if high:
            sections.append("🟠 High (Score 8-9)")
            for s in sorted(high, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s, show_reason=True))
                sections.append("")

        # Notable
        if notable:
            sections.append("🟡 Notable (Score 6-7)")
            for s in sorted(notable, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s, show_reason=False))
                sections.append("")

        # Dev activity (tech events below notable threshold)
        dev_activity = [s for s in signals if s.category == "TECH_EVENT" and s.priority_score < 6]
        if dev_activity:
            sections.append("🔧 Dev activity")
            for s in sorted(dev_activity, key=lambda x: -x.priority_score)[:5]:
                sections.append(self._format_signal(s, show_reason=True))
                sections.append("")

        # No events
        if not critical and not high and not notable and not dev_activity:
            sections.append("— No high-priority events. Quiet day.")

        # Source Health
        if source_health:
            sections.extend(self._format_health(source_health))

        return "\n".join(sections)

    def should_send(self, signals: list[Signal]) -> bool:
        """Determine if digest should be sent (3+ events score ≥6)."""
        notable_count = sum(1 for s in signals if s.priority_score >= 6)
        return notable_count >= 3

    def _format_signal(self, signal: Signal, show_reason: bool = False) -> str:
        """Format a single signal for the digest."""
        impact_labels = {1: "Low", 2: "Moderate", 3: "Notable", 4: "High", 5: "Critical"}
        sources_str = ", ".join(set(a["source"] for a in signal.activity))
        rein_str = f" — {signal.source_count}x" if signal.source_count > 1 else ""

        chain = signal.chain.capitalize()
        desc = signal.description
        sources = sources_str

        lines = [
            f"• {chain}: {desc} [{sources}{rein_str}]",
        ]

        # Show "Why?" for high/critical signals
        if show_reason and signal.trader_context:
            lines.append(f"  Why: {signal.trader_context}")

        return "\n".join(lines)

    def _detect_theme(self, signals: list[Signal]) -> Optional[str]:
        """Detect the day's dominant theme — show tech events first, then other categories."""
        if not signals:
            return None

        # Priority: TECH_EVENT > RISK_ALERT > PARTNERSHIP > FINANCIAL > REGULATORY > VISIBILITY
        # TVL/financial is data noise — tech events and partnerships are the real news
        theme_priority = ["TECH_EVENT", "RISK_ALERT", "PARTNERSHIP", "REGULATORY", "VISIBILITY"]

        category_counts = {}
        for s in signals:
            category_counts[s.category] = category_counts.get(s.category, 0) + 1

        # Pick highest-priority category that has signals
        dominant = None
        for cat in theme_priority:
            if cat in category_counts:
                dominant = cat
                break

        if not dominant:
            # Fall back to most common if none of the priority categories
            dominant = max(category_counts, key=category_counts.get)

        dominant_signals = [s for s in signals if s.category == dominant]

        if dominant == "TECH_EVENT":
            items = []
            for s in dominant_signals[:5]:
                chain = s.chain.capitalize()
                desc = s.description.split("(")[0].strip()
                items.append(f"{chain} — {desc.lower()}")
            return "Protocol activity: " + "; ".join(items)

        elif dominant == "RISK_ALERT":
            chains = list(set(s.chain.capitalize() for s in dominant_signals[:3]))
            return f"Security incidents on {', '.join(chains)}. Check exposure."

        elif dominant == "PARTNERSHIP":
            items = []
            for s in dominant_signals[:5]:
                chain = s.chain.capitalize()
                desc = s.description.split("(")[0].strip()
                items.append(f"{chain} — {desc.lower()}")
            return "Ecosystem expansion: " + "; ".join(items)

        elif dominant == "REGULATORY":
            chains = list(set(s.chain.capitalize() for s in dominant_signals[:3]))
            return f"Regulatory activity affecting {', '.join(chains)}. Watch closely."

        elif dominant == "VISIBILITY":
            chains = list(set(s.chain.capitalize() for s in dominant_signals[:3]))
            return f"Visibility surge on {', '.join(chains)}."

        return None

    def _format_health(self, health: dict) -> list[str]:
        """Format source health summary."""
        lines = ["⚠️ Source health"]

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
