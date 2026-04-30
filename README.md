# Chain Monitor

Multi-chain strategic intelligence system. Monitors 27 blockchain chains across 9 event categories, scores events, synthesizes per-chain narratives, and delivers daily/weekly digests to Telegram.

## v2.0 — Agent-Native by Default

The pipeline now runs entirely deterministically within your agent. No external LLM APIs, no subprocess calls, no tokens.

1. **Parallel Collect** — all 10 collectors run concurrently via `asyncio.gather()`
2. **Dedup** — O(n) hash-based deduplication (URL + fingerprint index)
3. **Categorize + Score** — deterministic keyword categorization + rule-based scoring
4. **Per-chain analyze** — deterministic heuristics merge signals, assign priorities, generate summaries
5. **Digest synthesize** — structured template formatting (prose for ≥2, bullets for <2). Markdown links embedded on first word.
6. **Weekly synthesize** — Reads 7 days of persisted daily digests, produces deterministic weekly brief
7. **Deliver** — Telegram send + run log + daily digest persistence

### What's New in v2.0

- **Agent-native by default**: No LLM keys, no Ollama server, no OpenRouter tokens. Clone and run.
- **No external API dependency**: All analysis, categorization, and synthesis is deterministic Python.
- **Deterministic outputs**: Same inputs → same digest, every time. No LLM temperature drift.
- **Keyword-only enrichment**: Replaced batched LLM semantic enrichment with deterministic keyword matching.
- **Zero-cost operation**: No per-token costs, no rate limits, no fallback model juggling.
- **Per-chain narrative**: Heuristic merging of cross-source signals into coherent observations.
- **Parallel everything**: Collectors and chain analyzers both run concurrently.
- **O(n) dedup**: Single-pass hash dedup replaces the old O(n*m) text similarity loop.
- **Markdown links on first word**: Evidence-backed hyperlinks embedded via `[Word](URL)` format.
- **Management CLI**: `scripts/chain_monitor_cli.py` for chains, cron, digest, health.
- **Setup wizard**: `scripts/setup.py` interactive `.env` generator.
- **Doctor**: `scripts/doctor.py` end-to-end health check with auto-fix hints.

## Quick Start

```bash
cd chain-monitor

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for Twitter/TradingView scraping)
python -m playwright install chromium

# Install Camoufox (anti-detect browser for Cloudflare-protected sites)
camoufox fetch

# Interactive setup (creates .env, checks Telegram)
python3 scripts/setup.py

# Edit .env with your API keys (only Telegram + optional data source keys)
cp .env.example .env
nano .env

# Health check
python3 scripts/doctor.py

# Run the full pipeline (daily digest)
python3 main.py

# Run the v2 Twitter-centric digest (raw tweets → events → analyze → digest)
python3 scripts/run_stored_reanalysis.py

# Run the weekly digest
python3 scripts/run_weekly_digest.py

# Full pipeline for all 27 chains
python3 scripts/run_all_chains.py

# Dry-run digest (no Telegram, print to stdout)
python3 scripts/chain_monitor_cli.py digest --dry-run --preview

# Install daily cron at 9am UTC
python3 scripts/chain_monitor_cli.py cron install --hour 9

# Run tests
python3 -m pytest tests/ -q
```

### What You Need

| Requirement | Required? | Cost | Why |
|-----------|-----------|------|-----|
| Telegram Bot Token | **Yes** | Free | @BotFather — only required delivery channel |
| CoinGecko API Key | No | Free | Price/MCAP data |
| GitHub Token | No | Free | Version tags, high-signal PRs |
| LLM provider | **No** | N/A | v2.0 is fully agent-native |

## Architecture

```
collectors/     → Data ingestion (10 collectors)
processors/     → Categorizer, scorer, reinforcer, chain analyzer (agent-native)
output/         → Digest formatting and Telegram delivery
config/         → YAML configuration
storage/        → Event data, health logs, narrative history
scripts/        → Setup and verification scripts
tests/          → Unit, integration, system tests
```

### Pipeline Stages (Agent-Native)

| Stage | Module | What It Does |
|-------|--------|-------------|
| 1. Collect | `processors/parallel_runner.py` | `asyncio.gather()` across all 10 collectors |
| 2. Dedup | `processors/dedup_engine.py` | O(n) hash-based deduplication |
| 3. Categorize | `processors/categorizer.py` | Keyword matching across CATEGORY_KEYWORDS |
| 4. Score | `processors/scoring.py` | Impact × Urgency = Priority (1-15) |
| 5. Chain Analyze | `processors/chain_analyzer.py` | Deterministic merge, priority, narrative |
| 6. Digest | `processors/summary_engine.py` | Structured template output |
| 7. Deliver | `output/telegram_sender.py` | Telegram Bot API |

### The `processors/chain_analyzer.py` Heuristic Engine

Instead of LLM calls, chain analysis uses:

- **Keyword category priority table**: RISK_ALERT (15) > REGULATORY (12) > FINANCIAL (10) > PARTNERSHIP (7) > TECH_EVENT (6) > VISIBILITY (3)
- **Subcategory scoring**: Fine-grained weights per subcategory (hack=15, mainnet_launch=6, keynote=3, etc.)
- **Trading noise filter**: Price predictions, TA, and memes get 70% score penalty
- **Trigram merge**: Events sharing ≥2 trigrams or same subcategory are merged into one observation
- **Multi-source bonus**: Confidence scales with number of distinct sources confirming an event
- **Narrative templates**: Category-specific "why it matters" reasoning (e.g. "Regulatory developments often move markets...")

