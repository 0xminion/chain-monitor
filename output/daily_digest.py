"""Daily digest formatter — generates the daily Telegram digest."""

import logging
from datetime import datetime, timezone
from typing import Optional

from config.loader import get_chains
from processors.signal import Signal

logger = logging.getLogger(__name__)


def _is_noise(signal: Signal) -> bool:
    """Filter out noisy signals that clutter the digest."""
    desc = signal.description
    # EIPs RSS index pages — just category listings, not real content
    if "EIPs RSS" in desc:
        return True
    # Generic RSS "New post" with no real title
    if desc.startswith("[") and "New post" in desc:
        return True
    # Price/financial noise — user doesn't want price content
    if signal.category in ("FINANCIAL", "PRICE_NOISE"):
        return True
    return False


class DailyDigestFormatter:
    """Formats signals into a daily Telegram digest."""

    def format(self, signals: list[Signal], source_health: dict = None, upcoming: list = None) -> str:
        """Format signals into daily digest text."""
        # Filter noise before formatting
        signals = [s for s in signals if not _is_noise(s)]

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
        """Detect the single most important theme across ALL categories."""
        if not signals:
            return None

        # Sort all signals by priority, pick the top one for the theme
        top = sorted(signals, key=lambda x: -x.priority_score)[0]

        # Count how many high-priority signals exist per category
        high_signals = [s for s in signals if s.priority_score >= 6]
        if not high_signals:
            # Show most interesting dev activity
            tech = [s for s in signals if s.category == "TECH_EVENT"]
            if tech:
                top_tech = sorted(tech, key=lambda x: -x.priority_score)[0]
                desc = top_tech.description.split("(")[0].strip()
                return f"{top_tech.chain.capitalize()}: {desc.lower()}"
            return None

        cat_counts = {}
        for s in high_signals:
            cat_counts[s.category] = cat_counts.get(s.category, 0) + 1
        dominant_cat = max(cat_counts, key=cat_counts.get)
        dominant_signals = [s for s in high_signals if s.category == dominant_cat]

        if dominant_cat == "RISK_ALERT":
            chains = list(set(s.chain.capitalize() for s in dominant_signals[:3]))
            return f"⚠️ Security incident on {', '.join(chains)}. Check exposure."

        if dominant_cat == "REGULATORY":
            chains = list(set(s.chain.capitalize() for s in dominant_signals[:3]))
            return f"⚖️ Regulatory action affecting {', '.join(chains)}."

        if dominant_cat == "PARTNERSHIP":
            items = []
            for s in dominant_signals[:3]:
                desc = s.description.split("(")[0].strip()
                items.append(f"{s.chain.capitalize()} — {desc.lower()}")
            return "🤝 " + "; ".join(items)

        if dominant_cat == "TECH_EVENT":
            items = []
            for s in dominant_signals[:3]:
                desc = s.description.split("(")[0].strip()
                items.append(f"{s.chain.capitalize()} — {desc.lower()}")
            return "🔧 " + "; ".join(items)

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
