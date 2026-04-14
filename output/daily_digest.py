"""Daily digest formatter — generates the daily Telegram digest."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from config.loader import get_chains
from processors.signal import Signal

logger = logging.getLogger(__name__)


def _extract_url(signal: Signal) -> Optional[str]:
    """Extract the best URL from signal evidence for inline linking."""
    if not signal.activity:
        return None
    evidence = signal.activity[0].get("evidence", {})
    for key in ("html_url", "pr_url", "link", "feed_url"):
        url = evidence.get(key)
        if url and url.startswith("http"):
            return url
    return None


def _clean_description(desc: str) -> str:
    """Strip [Source Name] prefix from RSS descriptions."""
    if desc.startswith("["):
        idx = desc.find("]")
        if idx >= 0:
            return desc[idx + 1:].strip()
    return desc.strip()


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
    # Routine GitHub fixes/feats that aren't major releases
    if signal.category == "TECH_EVENT" and signal.activity:
        source = signal.activity[0].get("source", "")
        if source == "GitHub":
            metric = signal.activity[0].get("evidence", {}).get("metric", "")
            # Only keep major releases and high-signal PRs (EIP/fork/security/audit)
            if metric not in ("major_release", "new_release"):
                desc_lower = desc.lower()
                # Skip routine fix/feat/build PRs
                routine = ("fix:", "fix(", "feat:", "feat(", "build:", "build(",
                           "backport ", "update ", "core/vm:", "core/eth:",
                           "core/p2p:", "core/state:", "release rlock",
                           "confidential asset")
                if any(desc_lower.startswith(p) for p in routine):
                    return True
    return False


def _html_link(title: str, url: Optional[str]) -> str:
    """Create an HTML-linked title for Telegram."""
    if url and url.startswith("http"):
        # Escape HTML entities in title
        safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<a href="{url}">{safe}</a>'
    return title


class DailyDigestFormatter:
    """Formats signals into a daily Telegram digest."""

    def format(self, signals: list[Signal], source_health: dict = None, upcoming: list = None) -> str:
        """Format signals into daily digest text."""
        signals = [s for s in signals if not _is_noise(s)]

        now = datetime.now(timezone.utc).strftime("%b %d, %Y")

        critical = [s for s in signals if s.priority_score >= 10]
        high = [s for s in signals if 8 <= s.priority_score < 10]
        notable = [s for s in signals if 6 <= s.priority_score < 8]

        sections = [
            f"📊 Chain Monitor — {now}",
            "",
        ]

        # Theme
        theme = self._detect_theme(signals)
        if theme:
            sections.extend(["🧠 Today's theme", theme, ""])

        # Critical
        if critical:
            sections.append("🔴 Critical (Score ≥10)")
            for s in sorted(critical, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # High
        if high:
            sections.append("🟠 High (Score 8-9)")
            for s in sorted(high, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # Notable
        if notable:
            sections.append("🟡 Notable (Score 6-7)")
            for s in sorted(notable, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # Dev activity
        dev_activity = [s for s in signals if s.category == "TECH_EVENT" and s.priority_score < 6]
        if dev_activity:
            sections.append("🔧 Dev activity")
            for s in sorted(dev_activity, key=lambda x: -x.priority_score)[:3]:
                sections.append(self._format_signal(s))
                sections.append("")

        # Partnerships
        partnerships = [s for s in signals if s.category == "PARTNERSHIP"]
        if partnerships:
            sections.append("🤝 Partnerships")
            for s in sorted(partnerships, key=lambda x: -x.priority_score)[:5]:
                sections.append(self._format_signal(s))
                sections.append("")

        # No events
        if not critical and not high and not notable and not dev_activity and not partnerships:
            sections.append("— No high-priority events. Quiet day.")

        # Source Health
        if source_health:
            sections.extend(self._format_health(source_health))

        return "\n".join(sections)

    def should_send(self, signals: list[Signal]) -> bool:
        """Determine if digest should be sent (3+ events score ≥6)."""
        notable_count = sum(1 for s in signals if s.priority_score >= 6)
        return notable_count >= 3

    def _format_signal(self, signal: Signal) -> str:
        """Format a single signal with HTML-linked title."""
        chain = signal.chain.capitalize()
        desc_clean = _clean_description(signal.description)
        url = _extract_url(signal)
        linked = _html_link(desc_clean, url)
        sources_str = ", ".join(set(a["source"] for a in signal.activity))
        rein_str = f" — {signal.source_count}x" if signal.source_count > 1 else ""

        return f"• {chain}: {linked} [{sources_str}{rein_str}]"

    def _detect_theme(self, signals: list[Signal]) -> Optional[str]:
        """Detect the single most important theme across ALL categories."""
        if not signals:
            return None

        high_signals = [s for s in signals if s.priority_score >= 6]
        if not high_signals:
            tech = [s for s in signals if s.category == "TECH_EVENT"]
            if tech:
                top_tech = sorted(tech, key=lambda x: -x.priority_score)[0]
                desc = _clean_description(top_tech.description).split("(")[0].strip()
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

        if dominant_cat == "TECH_EVENT":
            items = []
            for s in dominant_signals[:3]:
                desc = _clean_description(s.description).split("(")[0].strip()
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
