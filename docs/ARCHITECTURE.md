# Chain Monitor — Architecture

**Version:** v0.1.0-agent-native
**Last updated:** May 2026

---

## Pipeline Overview

7-stage deterministic pipeline. The running agent is the only reasoning engine — there are no external LLM calls, no Telegram bot, and no inline model inference.

```
┌────────────────────┐
│ Stage 0: Collect     │ ← asyncio.gather across 10 collectors
│    (parallel)        │     RSS, DefiLlama, CoinGecko, TradingView, Events,
│                      │     Hackathon Outcomes, Risk Alert, Regulatory, Twitter
└──────────┬──────────┘
           │ list[RawEvent]
           v
┌────────────────────┐
│ Stage 1: Dedup       │ ← O(n) hash-based dedup (URL + fingerprint)
│                      │     Source health computed.
└──────────┬──────────┘
           │ list[RawEvent] + health report
           v
┌────────────────────┐
│ Stage 2: Categorize  │ ← deterministic keyword + source-provided category
│                      │     fallback. No LLM. No agent blocking.
└──────────┬──────────┘
           │ list[RawEvent] with category/subcategory
           v
┌────────────────────┐
│ Stage 3: Score       │ ← rule-based P2-P9 scoring + chain mapping
│                      │     Baselines sourced from config/baselines.yaml
└──────────┬──────────┘
           │ list[Signal]
           v
┌────────────────────┐
│ Stage 4: Reinforce   │ ← cross-source merge (dedup on fingerprint)
│                      │     Same event from RSS = one reinforced signal
└──────────┬──────────┘
           │ dict[chain, list[Signal]]
           v
┌────────────────────┐
│ Stage 5: Analyze     │ ← per-chain deterministic analysis
│                      │     builds ChainDigest (summary, events, score)
└──────────┬──────────┘
           │ list[ChainDigest]
           v
┌────────────────────┐
│ Stage 6: Synthesize  │ ← AgentDigestRunner builds markdown prompt
│                      │     Prompt saved to storage/agent_input/
└──────────┬──────────┘
           │ str (Markdown prompt)
           v
┌────────────────────┐
│ Stage 7: Deliver     │ ← Agent-native prose synthesis
│                      │     The running agent reads prompt, writes digest
└────────────────────┘
```

---

## Design Decisions

### Agent-Native Architecture

The traditional LLM-in-pipeline approach (calling OpenAI/Ollama during each run) was removed because:

1. **Hallucination risk:** inline LLM calls fabricate URLs, dollar amounts, and partnerships
2. **Latency:** 30-120s blocking calls slow a pipeline that should finish in ~5min
3. **Token cost:** daily + weekly synthesis consumes ~50K tokens/day per model provider
4. **Reliability:** local Ollama models crash on 16GB Steam Deck under concurrent browser load

The agent-native model inverts this: the pipeline produces deterministic structured data, the running agent (you) reads a rich prompt and writes prose. Trust moves from opaque model inference to explicit prompt + human reasoning.

### Why ProcessPoolExecutor for Twitter (not async)

X throttles concurrent tabs within a single browser context. A single Playwright `Browser` + 5+ concurrent `Page` objects yields degraded or empty timelines. Each `ProcessPoolExecutor` worker gets its own isolated browser + temp Chrome profile, bypassing server-side detection entirely. This costs RAM (~200MB/worker) but produces reliable tweet extraction on Steam Deck (16GB total).

---

## Stage-by-Stage Details

### Stage 0: Parallel Collect

All collectors implement `BaseCollector` with `async collect()` returning `list[RawEvent]`. `parallel_runner.collect_all()` gathers them with `asyncio.gather(return_exceptions=True)` so one broken collector cannot crash the pipeline.

Twitter is the only collector using synchronous Playwright via `ProcessPoolExecutor`. It batches 138 handles across 15 workers × 10 batches. Each worker gets a lightweight Chrome profile copy (no caches, no IndexedDB) to keep `/tmp` usage under 1.5GB.

### Stage 1: Dedup

`dedup_engine.py` maintains a rolling hash set across pipeline runs. Deduplication keys:

- Primary: `hashlib.sha256(url + normalized_text[:120])`
- Fallback: `hashlib.sha256(normalized_text[:200])` for events without URLs

Complexity: O(n) single pass. Old approach was O(n×m) pairwise similarity — abandoned because it was ~40% of runtime on 200+ events.

### Stage 2: Categorize

`EventCategorizer.apply_categories()` maps events using source-provided categories. A deterministic keyword dictionary (`CATEGORY_KEYWORDS` in `categorizer.py`) provides fallback when the collector didn't set a category. No blocking agent checkpoint in production — the "agent checkpoint" pattern in `agent_native.py` is reserved for manual override workflows.

### Stage 3–4: Score + Reinforce

