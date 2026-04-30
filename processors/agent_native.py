"""Agent-native checkpoint utilities.

No keyword matching. No LLM calls. The running agent provides all semantic reasoning.

Provides:
  - save_agent_task(): persist a structured task for the agent
  - find_agent_output(): locate the agent's completed work
  - save_agent_output(): persist agent-completed results

Task flow:
  1. Python code calls save_agent_task() with raw data + instructions
  2. Running agent reads the task, applies reasoning, calls save_agent_output()
  3. Python code calls find_agent_output() and resumes the pipeline
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
AGENT_INPUT_DIR = REPO_ROOT / "storage" / "agent_input"
AGENT_OUTPUT_DIR = REPO_ROOT / "storage" / "agent_output"


def save_agent_task(task_type: str, payload: dict) -> Path:
    """Save a structured task for the running agent.

    Returns the path to the saved task file.
    """
    AGENT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = AGENT_INPUT_DIR / f"{task_type}_task_{ts}.json"
    envelope = {
        "task_type": task_type,
        "task_id": ts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[agent-native] Task saved: {path}")
    return path


def find_agent_output(task_type: str, task_id: Optional[str] = None) -> Optional[Path]:
    """Find the most recent agent output for a given task type.

    If task_id is provided, requires an exact match on task_id.
    Otherwise returns the most recent output file.
    """
    AGENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pattern = f"{task_type}_output_*.json"
    files = sorted(AGENT_OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        return None

    if task_id:
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("task_id") == task_id:
                    return f
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    return files[0]


def save_agent_output(task_type: str, task_id: str, results: list[dict], metadata: Optional[dict] = None) -> Path:
    """Save agent-completed results.

    Call this from the running agent after processing a task.
    """
    AGENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = AGENT_OUTPUT_DIR / f"{task_type}_output_{ts}.json"
    envelope = {
        "task_type": task_type,
        "task_id": task_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "metadata": metadata or {},
    }
    path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[agent-native] Output saved: {path}")
    return path


def load_agent_output(path: Path) -> dict:
    """Load and validate agent output file."""
    if not path.exists():
        raise FileNotFoundError(f"Agent output not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" not in data:
        raise ValueError(f"Agent output missing 'results' key: {path}")
    return data
