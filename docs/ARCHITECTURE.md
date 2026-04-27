# Chain Monitor Architecture — v2.0

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
│ Stage 3: Categorize│ ← keyword (O(n)) + optional semantic enrich
│ + Score + Reinforce│     preserves backward compat with Signal model
└────────┬────────┘
         │ list[Signal]
         v
┌─────────────────┐
│ Stage 4: Chain   │ ← O(c) LLM calls, c=27 chains
│      Analyze     │     parallel via asyncio.Semaphore(5)
│  Merge signals   │     Merges related cross-source events with
│  into narratives │     confidence threshold
└────────┬────────┘
         │ list[ChainDigest]
         v
┌─────────────────┐
│ Stage 5: Digest  │ ← 1 LLM call (or fallback to structured)
│    Synthesize    │     LLM prose for chains ≥5, bullets for <5
└────────┬────────┘
         │ str (Telegram Markdown)
         v
┌─────────────────┐
│ Stage 6: Deliver │ ← Telegram + JSON run log + cleanup
│                  │     Send if ≥3 chains have significant activity
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
- `summary`: prose narrative, 2-4 sentences
- `key_events`: merged observations with `sources`, `why_it_matters`

### Stage 5 → 6: Final digest
If LLM enabled: single synthesis prompt with all ChainDigests.
If LLM disabled: pure-Python fallback with structured bullets.

## Parallelization Strategy

| Stage | Parallelization | Bottleneck | Mitigation |
|-------|------------------|------------|------------|
| 1 Collect | asyncio.gather + ThreadPoolExecutor | I/O wait on APIs | Semaphore(5) to avoid rate limits |
| 2 Dedup | Single-threaded (O(n), fast) | None | None needed |
| 3 Categorize | Single-threaded (O(n)) | None | None needed |
| 4 Chain analyze | asyncio.gather + Semaphore(5) | LLM latency | 5 concurrent, truncate >30 events |
| 5 Digest synthesize | Single-threaded | LLM latency | 45s timeout |
| 6 Deliver | Single-threaded | Telegram API | Auto-split + retry |

## LLM Call Budget

Per run:
- Stage 4: up to 27 calls × ~2,000 prompt tokens each
- Stage 5: 1 call × ~3,000 prompt tokens
- Total: ~57K tokens per run

Context window requirement: 200K+ recommended for chains with 100+ events
(truncation keeps top 40 per chain).

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
- LLM calls have circuit-breaker: after 3 consecutive failures, enrichment is disabled for the run
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
- Change scoring: edit `processors/scoring.py`
- Add new event category: update `processors/categorizer.py` CATEGORY_KEYWORDS + LLM prompts