`SignalScorer.score()` converts a categorized event into a `Signal` with `impact` (1-5), `urgency` (1-3), and `priority_score = impact × urgency`. Chain mapping uses `primary_chain` from config, then keyword mentions, then description heuristics.

`SignalReinforcer.process()` merges signals with identical fingerprints. A signal reinforced by 3+ sources gets `composite_confidence = min(0.95, max_reliability × 1.3)`.

### Stage 5: Per-chain Analyze

`chain_analyzer.analyze_all_chains()` iterates each configured chain and builds a `ChainDigest` from its signals. Deterministic rules pick:

- `dominant_topic`: category with most signals
- `key_events`: top-N by priority (sorted descending, max 5)
- `priority_score`: highest individual signal priority + source-count bonus

### Stage 6: Prompt Synthesis

`AgentDigestRunner.synthesize()` calls `summary_engine._build_daily_prompt()` to produce a markdown prompt containing:

1. Date header
2. Source health summary
3. One `### ChainName (Score: X)` section per active chain
4. Per-event `URL:` and `Detail:` fields for every signal
5. Strict output format instructions (word count, link placement, prose rules)

The prompt is saved to `storage/agent_input/daily_prompt_YYYYmmDD_HHMMSS.md`.

### Stage 7: Agent-native Delivery

The running agent reads the saved prompt and writes the final digest prose directly into the active chat. No code invocation — the agent is the synthesis engine.

---

## Data Flow

```
RawEvent → Dedup → CategorizedEvent → Signal → ReinforcedSignal → ChainDigest → Prompt
```

Persistence points (all atomic via `safe_text_write` / `safe_json_write`):

| Artifact | Path | Purpose |
|----------|------|---------|
| Raw events | `storage/events/<id>.json` | Reinforcer reloads on restart |
| Health log | `storage/health/run_*.json` | Per-run stats + timing |
| Metrics | `storage/metrics/metrics.jsonl` | `PipelineMetrics` telemetry |
| Agent prompt | `storage/agent_input/daily_prompt_*.md` | Prompt for agent synthesis |
| Daily digest | `storage/daily_digests/daily_digest_*.md` | Weekly builder input |

---

## Concurrency & Resource Budget

| Stage | Concurrency | Bottleneck | Mitigation |
|-------|-------------|------------|------------|
| Collect | asyncio.gather + `ProcessPoolExecutor` for Twitter | API rate limits | Configured semaphore + batching |
| Dedup | Single-threaded (O(n)) | None | None |
| Score | Single-threaded (O(n)) | None | None |
| Reinforce | Single-threaded | Disk I/O | FileLock on signal storage |
| Analyze | asyncio.gather | Data volume | Deterministic, fast |
| Synthesize | Single-threaded | Disk write | Instant |
| Deliver | Agent-native (chat) | None | Prompt persisted for retry |

Steam Deck-specific constraints enforced in `config/pipeline.yaml`:

- `memory_throttle_mb: 500` — when `<500MB` free, concurrency drops to 2
- Twitter lite profile copy — excludes `GPUCache`, `blob_storage`, `Code Cache`, `IndexedDB`, etc.
- Chrome process cleanup: `pkill -9 chrome` pre-run if zombies detected

---

## Extension Points

- **Add collector:** subclass `BaseCollector`, implement `collect()`, add to `main.py` collector list
- **Add chain:** `scripts/chain_monitor_cli.py chains add <name>` or edit `config/chains.yaml`
- **Change prompt:** edit `processors/summary_engine.py` `_build_daily_prompt()`
- **Change scoring:** edit `processors/scoring.py`
- **Add event category:** update `processors/categorizer.py` `CATEGORY_KEYWORDS`

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | 7-stage pipeline orchestrator |
| `processors/parallel_runner.py` | `collect_all()` async gather |
| `processors/dedup_engine.py` | O(n) hash dedup |
| `processors/scoring.py` | Rule-based signal scoring |
| `processors/reinforcement.py` | Cross-source signal merge |
| `processors/chain_analyzer.py` | Per-chain digest building |
| `processors/summary_engine.py` | Markdown prompt builder |
| `processors/agent_runner.py` | Prompt persister (agent-native only) |
| `collectors/twitter_collector.py` | Playwright-based extraction with ProcessPoolExecutor |
| `config/pipeline.yaml` | Centralized tunables (workers, thresholds, retention) |
| `scripts/chain_monitor_cli.py` | Management CLI for chains, cron, digest, health |

---

## Agent-Native Synthesis Budget

No external LLM calls during pipeline execution. Token count: zero.

- Stage 0–5: pure computation, no tokens
- Stage 6: prompt written to disk (zero tokens consumed by pipeline)
- Stage 7: the running agent synthesizes prose independently

Prompt sizes for context sizing:

- Daily: ~5-15K chars per active chain
- Weekly: up to 200K chars of digest text (truncated by builder)