### Categorizer Keyword Maps

The categorizer matches against comprehensive keyword lists:

- **RISK_ALERT**: hack, exploit, outage, vulnerability, breach, drained, stolen, attack
- **REGULATORY**: SEC, enforcement, lawsuit, ban, license, approval, compliance, fine
- **FINANCIAL**: TVL, funding, raised, airdrop, TGE, grant, milestone
- **PARTNERSHIP**: partnership, integration, deployed on, live on, collaboration
- **TECH_EVENT**: upgrade, mainnet, testnet, release, EIP, hard fork, governance
- **VISIBILITY**: conference, hackathon, keynote, hired, CEO, podcast, demo day

Twitter-specific expansions catch colloquial phrases: "wen mainnet" → VISIBILITY, "v2 is here" → TECH_EVENT, "now live on" → PARTNERSHIP.

## Configuration

All configuration is YAML-based. No code changes needed to add/remove chains or narratives.

| File | Purpose |
|------|---------|
| `config/chains.yaml` | 27 chain definitions, data sources, GitHub repos |
| `config/baselines.yaml` | Per-chain scoring thresholds |
| `config/narratives.yaml` | Narrative categories and keywords |
| `config/sources.yaml` | RSS feeds, API endpoints, TradingView config |

### Adding a New Chain

1. Add entry to `config/chains.yaml`:
```yaml
newchain:
  category: "high_tps"
  tier: 3
  coingecko_id: "newchain"
  defillama_slug: "newchain"
  github_repos:
    - "newchain-org/newchain"
  blog_rss: "https://newchain.io/blog/rss.xml"
```

2. Add baseline to `config/baselines.yaml`:
```yaml
newchain:
  tvl_absolute_milestone: 100000000
  tvl_change_notable: 25
  tvl_change_spike: 50
  regulatory_sensitivity: "LOW"
```

## Collectors

| Collector | Source | Method | Signals |
|-----------|--------|--------|---------|
| DefiLlama | TVL, fees, volume, protocol attribution | REST API | FINANCIAL |
| CoinGecko | Price, market cap anomalies | REST API | FINANCIAL |
| GitHub | Version tags, high-signal PRs, EIP descriptions | REST API | TECH_EVENT |
| RSS | 11 news feeds + 68 chain blog feeds + 13 podcasts | RSS/Atom | All categories |
| Regulatory | SEC EDGAR filings, CoinCenter policy | RSS | REGULATORY |
| Risk Alert | DeFiLlama hacks, TVL crashes, Immunefi | REST API | RISK_ALERT |
| TradingView | News flow from 16+ providers | Playwright (Chromium) | All categories |
| Events | ethereum.org conferences, ETHGlobal hackathons | Camoufox (anti-detect) | VISIBILITY |
| Twitter/X | 138 handles across 28 chains | Playwright | All categories |

## Event Categories

| Category | What It Captures | Sources |
|----------|-----------------|---------|
| Tech event | Mainnet launches, upgrades, releases, EIPs, audits | GitHub, RSS, TradingView |
| Partnership | Integrations, collaborations, deployments, co-launches | RSS, TradingView |
| Regulatory | SEC filings, licenses, approvals, bans, enforcement | SEC EDGAR, CoinCenter, RSS |
| Risk alert | Hacks, exploits, outages, critical bugs | DeFiLlama, RSS, TradingView |
| Visibility | Conferences, hackathons, AMAs, hires, departures | ethereum.org, ETHGlobal, RSS |
| Financial | TVL milestones, volume spikes, funding, airdrops, TGEs | DefiLlama, CoinGecko, RSS |
| News | General crypto news without specific chain attribution | RSS |
| AI narrative | AI agent activity, LLM integrations | RSS |

## Scoring

Every event gets an **Impact** (1-5) × **Urgency** (1-3) = **Priority Score**.

| Score | Delivery |
|-------|----------|
| ≥10 | Immediate Telegram alert |
| 6-9 | Daily digest |
| 3-5 | Weekly report |
| <3 | Log only |

Thresholds are per-chain (configurable in baselines.yaml).

## Data Retention

- Raw events: 90 days
- Aggregated metrics: 90 days
- Weekly reports (narrative history): 90 days

## Testing

```bash
python3 -m pytest tests/
python3 -m pytest tests/unit/
python3 -m pytest tests/ --cov=collectors --cov=processors --cov=output
```

## FAQ

**Q: Can I still use an LLM if I want?**
A: The `processors/llm_client.py` module is still present for optional external use, but the pipeline no longer calls it. To re-enable LLM enrichment, modify `processors/semantic_enricher.py` to instantiate `LLMClient()`.

**Q: Is the output worse without an LLM?**
A: For the daily digest use case, LLMs were primarily used for prose generation. The agent-native template writes clear, structured summaries with proper markdown links. The categorization was already keyword-based; removing LLM semantic enrichment eliminates false positives from LLM hallucinations and ensures deterministic, reproducible results.

**Q: What about creative weekly synthesis?**
A: The weekly digest still produces thematic summaries, but via deterministic parsing of daily digests rather than LLM synthesis. Chains are grouped by activity volume, and individual signals carry through with links preserved.
