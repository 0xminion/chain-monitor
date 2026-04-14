# Chain Monitor

Multi-chain strategic intelligence system. Monitors 27 blockchain chains across 7 event categories, scores events, detects narratives, and delivers daily/weekly digests to Telegram.

## Quick Start

```bash
cd chain-monitor

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium

# Install Camoufox (anti-detect browser for Cloudflare-protected sites)
camoufox fetch

# Edit .env with your API keys
cp .env.example .env
nano .env

# Run a collection cycle
python3 main.py
```

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

## Architecture

```
collectors/     → Data ingestion (8 collectors)
processors/     → Categorizer, scorer, reinforcer, narrative tracker
output/         → Digest formatting and Telegram delivery
config/         → YAML configuration
storage/        → Event data, health logs, narrative history
scripts/        → Setup and verification scripts
tests/          → Unit, integration, system tests
```

## Collectors

| Collector | Source | Method | Signals |
|-----------|--------|--------|---------|
| DefiLlama | TVL, fees, volume, protocol attribution | REST API | FINANCIAL |
| CoinGecko | Price, market cap anomalies | REST API | FINANCIAL |
| GitHub | Version tags, high-signal PRs, EIP descriptions | REST API | TECH_EVENT |
| RSS | 11 news feeds + 54 chain blog feeds + 13 podcast feeds | RSS/Atom | All categories |
| Regulatory | SEC EDGAR filings, CoinCenter policy | RSS | REGULATORY |
| Risk Alert | DeFiLlama hacks, TVL crashes, Immunefi | REST API | RISK_ALERT |
| TradingView | News flow from 16+ providers | Playwright (Chromium) | All categories |
| Events | ethereum.org conferences, ETHGlobal hackathons | Camoufox (anti-detect) | VISIBILITY |

## Event Categories

| Category | What It Captures | Sources |
|----------|-----------------|---------|
| Tech event | Mainnet launches, upgrades, releases, EIPs, audits | GitHub, RSS, TradingView |
| Partnership | Integrations, collaborations, deployments, co-launches | RSS keyword matching, TradingView |
| Regulatory | SEC filings, licenses, approvals, bans, enforcement | SEC EDGAR, CoinCenter, RSS, TradingView |
| Risk alert | Hacks, exploits, outages, critical bugs | DeFiLlama, RSS, TradingView |
| Visibility | Conferences, hackathons, AMAs, hires, departures | ethereum.org, ETHGlobal, RSS, TradingView |
| Financial | TVL milestones, volume spikes, funding, airdrops, TGEs | DefiLlama, CoinGecko, RSS, TradingView |
| News | General crypto news without specific chain attribution | RSS keyword matching |
| AI narrative | AI agent activity, LLM integrations | RSS keyword matching |

## Data Sources Detail

### Financial
- **DefiLlama**: TVL per chain (with top protocol attribution), fees, revenue, stablecoin flows
- **CoinGecko**: Price, market cap anomaly detection

### Technical
- **GitHub**: Version tags (major releases only), high-signal PRs (EIPs, security, breaking changes)
- **EIP context**: Auto-fetches EIP descriptions and release notes from GitHub

### News & Events
- **RSS feeds**: CoinDesk, The Block, Cointelegraph, NewsBTC, 99Bitcoins, Decrypt, Blockworks, CryptoSlate, CoinGape, Bitcoin.com, AMBCrypto
- **Chain blog feeds (68 total)**: Each chain may publish via blog, Medium, Substack, or podcast — all sources are checked independently (peer-level, no fallback hierarchy)
- **Podcast feeds (13 total)**: Bankless, Unchained, What Bitcoin Did, Lightspeed, The Defiant, The Scoop, Empire, 0xResearch, Bell Curve, Tales from the Crypt, Thinking Crypto, Week in Ethereum, The Breakdown
- **TradingView**: Playwright scraper for crypto news flow (bypasses JS rendering)
- **ethereum.org**: 38+ upcoming conferences with dates, locations, tags (Camoufox anti-detect)
- **ETHGlobal**: Hackathons, meetups, conferences (Camoufox anti-detect)

### Regulatory
- **SEC EDGAR**: Recent filings for crypto-related entities
- **CoinCenter**: Policy analysis and developer rights advocacy
- **DeFi Education Fund**: Legislative tracking

### Risk
- **DeFiLlama hacks**: Known hack incidents
- **TVL crashes**: Automated detection of >15% TVL drops
- **Immunefi**: Bug bounty and vulnerability disclosures

## Scoring

Every event gets an **Impact** (1-5) × **Urgency** (1-3) = **Priority Score**.

| Score | Delivery |
|-------|----------|
| ≥10 | Immediate Telegram alert |
| 6-9 | Daily digest |
| 3-5 | Weekly report |
| <3 | Log only |

Thresholds are per-chain (configurable in baselines.yaml).

## Keyword Matching (Partnership & Visibility)

The categorizer uses expanded keyword sets to catch announcements from RSS/TradingView:

**Partnership keywords**: partnership, partners with, integration, deployed on, live on, launches on, available on, adds support for, expands to, migrates to, built on, powered by, alliance, consortium, strategic, ecosystem partner

**Visibility keywords**: conference, hackathon, ama, keynote, speaker, podcast, live stream, community call, new ceo/cto, hired, appointed, resigned, stepped down

## Telegram Delivery

Digests are sent via Telegram Bot API using **Markdown** parse mode with clickable `[Title](URL)` links embedded on signal titles.

- Links must be Markdown format: `[Title](URL)` — never HTML `<a>` tags (Telegram doesn't render them)
- No price/financial content in digests
- Partnerships shown as separate section
- Only major releases with release notes in tech events

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

## API Keys Required

| Key | Cost | Where to Get |
|-----|------|-------------|
| CoinGecko | Free (30 req/min, 10K/mo) | coingecko.com/api |
| GitHub Token | Free (5000 req/hr) | github.com/settings/tokens |
| Telegram Bot | Free | @BotFather |
