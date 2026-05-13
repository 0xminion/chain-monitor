"""Daily digest formatter — generates the daily Telegram digest.

Produces prose-synthesized per-chain summaries with markdown source links.
Uses the summarizer module for LLM-driven prose synthesis.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from config.loader import get_chains
from processors.signal import Signal
from output.summarizer import summarize_chain

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
    sources_str = ",".join(a["source"] for a in signal.activity).lower()
    if "github" in sources_str:
        return True
    if "EIPs RSS" in desc:
        return True
    if desc.startswith("[") and "New post" in desc:
        return True
    if signal.category in ("FINANCIAL", "PRICE_NOISE"):
        return True
    if "FEATURED\n" in desc or "No hackathons found" in desc:
        return True
    if signal.category == "VISIBILITY" and any(
        kw in desc.lower() for kw in ["winners of", "results of", "announce the result"]
    ):
        return True
    if signal.category == "TECH_EVENT" and signal.activity:
        metric = signal.activity[0].get("evidence", {}).get("metric", "")
        if metric not in ("major_release", "new_release"):
            desc_lower = desc.lower()
            routine = (
                "fix:", "fix(", "feat:", "feat(", "build:", "build(",
                "backport ", "update ", "core/vm:", "core/eth:",
                "core/p2p:", "core/state:", "release rlock",
                "confidential asset",
            )
            if any(desc_lower.startswith(p) for p in routine):
                return True
    return False


def _is_recent_for_digest(signal: Signal, max_age_hours: float = 24) -> bool:
    """Check if signal is recent enough for the daily digest."""
    if not signal.activity:
        return True
    evidence = signal.activity[0].get("evidence", {})
    if not isinstance(evidence, dict):
        return True
    age_hours = evidence.get("age_hours")
    if age_hours is not None:
        return age_hours <= max_age_hours
    published = evidence.get("published_at") or evidence.get("published")
    if published:
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            return age <= max_age_hours
        except (ValueError, TypeError):
            pass
    return True


class DailyDigestFormatter:
    """Formats signals into a prose-synthesized daily Telegram digest.

    Calls the LLM summarizer per chain, then renders markdown output
    with clickable source links.
    """

    async def format(
        self,
        signals: list[Signal],
        source_health: dict = None,
        upcoming: list = None,
        source_health_detail: dict = None,
    ) -> str:
        """Format signals into prose digest text — one paragraph per chain.

        Layout:
          📊 Chain Monitor — date
          **Ethereum** (Score: 8)
          Prose summary with [markdown links](...).
          **Solana** (Score: 6)
          ...
          ⚠️ Source health
        """
        signals = [s for s in signals if not _is_noise(s)]

        # Deduplicate by signal ID
        seen = {}
        for s in signals:
            if s.id not in seen or s.priority_score > seen[s.id].priority_score:
                seen[s.id] = s
        signals = list(seen.values())

        # Time filter
        signals = [s for s in signals if _is_recent_for_digest(s, max_age_hours=24)]

        if not signals:
            now = datetime.now(timezone.utc).strftime("%b %d, %Y")
            return f"📊 Chain Monitor — {now}\n\n— No events in past 24h."

        # Group by chain
        by_chain: dict[str, list[Signal]] = defaultdict(list)
        for s in signals:
            by_chain[s.chain].append(s)

        # Sort chains by signal count
        chain_order = sorted(
            by_chain.items(),
            key=lambda x: (-len(x[1])),
        )

        now = datetime.now(timezone.utc).strftime("%b %d, %Y")

        lines: list[str] = [
            f"📊 Chain Monitor — {now}",
            "",
        ]

        # Summarize each chain via async LLM call
        summaries = await self._summarize_all(chain_order)

        # Separate high-signal sections vs tail
        head_chains = []
        tail_chains = []
        for (chain, sigs), prose in zip(chain_order, summaries):
            top_score = max((s.priority_score for s in sigs), default=0)
            twitter_count = sum(
                1 for s in sigs
                if any(a.get("source", "").lower() == "twitter" for a in s.activity)
            )
            chain_display = chain.capitalize() if chain.lower() != "unknown" else "General"

            entry = f"**{chain_display}** (Score: {top_score})\n{prose}"
            if twitter_count >= 5 or top_score >= 5:
                head_chains.append(entry)
            else:
                tail_chains.append(entry)

        for entry in head_chains:
            lines.append(entry)
            lines.append("")

        if tail_chains:
            for entry in tail_chains:
                lines.append(entry)
                lines.append("")

        # Source health
        if source_health:
            lines.extend(self._format_health(source_health, detail=source_health_detail))

        return "\n".join(lines)

    async def _summarize_all(
        self, chain_order: list[tuple[str, list[Signal]]]
    ) -> list[str]:
        """Summarize all chains via LLM, collecting results concurrently."""
        tasks = []
        for chain, sigs in chain_order:
            tasks.append(summarize_chain(chain, sigs))

        results = await asyncio.gather(*tasks)
        return results

    def should_send(self, signals: list[Signal]) -> bool:
        """Determine if digest should be sent (3+ events score ≥3)."""
        count = sum(1 for s in signals if s.priority_score >= 3)
        return count >= 3

    def _format_signal(self, signal: Signal, show_source: bool = False) -> str:
        """Format a single signal (legacy — used by weekly digest)."""
        chain = signal.chain.capitalize()
        desc_clean = _clean_description(signal.description)
        url = _extract_url(signal)
        sources_str = ", ".join(set(a["source"] for a in signal.activity))

        if url:
            title = f"[{desc_clean}]({url})"
        else:
            title = desc_clean

        if show_source and sources_str:
            return f"• {chain}: {title} [{sources_str}]"
        return f"• {chain}: {title}"

    def _format_health(self, health: dict, detail: dict = None) -> list[str]:
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

        lines.append(f"  Collectors: {healthy}/{total} healthy | {degraded} degraded | {down} down")

        if detail:
            feed_down = [
                name for name, h in detail.items()
                if _norm(h.get("status", "")) != "healthy"
            ]
            if feed_down:
                lines.append(f"  Feed issues ({len(feed_down)}):")
                for name in feed_down[:5]:
                    h = detail[name]
                    error = h.get("last_error", "unknown")[:60]
                    lines.append(f"    • {name}: {error}")
                if len(feed_down) > 5:
                    lines.append(f"    ... and {len(feed_down) - 5} more")

        lines.append("")
        return lines
