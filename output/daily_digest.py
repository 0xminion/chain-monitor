"""Daily digest formatter — generates the daily Telegram digest."""

import logging

from datetime import datetime, timezone
from typing import Optional


from processors.signal import Signal

logger = logging.getLogger(__name__)


def _extract_url(signal: Signal) -> Optional[str]:
    """Extract the best URL from signal evidence for linking."""
    if not signal.activity:
        return None
    evidence = signal.activity[0].get("evidence", {})
    if not isinstance(evidence, dict):
        return None
    for key in ("html_url", "pr_url", "link", "feed_url"):
        url = evidence.get(key)
        if url and url.startswith("http"):
            return url
    # Fallback: check all activities for a URL
    for act in signal.activity:
        ev = act.get("evidence", {})
        if isinstance(ev, dict):
            for key in ("html_url", "pr_url", "link", "feed_url"):
                url = ev.get(key)
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
    # Raw Devpost/hackathon text dumps — not formatted for digest
    if "FEATURED\n" in desc or "No hackathons found" in desc:
        return True
    # Old hackathon outcome reports (Solana/ETHGlobal results from months ago)
    if signal.category == "VISIBILITY" and any(kw in desc.lower() for kw in ["winners of", "results of", "announce the result"]):
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


def _is_recent_for_digest(signal: Signal, max_age_hours: float = 24) -> bool:
    """Check if signal is recent enough for the daily digest.
    
    Filters based on the actual event age (from evidence), not detection time.
    Signals without age data are allowed through (assume recent).
    """
    if not signal.activity:
        return True  # no data, allow
    evidence = signal.activity[0].get("evidence", {})
    if not isinstance(evidence, dict):
        return True
    
    age_hours = evidence.get("age_hours")
    if age_hours is not None:
        return age_hours <= max_age_hours
    
    # Check published_at timestamp
    published = evidence.get("published_at") or evidence.get("published")
    if published:
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            return age <= max_age_hours
        except (ValueError, TypeError):
            pass
    
    return True  # no age data, allow


class DailyDigestFormatter:

    def format(self, signals: list[Signal], source_health: dict = None, upcoming: list = None, source_health_detail: dict = None) -> str:
        """Format signals into daily digest text."""
        signals = [s for s in signals if not _is_noise(s)]

        # Deduplicate by signal ID — keep highest scoring instance
        seen = {}
        for s in signals:
            if s.id not in seen or s.priority_score > seen[s.id].priority_score:
                seen[s.id] = s
        signals = list(seen.values())

        # Time filter: only include signals from past 24h
        signals = [s for s in signals if _is_recent_for_digest(s, max_age_hours=24)]

        now = datetime.now(timezone.utc).strftime("%b %d, %Y")

        # New scoring tiers
        critical = [s for s in signals if s.priority_score >= 8]
        high = [s for s in signals if 5 <= s.priority_score < 8]
        medium = [s for s in signals if 3 <= s.priority_score < 5]

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
            sections.append("🔴 Critical (Score ≥8)")
            for s in sorted(critical, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # High
        if high:
            sections.append("🟠 High (Score 5-7)")
            for s in sorted(high, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # Medium
        if medium:
            sections.append("🟡 Medium (Score 3-4)")
            for s in sorted(medium, key=lambda x: -x.priority_score):
                sections.append(self._format_signal(s))
                sections.append("")

        # Dev activity (low-priority tech events not already surfaced)
        dev_activity = [s for s in signals if s.category == "TECH_EVENT" and s.priority_score < 3]
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
        if not critical and not high and not medium and not dev_activity and not partnerships:
            sections.append("— No high-priority events. Quiet day.")

        # Source Health
        if source_health:
            sections.extend(self._format_health(source_health, detail=source_health_detail))

        return "\n".join(sections)

    def should_send(self, signals: list[Signal]) -> bool:
        """Determine if digest should be sent (3+ events score ≥3)."""
        count = sum(1 for s in signals if s.priority_score >= 3)
        return count >= 3

    def _format_signal(self, signal: Signal) -> str:
        """Format a single signal with clickable link embedded in title."""
        chain = signal.chain.capitalize()
        desc_clean = _clean_description(signal.description)
        url = _extract_url(signal)
        sources_str = ", ".join(set(a["source"] for a in signal.activity))

        if url:
            # Markdown link: [Title](URL) — Telegram renders as clickable
            title = f"[{desc_clean}]({url})"
        else:
            title = desc_clean

        return f"• {chain}: {title} [{sources_str}]"

    def _detect_theme(self, signals: list[Signal]) -> Optional[str]:
        """Detect the single most important theme across ALL categories."""
        if not signals:
            return None

        high_signals = [s for s in signals if s.priority_score >= 5]
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

    def _format_health(self, health: dict, detail: dict = None) -> list[str]:
        """Format source health summary with per-feed detail."""
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

        lines.append(f"  Collectors: {healthy}/{total} healthy | {degraded} degraded | {down} down")

        # Per-feed detail from RSS and other collectors
        if detail:
            feed_down = [name for name, h in detail.items() if _norm(h.get("status", "")) != "healthy"]
            if feed_down:
                lines.append(f"  Feed issues ({len(feed_down)}):")
                for name in feed_down[:5]:
                    h = detail[name]
                    error = h.get("last_error", "unknown")[:60]
                    lines.append(f"    • {name}: {error}")
                if len(feed_down) > 5:
                    lines.append(f"    ... and {len(feed_down) - 5} more")

        # Collector-level issues
        issues = [
            (name, h) for name, h in health.items()
            if _norm(h.get("status", "")) != "healthy"
        ]
        if issues:
            for name, h in issues[:3]:
                lines.append(f"  {name}: {h.get('status', 'unknown')} ({h.get('failures_24h', 0)} failures)")

        lines.append("")
        return lines
