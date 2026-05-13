# Chain Monitor

Multi-chain crypto intelligence pipeline. Monitors 27 blockchain ecosystems across 6 event categories with [composable Twitter X Search providers](collectors/twitter/), deterministic scoring, and Ollama-powered per-chain prose synthesis.

## Pipeline (7 stages)

1. **Parallel Collect** — 9 collectors (incl. composable Twitter) run concurrently via `asyncio.gather`
2. **Categorize** — keyword-based classification (RISK_ALERT, REGULATORY, FINANCIAL, PARTNERSHIP, TECH_EVENT, VISIBILITY)
3. **Score** — deterministic impact/urgency scoring with Twitter urgency boost
4. **Reinforce** — cross-source signal deduplication (URL + text similarity)
5. **Per-chain Grouping** — signals bucketed by chain, sorted by count
6. **Prose Synthesis** — [Ollama summarizer](output/summarizer.py) (`gemma4:31b-cloud`) generates per-chain prose with markdown `[text](url)` links
7. **Deliver** — digest saved to disk + optional Telegram delivery

## Quick Start

```bash
cd chain-monitor
pip install -r requirements.txt

# Configure .env (see below)
cp .env.example .env
# Edit .env with your keys

# Run the pipeline
python3 main.py

# Run tests
python3 -m pytest tests/ -q
```

## Twitter Collection

Twitter uses a **composable provider architecture** under `collectors/twitter/`. The default provider is [SurplusTwitterProvider](collectors/twitter/surplus_twitter_provider.py) — direct Twitter API v2 via x402 micropayment at $0.0275/call.

**14 batches × 10 handles** (X API cap) for 138 monitored accounts. Providers are swappable via `XSEARCH_PROVIDER` env var:

| Provider | Backend | Cost/run |
|----------|---------|----------|
| `surplus_twitter` *(default)* | Twitter API v2 via x402 | ~$0.39 |
| `direct_xai` | xAI X Search API | ~$0.07 |
| `antseed_buyer` | Antseed P2P proxy | ~$0.10 |
| `surplus_intelligence` | Grok 2-step tool-calling | ~$0.10 |

## Structure

| Directory | Purpose |
|-----------|---------|
| `collectors/` | 9 data ingestors: RSS, Twitter, DefiLlama, CoinGecko, TradingView, Events, Hackathon Outcomes, Regulatory, Risk Alert |
| `collectors/twitter/` | Composable X Search providers + collector + token tracker |
| `processors/` | Categorizer, scorer, reinforcer, signal model, narrative tracker |
| `output/` | Daily digest formatter, [summarizer](output/summarizer.py), weekly digest, Telegram sender |
| `config/` | `chains.yaml`, `twitter_accounts.yaml`, `baselines.yaml`, `sources.yaml`, `pipeline.yaml` |
| `scripts/` | Setup, doctor, exports |
| `storage/` | Events, health logs, narrative history, raw tweets, digest output |

## Configuration

Key env vars (`.env`):

```
LOG_LEVEL=INFO
DATA_RETENTION_DAYS=90
XSEARCH_PROVIDER=surplus_twitter

# Ollama summarizer
SUMMARIZE_API_URL=http://localhost:11434/v1
SUMMARIZE_MODEL=gemma4:31b-cloud

# API keys (optional per collector)
COINGECKO_API_KEY=...
CRYPTORANK_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

## Digest Format

Per-chain prose with inline source links:

```
**Ethereum** (Score: 12)
[Clear signing went live](https://blog.ethereum.org/...) — an open ERC-7730
standard to end blind signing. The [CLARITY Act markup](https://decrypt.co/...)
was scheduled by the Senate Banking Panel.

**Solana** (Score: 8)
[Alpenglow upgrade began testing](https://decrypt.co/...) ahead of full rollout.
[Beezie expanded tokenized collectibles](https://x.com/solana/status/...) to Solana.
```

## Testing

```bash
python3 -m pytest tests/ -q
```

200+ tests covering unit, integration, and system suites.

## License

MIT
