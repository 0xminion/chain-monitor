# Chain Monitor — Architecture

**Version:** v1.0  
**Last updated:** May 2026

---

## Pipeline

```
Collect (async parallel)
  │ 9 collectors + composable Twitter provider
  │
  v
Categorize (keyword-based)
  │ RISK_ALERT → REGULATORY → FINANCIAL → PARTNERSHIP → TECH_EVENT → VISIBILITY
  │
  v
Score (deterministic)
  │ Impact 1-5 × Urgency 1-3 → priority_score
  │ Twitter gets urgency boost (min +1)
  │
  v
Reinforce (dedup)
  │ URL match → merge activity entries
  │ Text similarity (Jaccard ≥ 0.6) → merge
  │ Echo detection (≥0.85 sim, ≥3 sources) → drop
  │
  v
Group by chain → sort by signal count
  │
  v
Summarize (Ollama: gemma4:31b-cloud)
  │ Per-chain prose with inline [text](url) markdown links
  │
  v
Deliver
  ├─ daily_digest_latest.md (disk)
  ├─ signal_bundle.json (structured, for cron agent synthesis)
  └─ Telegram (optional, if bot token configured)
```

---

## Twitter Architecture (`collectors/twitter/`)

Composable provider pattern. Swap backends by setting `XSEARCH_PROVIDER` env var.

```
collectors/twitter/
├── provider.py                  XSearchProvider (abstract base)
├── direct_xai.py                DirectXAIProvider (api.x.ai)
├── antseed_provider.py          AntseedBuyerProvider (P2P proxy)
├── surplus_provider.py          SurplusIntelligenceProvider (Grok + x402)
├── surplus_twitter_provider.py  SurplusTwitterProvider (Twitter API v2 via x402) ← DEFAULT
├── collector.py                 TwitterCollector (batches, converts to events)
└── token_tracker.py             PipelineTokenTracker
```

**Collection flow:**
1. `config/twitter_accounts.yaml` → 138 handles across 27 chains
2. Batch into groups of ≤10 (X API hard cap) → 14 batches
3. Launch tasks with 300ms stagger (avoids Vercel DDoS protection on surplusintelligence.ai)
4. Provider returns `SearchResult(tweets, usage)`
5. `_tweets_to_events()` converts to pipeline event dicts with `source: "twitter"`, X URLs, role metadata

**Retry + Backoff:** SurplusTwitterProvider retries Vercel 403 "Security Checkpoint" with exponential backoff (2s/4s/8s) and re-attempts x402 payment on 402.

**Cost:** $0.0275/call × 14 batches = ~$0.39/run (SurplusTwitterProvider default)

---

## Scoring

### Impact (1-5)

| Category | Subcategory | Impact |
|----------|-------------|--------|
| RISK_ALERT | hack > $10M | 5 |
| RISK_ALERT | hack/exploit/outage/critical_bug | 4 |
| RISK_ALERT | default | 3 |
| REGULATORY | enforcement | 5 |
| REGULATORY | license/approval | 4 |
| REGULATORY | comment_period | 3 |
| FINANCIAL | tvl_milestone | 4 |
| FINANCIAL | tvl_spike ≥ 25% | 4 |
| FINANCIAL | funding ≥ $50M | 4 |
| TECH_EVENT | mainnet_launch | 5 |
| TECH_EVENT | upgrade | max(floor, 4) |
| TECH_EVENT | governance_passed | 4 |
| PARTNERSHIP | tier 1 | 4 |
| VISIBILITY | keynote/hire/departure | 3 |

### Urgency (1-3)

- RISK_ALERT (hack/exploit/outage) → 3
- REGULATORY (enforcement) → 3
- High-impact FINANCIAL/TECH_EVENT (impact ≥ 4) → 2
- governance_vote → 2
- **Twitter boost**: all Twitter signals get min urgency 2; founder/lead/cto roles or ≥500 likes → urgency 3
- Default → 1

---

## Summarizer (`output/summarizer.py`)

Calls local Ollama at `SUMMARIZE_API_URL` (default `http://localhost:11434/v1`) with model `SUMMARIZE_MODEL` (default `gemma4:31b-cloud`).

**Prompt**: Rich instruction set + per-signal `[description](url)` lines. Model returns 2-4 sentence prose with inline markdown links. Zero token cost (local inference).

**Concurrency**: All chains summarized in parallel via `asyncio.gather`.

---

## Persistence

| Artifact | Path | Format |
|----------|------|--------|
| Signal events | `storage/events/<id>.json` | Signal.to_dict() |
| Run log | `storage/health/run_*.json` | Stats + timing |
| Raw tweets | `storage/twitter/raw/tweets_*.json` | List of tweet dicts |
| Daily digest | `storage/twitter/summaries/daily_digest_latest.md` | Markdown prose |
| Signal bundle | `storage/twitter/summaries/signal_bundle.json` | Structured, for cron |
| Twitter summary | `storage/twitter/summaries/twitter_summary_*.md` | Monthly markdown |

---

## Key Design Decisions

1. **Composable Twitter over browser scraping.** Subprocess Camoufox workers were replaced with API providers. Real tweet IDs, real metrics, no login walls, no memory leaks.

2. **Ollama summarizer over antseed buyer.** Zero-cost local inference for per-chain prose. Env-swappable endpoint. Prompt cached and deterministic (temperature=0).

3. **Every chain gets its own block.** No "Additional signals" group. No score gate. Every chain renders identically regardless of tweet count.

4. **Signal bundle for cron.** Pipeline saves structured JSON alongside prose digest. Cron agent reads bundle and synthesizes independently — no need to re-run collectors.

5. **Keyword-based categorization over agent-native checkpoint.** The agent-native `prepare_agent_task()` → `try_load_results()` → `apply_categories()` loop was replaced with direct `categorize()` that uses `CATEGORY_KEYWORDS` and `SUBCATEGORY_MAP` (lists, not strings).
