# Chain Monitor

Multi-chain crypto intelligence pipeline. Monitors 27 blockchain ecosystems across 6 event categories, scores signals, and structures daily/weekly digests for agent-native prose synthesis.

The running agent is the only reasoning engine in the loop: it reads the generated prompt and writes the final digest prose directly into the active chat. No external LLM calls. No Telegram bot.

---

## Pipeline (7 stages)

1. **Parallel Collect** — 9 collectors run concurrently via `asyncio.gather`
2. **Dedup** — O(n) hash-based deduplication
3. **Categorize** — source-provided categories with deterministic keyword fallback
4. **Score + Reinforce** — rule-based heuristics merge similar signals across sources
5. **Per-chain Analyze** — deterministic analysis builds `ChainDigest` objects
6. **Agent Prompt Synthesis** — structured markdown prompt saved to `storage/agent_input/`
7. **Agent-native Delivery** — running agent reads prompt and writes prose

---

## Quick Start

```bash
cd chain-monitor

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium

# Setup .env (data source API keys only; no LLM config needed)
python3 scripts/setup.py

# Health check
python3 scripts/doctor.py

# Run the full pipeline
python3 main.py

# With resource profiling
python3 scripts/chain_monitor_cli.py digest --preview

# Install daily cron at 9am UTC
python3 scripts/chain_monitor_cli.py cron install --hour 9

# Run tests
python3 -m pytest tests/ -q
```

---

## Structure

| Directory | Purpose |
|-----------|---------|
| `collectors/` | 9 data ingestors: RSS, Twitter, DefiLlama, GitHub, regulatory, etc. |
| `processors/` | Dedup, scoring, reinforcement, chain analysis, prompt synthesis |
| `output/` | Weekly digest builder (reads 7 days of persisted daily prompts) |
| `config/` | `chains.yaml`, `baselines.yaml`, `sources.yaml`, `pipeline.yaml` |
| `scripts/` | `setup.py`, `doctor.py`, `chain_monitor_cli.py` |
| `storage/` | Events, health logs, narrative history, agent prompts |

---

## Collectors

| Collector | Source | Signals |
|-----------|--------|---------|
| DefiLlama | TVL, fees, volume | FINANCIAL |
| CoinGecko | Price, market cap anomalies | FINANCIAL |
| GitHub | Version tags, PRs, EIPs | TECH_EVENT |
| RSS | 80+ feeds across 27 chains | All categories |
| Regulatory | SEC EDGAR, policy | REGULATORY |
| Risk Alert | Hack/vulnerability feeds | RISK_ALERT |
| TradingView | News flow via Playwright | All categories |
| Events | Conferences, hackathons | VISIBILITY |
| Twitter | 138 chain accounts via Playwright | All categories |

---

## Configuration

`config/pipeline.yaml` holds all tunable constants (workers, thresholds, retention). `config/loader.py` reads YAML + `.env` with sensible defaults. No hardcoded values in Python.

Key env vars (`.env`):

```
LOG_LEVEL=INFO
DATA_RETENTION_DAYS=90
TWITTER_MAX_WORKERS=15
TWITTER_NUM_BATCHES=10
TWITTER_LOOKBACK_HOURS=24

# Optional data source keys
COINGECKO_API_KEY=***
YOUTUBE_API_KEY=***
GITHUB_TOKEN=***
```

---

## Agent-Native Delivery

The pipeline writes a structured Markdown prompt (`storage/agent_input/daily_prompt_*.md`) containing:

- Per-chain event summaries with URLs
- Source health report
- Cross-chain theme prompt

The running agent reads this file and produces the final digest prose directly in chat. Zero external LLM dependencies. Zero Telegram bot.

---

## Testing

```bash
python3 -m pytest tests/ -q
```

254 tests cover unit, integration, system, and regression suites.

---

## License

MIT
