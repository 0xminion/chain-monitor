"""Narrative tracker — groups signals by theme, tracks velocity."""

import json
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Optional

from config.loader import get_narratives
from processors.signal import Signal

logger = logging.getLogger(__name__)

NARRATIVE_DIR = Path(__file__).parent.parent / "storage" / "narratives"


class NarrativeTracker:
    """Tracks narrative themes and velocity over time."""

    def __init__(self):
        NARRATIVE_DIR.mkdir(parents=True, exist_ok=True)
        self.narrative_config = get_narratives()
        self.weekly_counts: dict[str, dict[str, int]] = {}  # week_key -> {narrative -> count}
        self._load_history()

    def _load_history(self):
        """Load narrative history from storage."""
        path = NARRATIVE_DIR / "history.json"
        if path.exists():
            with open(path) as f:
                self.weekly_counts = json.load(f)

    def _save_history(self):
        """Save narrative history to storage."""
        path = NARRATIVE_DIR / "history.json"
        with open(path, "w") as f:
            json.dump(self.weekly_counts, f, indent=2)

    def _get_week_key(self, dt: datetime = None) -> str:
        """Get ISO week key like '2026-W15'."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"

    def classify_signal(self, signal: Signal) -> list[str]:
        """Classify a signal into narrative themes."""
        text = f"{signal.description} {signal.trader_context}".lower()
        matched_narratives = []

        narratives_cfg = self.narrative_config.get("narratives", {})
        for key, narrative in narratives_cfg.items():
            keywords = narrative.get("keywords", [])
            for kw in keywords:
                if kw in text:
                    matched_narratives.append(key)
                    break

        return matched_narratives if matched_narratives else ["uncategorized"]

    def record_signal(self, signal: Signal):
        """Record a signal for narrative tracking."""
        week_key = self._get_week_key()
        narratives = self.classify_signal(signal)

        if week_key not in self.weekly_counts:
            self.weekly_counts[week_key] = defaultdict(int)

        for narrative in narratives:
            self.weekly_counts[week_key][narrative] += 1

        self._save_history()

    def get_velocity(self, lookback_weeks: int = 4) -> dict:
        """Calculate narrative velocity (current vs trailing average)."""
        now = datetime.now(timezone.utc)
        weeks = []
        for i in range(lookback_weeks):
            dt = now - timedelta(weeks=i)
            weeks.append(self._get_week_key(dt))

        current_week = weeks[0]
        prior_weeks = weeks[1:]

        current_counts = self.weekly_counts.get(current_week, {})
        velocity = {}

        all_narratives = set()
        for w in [current_week] + prior_weeks:
            all_narratives.update(self.weekly_counts.get(w, {}).keys())

        for narrative in all_narratives:
            current = current_counts.get(narrative, 0)
            prior_values = [self.weekly_counts.get(w, {}).get(narrative, 0) for w in prior_weeks]
            prior_avg = sum(prior_values) / max(len(prior_values), 1)

            if prior_avg > 0:
                pct_change = ((current - prior_avg) / prior_avg) * 100
            elif current > 0:
                pct_change = 100.0
            else:
                pct_change = 0.0

            thresholds = self.narrative_config.get("velocity_thresholds", {})
            if pct_change >= thresholds.get("accelerating", 50):
                trend = "📈 accelerating"
            elif pct_change <= thresholds.get("fading", -30):
                trend = "📉 fading"
            else:
                trend = "➡️ steady"

            velocity[narrative] = {
                "current": current,
                "prior_avg": round(prior_avg, 1),
                "pct_change": round(pct_change, 1),
                "trend": trend,
                "weekly": [self.weekly_counts.get(w, {}).get(narrative, 0) for w in reversed(weeks)],
            }

        return velocity

    def get_convergence_flags(self) -> list[dict]:
        """Detect narrative convergence (3+ chains entering same theme)."""
        flags = []
        velocity = self.get_velocity()
        thresholds = self.narrative_config.get("velocity_thresholds", {})

        for narrative, data in velocity.items():
            if data["pct_change"] >= thresholds.get("convergence", 50):
                flags.append({
                    "narrative": narrative,
                    "signal_count": data["current"],
                    "velocity": data["pct_change"],
                    "trend": data["trend"],
                })

        return sorted(flags, key=lambda x: x["velocity"], reverse=True)

    def get_scorecard(self, lookback_weeks: int = 8) -> dict:
        """Generate 8-week narrative scorecard."""
        now = datetime.now(timezone.utc)
        weeks = []
        for i in range(lookback_weeks):
            dt = now - timedelta(weeks=i)
            weeks.append(self._get_week_key(dt))

        scorecard = {}
        all_narratives = set()
        for w in weeks:
            all_narratives.update(self.weekly_counts.get(w, {}).keys())

        for narrative in all_narratives:
            first_week = self.weekly_counts.get(weeks[-1], {}).get(narrative, 0)
            last_week = self.weekly_counts.get(weeks[0], {}).get(narrative, 0)

            if first_week > 0:
                pct_change = ((last_week - first_week) / first_week) * 100
            elif last_week > 0:
                pct_change = 100.0
            else:
                pct_change = 0.0

            if pct_change > 100 and last_week < 15:
                entry = "✓ Still early"
            elif pct_change > 100 and last_week >= 15:
                entry = "Already mainstream"
            elif pct_change < -30:
                entry = "Fading"
            else:
                entry = "—"

            scorecard[narrative] = {
                "first_week": first_week,
                "current": last_week,
                "pct_change": round(pct_change, 1),
                "entry_signal": entry,
            }

        return scorecard
