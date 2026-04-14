"""Weekly digest formatter — generates the weekly strategic report."""

import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional

from config.loader import get_chains
from processors.signal import Signal
from processors.narrative_tracker import NarrativeTracker

logger = logging.getLogger(__name__)


def _clean_desc(desc: str) -> str:
    """Strip [Source Name] prefix from descriptions."""
    if desc.startswith("["):
        idx = desc.find("]")
        if idx >= 0:
            return desc[idx + 1:].strip()
    return desc.strip()


def _extract_url(signal: Signal) -> Optional[str]:
    """Extract URL from signal evidence for linking."""
    if not signal.activity:
        return None
    evidence = signal.activity[0].get("evidence", {})
    for key in ("html_url", "pr_url", "link", "feed_url"):
        url = evidence.get(key)
        if url and url.startswith("http"):
            return url
    return None


def _is_noise(signal: Signal) -> bool:
    """Filter noisy signals."""
    desc = signal.description
    if "EIPs RSS" in desc:
        return True
    if desc.startswith("[") and "New post" in desc:
        return True
    if signal.category in ("FINANCIAL", "PRICE_NOISE"):
        return True
    return False


class WeeklyDigestFormatter:
    """Formats signals into a weekly strategic report."""

    def format(
        self,
        signals: list[Signal],
        narrative_tracker: NarrativeTracker = None,
        source_health: dict = None,
    ) -> str:
        """Generate weekly digest from signals and narrative data."""
        signals = [s for s in signals if not _is_noise(s)]

        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=7)).strftime("%b %d")
        week_end = now.strftime("%b %d, %Y")

        sections = []

        # Header
        sections.append(f"📈 Chain Monitor — Weekly Digest")
        sections.append(f"Period: {week_start} — {week_end}")
        sections.append("")

        # Group signals by chain and category
        by_chain = defaultdict(list)
        by_cat = defaultdict(list)
        for s in signals:
            by_chain[s.chain].append(s)
            by_cat[s.category].append(s)

        # Action brief — top 3 actionable items
        sections.extend(self._format_action_brief(signals, by_chain))

        # Narrative of the week
        sections.extend(self._format_narrative(signals, by_cat, narrative_tracker))

        # Narrative velocity (4-week trend)
        if narrative_tracker:
            sections.extend(self._format_velocity(narrative_tracker))

        # Chain focus radar — per-chain highlights
        sections.extend(self._format_chain_focus(by_chain))

        # Risk alerts
        risk = [s for s in signals if s.category == "RISK_ALERT"]
        if risk:
            sections.append("⚠️ Risk Alerts")
            sections.append("")
            for s in sorted(risk, key=lambda x: -x.priority_score)[:5]:
                chain = s.chain.capitalize()
                desc = _clean_desc(s.description)[:65]
                sections.append(f"  • {chain}: {desc}")
            sections.append("")

        # Governance summary
        sections.extend(self._format_governance(signals))

        # Stats
        sections.extend(self._format_stats(signals, by_chain, by_cat, source_health))

        return "\n".join(sections)

    def _format_action_brief(self, signals: list[Signal], by_chain: dict) -> list[str]:
        """Generate top 3 actionable items from high-priority signals."""
        lines = ["🎯 Action Brief", ""]

        high = sorted(
            [s for s in signals if s.priority_score >= 8],
            key=lambda x: -x.priority_score
        )

        if not high:
            lines.append("  No high-priority events this week.")
            lines.append("")
            return lines

        for i, s in enumerate(high[:3], 1):
            chain = s.chain.capitalize()
            desc = _clean_desc(s.description)[:70]
            cat = s.category.lower().replace("_", " ")
            lines.append(f"  {i}. {chain}: {desc}")
            lines.append(f"     Category: {cat} | Score: {s.priority_score}")
            lines.append("")

        return lines

    def _format_narrative(
        self,
        signals: list[Signal],
        by_cat: dict,
        narrative_tracker: NarrativeTracker = None,
    ) -> list[str]:
        """Generate narrative of the week summary."""
        lines = ["🧠 Narrative of the Week", ""]

        if not signals:
            lines.append("  Quiet week. No significant narrative shifts.")
            lines.append("")
            return lines

        # Find dominant category
        cat_counts = {cat: len(sigs) for cat, sigs in by_cat.items()}
        if not cat_counts:
            lines.append("  No categorized signals this week.")
            lines.append("")
            return lines

        dominant_cat = max(cat_counts, key=cat_counts.get)
        dominant_sigs = by_cat[dominant_cat]

        # Synthesize a 1-line narrative
        chains = list(set(s.chain.capitalize() for s in dominant_sigs))[:4]
        top = max(dominant_sigs, key=lambda s: s.priority_score)
        desc = _clean_desc(top.description)[:60]

        cat_labels = {
            "TECH_EVENT": "building",
            "PARTNERSHIP": "integrating",
            "REGULATORY": "regulatory pressure",
            "RISK_ALERT": "security incidents",
            "VISIBILITY": "visibility push",
        }
        verb = cat_labels.get(dominant_cat, "active")

        lines.append(f"  {', '.join(chains[:3])} dominated by {verb} this week.")
        lines.append(f"  Top signal: {desc}")
        lines.append("")

        return lines

    def _format_velocity(self, narrative_tracker: NarrativeTracker) -> list[str]:
        """Format narrative velocity table (4-week trend)."""
        lines = ["📈 Narrative Velocity (4-week trend)", ""]

        velocity = narrative_tracker.get_velocity(lookback_weeks=4)

        if not velocity:
            lines.append("  Insufficient data (need 2+ weeks of history).")
            lines.append("")
            return lines

        # Sort by current count descending
        sorted_narratives = sorted(velocity.items(), key=lambda x: -x[1]["current"])

        lines.append(f"  {'Narrative':<20} {'Wk1':>4} {'Wk2':>4} {'Wk3':>4} {'Wk4':>4} {'Trend'}")
        lines.append(f"  {'-'*20} {'----':>4} {'----':>4} {'----':>4} {'----':>4} {'-----'}")

        for narrative, data in sorted_narratives[:8]:
            weeks = data.get("weekly", [0, 0, 0, 0])
            # Pad to 4 weeks
            while len(weeks) < 4:
                weeks.insert(0, 0)
            weeks = weeks[:4]

            trend = data["trend"]
            name = narrative[:20]
            lines.append(
                f"  {name:<20} {weeks[0]:>4} {weeks[1]:>4} {weeks[2]:>4} {weeks[3]:>4} {trend}"
            )

        lines.append("")

        # Convergence flags
        convergence = narrative_tracker.get_convergence_flags()
        if convergence:
            lines.append("  🚨 Convergence detected:")
            for flag in convergence[:3]:
                lines.append(
                    f"    {flag['narrative']}: {flag['signal_count']} signals "
                    f"(+{flag['velocity']:.0f}% vs trailing avg)"
                )
            lines.append("")

        return lines

    def _format_chain_focus(self, by_chain: dict) -> list[str]:
        """Generate per-chain focus highlights."""
        lines = ["🎯 Chain Focus", ""]

        # Sort chains by total signal score
        chain_scores = {}
        for chain, sigs in by_chain.items():
            chain_scores[chain] = sum(s.priority_score for s in sigs)

        top_chains = sorted(chain_scores.items(), key=lambda x: -x[1])[:8]

        for chain, total_score in top_chains:
            sigs = by_chain[chain]
            top = max(sigs, key=lambda s: s.priority_score)
            desc = _clean_desc(top.description)[:55]
            categories = list(set(s.category for s in sigs))
            cat_str = ", ".join(c.lower().replace("_", " ") for c in categories[:3])

            cap_chain = chain.capitalize()
            lines.append(f"  {cap_chain}: {desc}")
            lines.append(f"    Active: {cat_str} | {len(sigs)} events")
            lines.append("")

        return lines

    def _format_governance(self, signals: list[Signal]) -> list[str]:
        """Format governance summary."""
        lines = ["🏛️ Governance", ""]

        gov_signals = [
            s for s in signals
            if s.category == "TECH_EVENT" and any(
                kw in s.description.lower()
                for kw in ("proposal", "eip", "bip", "simd", "governance", "vote", "aip")
            )
        ]

        if not gov_signals:
            lines.append("  No governance activity detected this week.")
            lines.append("")
            return lines

        by_chain_gov = defaultdict(list)
        for s in gov_signals:
            by_chain_gov[s.chain].append(s)

        for chain, sigs in sorted(by_chain_gov.items(), key=lambda x: -len(x[1])):
            cap_chain = chain.capitalize()
            for s in sorted(sigs, key=lambda x: -x.priority_score)[:2]:
                desc = _clean_desc(s.description)[:65]
                lines.append(f"  • {cap_chain}: {desc}")
        lines.append("")

        return lines

    def _format_stats(
        self,
        signals: list[Signal],
        by_chain: dict,
        by_cat: dict,
        source_health: dict = None,
    ) -> list[str]:
        """Format methodology notes and stats."""
        lines = ["📊 Week Stats", ""]

        high = len([s for s in signals if s.priority_score >= 8])
        critical = len([s for s in signals if s.priority_score >= 10])

        lines.append(f"  Total signals: {len(signals)}")
        lines.append(f"  Critical (≥10): {critical}")
        lines.append(f"  High (8-9): {high}")
        lines.append(f"  Chains active: {len(by_chain)}")
        lines.append(f"  Categories active: {len(by_cat)}")

        if source_health:
            healthy = sum(
                1 for h in source_health.values()
                if h.get("status", "").lower() in ("healthy", "ok", "up")
            )
            lines.append(f"  Sources healthy: {healthy}/{len(source_health)}")

        lines.append("")
        return lines
