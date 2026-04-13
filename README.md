# Chain Monitor

Multi-chain strategic intelligence system. Monitors 30 blockchain chains across 6 event categories, scores events, detects narratives, and delivers daily/weekly digests to Telegram.

## Quick Start

```bash
# Clone and enter
cd chain-monitor

# Run setup (creates venv, installs deps, verifies sources)
bash scripts/setup.sh

# Edit .env with your API keys
nano .env

# Verify all data sources
python3 scripts/verify_sources.py

# Run a collection cycle
python3 main.py
```

## Configuration

All configuration is YAML-based. No code changes needed to add/remove chains or narratives.

| File | Purpose |
|------|---------|
| `config/chains.yaml` | Chain definitions, data sources, governance forums |
| `config/baselines.yaml` | Per-chain scoring thresholds |
| `config/narratives.yaml` | Narrative categories and keywords |
| `config/sources.yaml` | Global RSS feeds, API endpoints |

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
  youtube_channel: "@NewChain"
  status_page: null
  governance_forum:
    url: "https://gov.newchain.io"
    type: "discourse"
```

2. Add baseline to `config/baselines.yaml`:
```yaml
newchain:
  tvl_absolute_milestone: 100000000
  tvl_change_notable: 25
  tvl_change_spike: 50
  regulatory_sensitivity: "LOW"
  upgrade_impact_floor: 3
  trader_context_notes: "Early stage. Watch for ecosystem growth."
```

3. Run `python3 scripts/verify_sources.py` to verify

### Adding a New Narrative

Add to `config/narratives.yaml`:
```yaml
narratives:
  new_narrative:
    name: "New Narrative"
    keywords:
      - "keyword1"
      - "keyword2"
    description: "Description of this narrative theme"
```

## Architecture

```
collectors/     → Data ingestion (DefiLlama, CoinGecko, GitHub, RSS, scraping)
processors/     → Event processing (categorizer, scorer, reinforcer, narrative tracker)
output/         → Digest formatting and Telegram delivery
config/         → YAML configuration files
storage/        → Event data, health logs, narrative history
scripts/        → Setup and verification scripts
tests/          → Unit, integration, system tests
```

## Data Sources

| Category | Sources |
|----------|---------|
| Financial | DefiLlama (TVL, fees, volume), CoinGecko (price, mcap) |
| Tech Events | GitHub API (releases, commits), chain blog RSS |
| Governance | Discourse forums, GitHub proposal repos |
| News | CoinDesk, The Block, CoinTelegraph RSS |
| Regulatory | SEC EDGAR, CoinCenter, legal blog RSS |
| Risk | DeFiLlama hacks, Rekt News, GitHub issues |
| Visibility | YouTube API, podcast RSS, CryptoRank events |
| Scraping | Hyperliquid announcements, OKX announcements (Camoufox) |

## Event Categories

| Category | What It Captures |
|----------|-----------------|
| TECH_EVENT | Upgrades, releases, audits, governance proposals |
| PARTNERSHIP | Integrations, collaborations, co-launches |
| REGULATORY | Licenses, approvals, bans, enforcement |
| RISK_ALERT | Hacks, exploits, outages, critical bugs |
| VISIBILITY | Conferences, AMAs, hires, departures |
| FINANCIAL | TVL milestones, volume spikes, funding rounds |

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

- Raw events: 180 days (6 months)
- Aggregated metrics: 180 days
- Weekly reports: indefinite
- Run logs: 180 days

## Testing

```bash
# Run all tests
python3 -m pytest tests/

# Run unit tests only
python3 -m pytest tests/unit/

# Run with coverage
python3 -m pytest tests/ --cov=collectors --cov=processors --cov=output
```

## API Keys Required

| Key | Cost | Where to Get |
|-----|------|-------------|
| CoinGecko | Free (30 req/min, 10K/mo) | coingecko.com/api |
| CryptoRank | Free (Core tier) | cryptorank.io/public-api/pricing |
| YouTube Data API v3 | Free (10K units/day) | console.cloud.google.com |
| Telegram Bot | Free | @BotFather |
| GitHub Token | Free (5000 req/hr) | github.com/settings/tokens |
