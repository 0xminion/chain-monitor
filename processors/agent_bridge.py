"""Agent bridge — connect the running agent to collected data.

v3.0: Agent-native. The running agent (human or AI) is the semantic engine.
Collectors provide structured data. The agent reads and reasons.

No external LLM API calls. No keyword-matching heuristics.
The agent lives in the same process or is invoked after collection.
"""

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from processors.pipeline_types import PipelineContext, RawEvent, ChainDigest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
AGENT_INPUT_DIR = REPO_ROOT / "storage" / "agent_input"


def save_agent_input(ctx: PipelineContext) -> Path:
    """Save clean collected events as structured JSON for the agent."""
    AGENT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = ctx.started_at.strftime("%Y%m%d_%H%M%S")
    path = AGENT_INPUT_DIR / f"events_{ts}.json"

    records = []
    for ev in ctx.unique_events:
        records.append({
            "chain": ev.chain,
            "category": ev.category,
            "subcategory": ev.subcategory,
            "description": ev.description,
            "source": ev.source,
            "reliability": ev.reliability,
            "evidence": ev.evidence,
            "raw_url": ev.raw_url,
            "published_at": ev.published_at.isoformat() if ev.published_at else None,
            "semantic": ev.semantic,
        })

    payload = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_count": len(ctx.raw_events),
            "unique_count": len(ctx.unique_events),
            "source_health": ctx.health,
        },
        "events": records,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"[agent_bridge] Saved {len(records)} events for agent: {path}")
    return path


def load_agent_input(path: Path) -> dict:
    """Load saved agent input."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def events_to_agent_prompt(events: list[dict]) -> str:
    """Format events into a rich markdown prompt for the agent."""
    lines = [
        "# Chain Monitor — Collected Events",
        "",
        f"**Total unique events:** {len(events)}",
        "",
        "## Instructions",
        "Read each event, assign categories, assess priority, group by chain,",
        "merge duplicates, and write a concise daily digest suitable for Telegram.",
        "",
        "Use categories: RISK_ALERT, REGULATORY, FINANCIAL, PARTNERSHIP, TECH_EVENT, VISIBILITY, NEWS, NOISE",
        "",
        "For each chain with notable activity, produce:",
        "- A 1-2 sentence summary of what's happening",
        "- Key events (up to 3) with why they matter to a trader",
        "- A priority score (0-15) for the chain",
        "",
        "---",
        "",
    ]

    # Group by chain
    by_chain: dict[str, list[dict]] = {}
    for ev in events:
        by_chain.setdefault(ev["chain"], []).append(ev)

    for chain, evs in sorted(by_chain.items()):
        lines.append(f"## {chain.upper()}")
        for ev in evs:
            desc = ev["description"][:200]
            src = ev["source"]
            rel = ev.get("reliability", 0.7)
            url = ev.get("raw_url", "")
            sem = ev.get("semantic")
            lines.append(f"- [{src}] (reliability {rel:.2f}) {desc}")
            if url:
                lines.append(f"  URL: {url}")
            if sem and isinstance(sem, dict):
                lines.append(f"  Collector hint: {sem.get('category', 'N/A')} / {sem.get('subcategory', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


async def agent_synthesize(ctx: PipelineContext) -> str:
    """Default agent synthesis hook.

    Saves events to disk and returns a prompt. The running agent
    (human or AI) is expected to read the saved events and produce
    the actual digest.

    Override this function to plug in your own agent.
    """
    path = save_agent_input(ctx)
    prompt = events_to_agent_prompt([{
        "chain": e.chain,
        "category": e.category,
        "subcategory": e.subcategory,
        "description": e.description,
        "source": e.source,
        "reliability": e.reliability,
        "evidence": e.evidence,
        "raw_url": e.raw_url,
        "published_at": e.published_at.isoformat() if e.published_at else None,
        "semantic": e.semantic,
    } for e in ctx.unique_events])

    # Save the prompt too
    prompt_path = AGENT_INPUT_DIR / f"prompt_{path.stem.replace('events_', '')}.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    logger.info(f"[agent_bridge] Agent prompt saved: {prompt_path}")

    return (
        f"🤖 Agent input ready at: {path}\n\n"
        f"Agent prompt saved at: {prompt_path}\n\n"
        f"The running agent should read the prompt and produce the digest.\n"
        f"To auto-generate, override processors.agent_bridge.agent_synthesize().\n"
    )
