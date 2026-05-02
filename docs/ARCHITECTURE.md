# Chain Monitor Architecture — v0.1.0

## Pipeline Stages

```
┌─────────────────┐
│  Stage 1: Collect │ ← parallel (async, 10 collectors, semaphore=5)
│  O(k) collectors │     k=10
└────────┬────────┘
         │ list[RawEvent]
         v
┌─────────────────┐
│  Stage 2: Dedup   │ ← O(n) single pass
│  URL index + FP  │     n = total raw events
└────────┬────────┘
         │ list[RawEvent]
         v
┌─────────────────┐
│ Stage 3: Categorize│ ← agent-native checkpoint
│ + Score + Reinforce│     agent provides categories; deterministic scoring 
└────────┬────────┘
         │ list[Signal]
         v
┌─────────────────┐
│ Stage 4: Chain   │ ← deterministic O(c), c=27 chains
│      Analyze     │     merges related cross-source events with
│  Merge signals   │     confidence threshold
│  into narratives │
└────────┬────────┘
         │ list[ChainDigest]
         v
┌─────────────────┐
│ Stage 5: Digest   │ ← agent-native prompt synthesis; per-chain prose
│    Synthesize     │     Markdown links embedded on first word. (300-600 words)
└────────┬────────┘
         │ str (Telegram Markdown)
         v
┌─────────────────┐
│ Stage 6: Weekly   │ ← agent-native thematic synthesis
│    Synthesize     │     Reads 7 days of persisted daily digests.
│                   │     Up to 10 thematic sections with emoji headers.
└────────┬────────┘
         │ str (Telegram Markdown)
         v
┌─────────────────┐
│ Stage 7: Deliver  │ ← Telegram + JSON run log + daily digest persistence
│                  │     Send if ≥2 chains have significant activity
└─────────────────┘
```

## Data Flow

### Stage 1 → 2: RawEvent contract
Every collector (legacy or new) must produce output that can become a `RawEvent`.
The `RawEvent.from_collector_dict()` adapter bridges legacy dict-returning collectors.

### Stage 2 → 3: Deduplication keys
- **Primary key**: `url:{chain}:{normalized_url}`
- **Secondary key**: `fp:{chain}:{category}:{sha256(description[:200])[:24]}`

Collision resolution keeps the event with highest evidence weight.
Tie-breaker: most recent published_at.

### Stage 3 → 4: Signal to events_by_chain
After scoring, events are re-grouped by chain from the *unique* (not reinforced) set,
so the LLM sees all distinct observations for cross-source merging.

### Stage 4 → 5: ChainDigest
- `priority_score`: 0-15 (chain total, not per-event)
- `confidence`: 0.0-1.0 (how well sources agree)
- `summary`: prose narrative, 2-4 sentences (from deterministic builder)
- `key_events`: merged observations with `sources`, `why_it_matters`

### Stage 5 → 6: Final digest
Agent-native synthesis: rich markdown prompt saved to `storage/agent_input/` for the running agent.
Fallback: structured bullet list when no agent is available.

## Parallelization Strategy

| Stage | Parallelization | Bottleneck | Mitigation |
|-------|------------------|------------|------------|
| 1 Collect | asyncio.gather + ThreadPoolExecutor | I/O wait on APIs | Semaphore(5) to avoid rate limits |
| 2 Dedup | Single-threaded (O(n), fast) | None | None needed |
| 3 Categorize | Single-threaded (O(n)) | None | None needed |
| 4 Chain analyze | asyncio.gather | data volume | deterministic, fast |
| 5 Digest synthesize | Single-threaded | disk write | instant |
| 6 Deliver | Single-threaded | Telegram API | Auto-split + retry |

## Agent-Native Synthesis Budget

No external LLM calls are made during pipeline execution. The running agent reads
persisted prompts and produces prose digests independently.

- Stage 4: deterministic rule-based ChainDigest building (zero tokens)
- Stage 5: prompt written to disk for agent consumption (zero tokens)
- Stage 6: prompt written to disk for weekly consumption (zero tokens)

Daily prompt size: ~5-15K chars per chain (up to 30 chains).
Weekly prompt size: up to 200K chars of daily digest text (truncated).

## Configuration Files

| File | Purpose |
|------|---------|
| `config/chains.yaml` | 27 chain definitions |
| `config/baselines.yaml` | Per-chain scoring thresholds |
| `config/narratives.yaml` | Narrative categories and keywords |
| `config/sources.yaml` | RSS feeds, API endpoints |
| `.env` | Secrets, LLM provider, Telegram |

## Security & Error Isolation

- Each collector runs in its own task (isolated exceptions)
- `asyncio.gather(return_exceptions=True)` prevents one collector from crashing the pipeline
- Collector tasks isolated: `asyncio.gather(return_exceptions=True)` prevents one failed collector from crashing the pipeline
- Signal storage uses `FileLock` to prevent Coroutine/json corruption under cron overlap

## Testing

```bash
# Unit tests (fast, no external deps)
python3 -m pytest tests/unit/ -q

# Integration tests (real collectors, but mocked I/O)
python3 -m pytest tests/integration/ -q

# System tests (full pipeline, slow)
python3 -m pytest tests/system/ -q

# All tests
python3 -m pytest tests/ -q
```

## Extension Points

- Add a collector: subclass `BaseCollector`, implement `collect()`, register in `main.py`
- Add a chain: use `scripts/chain_monitor_cli.py chains add` or edit `config/chains.yaml`
- Change LLM prompt: edit `processors/chain_analyzer.py` or `processors/summary_engine.py`
- Change weekly digest format: edit `output/weekly_digest.py` `build_digest()`
- Change scoring: edit `processors/scoring.py`
- Add new event category: update `processors/categorizer.py` CATEGORY_KEYWORDS + LLM prompts

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup.py` | Interactive `.env` generator with LLM validation |
| `scripts/doctor.py` | End-to-end health check with auto-fix hints |
| `scripts/chain_monitor_cli.py` | Management CLI for chains, cron, digest, health |
| `scripts/run_all_chains.py` | Full pipeline for all 27 chains (batch Twitter, divide & conquer) |
| `output/weekly_digest.py` | Weekly digest builder (reads 7 days of daily prompts) |
