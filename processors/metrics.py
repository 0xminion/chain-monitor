"""Pipeline metrics — lightweight telemetry sink for chain-monitor.

Writes structured metrics to storage/metrics/metrics.jsonl for observability.
Each pipeline stage logs its latency and event counts.
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from processors.pipeline_utils import safe_json_write

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
METRICS_DIR = REPO_ROOT / "storage" / "metrics"
METRICS_FILE = METRICS_DIR / "metrics.jsonl"
RUN_STATE_FILE = METRICS_DIR / "collector_run_state.json"


class PipelineMetrics:
    """Track per-stage timing, event counts, and errors during pipeline execution."""

    def __init__(self):
        self._stages: dict[str, dict[str, Any]] = {}
        self._collector_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"events": 0, "errors": 0})
        self._start_time: float | None = None

    def stage_start(self, name: str):
        """Mark the start of a pipeline stage."""
        self._stages[name] = {"started_at": time.time(), "finished_at": None, "events_in": 0, "events_out": 0, "errors": 0}
        if self._start_time is None:
            self._start_time = time.time()

    def stage_end(self, name: str, events_in: int = 0, events_out: int = 0, errors: int = 0):
        """Mark the end of a pipeline stage with event counts."""
        if name in self._stages:
            self._stages[name]["finished_at"] = time.time()
            self._stages[name]["events_in"] = events_in
            self._stages[name]["events_out"] = events_out
            self._stages[name]["errors"] = errors

    def record_collector(self, name: str, events: int = 0, error: bool = False):
        """Record per-collector event count and error status."""
        self._collector_counts[name]["events"] += events
        if error:
            self._collector_counts[name]["errors"] += 1

    def to_dict(self) -> dict:
        """Serialize metrics to a dictionary."""
        stages_out = {}
        for name, data in self._stages.items():
            latency_ms = None
            if data.get("finished_at") and data.get("started_at"):
                latency_ms = round((data["finished_at"] - data["started_at"]) * 1000, 2)
            stages_out[name] = {
                "latency_ms": latency_ms,
                "events_in": data.get("events_in", 0),
                "events_out": data.get("events_out", 0),
                "errors": data.get("errors", 0),
            }
        total_latency_ms = None
        if self._start_time:
            total_latency_ms = round((time.time() - self._start_time) * 1000, 2)
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "total_latency_ms": total_latency_ms,
            "stages": stages_out,
            "collectors": dict(self._collector_counts),
        }

    def write(self):
        """Append metrics line to metrics.jsonl."""
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(self.to_dict(), ensure_ascii=False)
        with open(METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.info(f"[metrics] Pipeline metrics written to {METRICS_FILE}")

    def get_collector_alert_lines(self, health: dict) -> list[str]:
        """Return alert lines for collectors with zero events over consecutive runs.

        Reads previous run state from RUN_STATE_FILE and compares.
        """
        alerts = []
        prev_state = {}
        if RUN_STATE_FILE.exists():
            try:
                prev_state = json.loads(RUN_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        current_state = {}
        for collector_name, counts in self._collector_counts.items():
            current_state[collector_name] = {
                "events": counts["events"],
                "errors": counts["errors"],
                "status": health.get(collector_name, {}).get("status", "unknown"),
            }

        # Detect consecutive zero-event runs
        for name, data in current_state.items():
            if data["events"] == 0:
                prev_empty_runs = prev_state.get(name, {}).get("consecutive_empty_runs", 0)
                data["consecutive_empty_runs"] = prev_empty_runs + 1
                if data["consecutive_empty_runs"] >= 2:
                    alerts.append(
                        f"⚠️ Collector Alert: `{name}` has returned 0 events for {data['consecutive_empty_runs']} consecutive runs. "
                        f"Status: {data['status']}. Data may be incomplete."
                    )
            else:
                data["consecutive_empty_runs"] = 0

        # Detect down collectors (regardless of events)
        for name, h in health.items():
            if str(h.get("status", "")).lower() == "down":
                alerts.append(f"⚠️ Collector Alert: `{name}` is DOWN. Last error: {h.get('last_error', 'unknown')}")

        # Write updated state
        try:
            safe_json_write(RUN_STATE_FILE, current_state)
        except Exception as exc:
            logger.warning(f"[metrics] Failed to write run state: {exc}")

        return alerts
