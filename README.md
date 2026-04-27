# Chain Monitor

Multi-chain strategic intelligence system. Monitors 27 blockchain chains across 8 event categories, scores events, synthesizes per-chain narratives via LLM, and delivers daily/weekly digests to Telegram.

## v2.0 — Chain-Centric LLM Synthesis

The pipeline now treats every chain as a unit of intelligence:

1. **Parallel Collect** — all 10 collectors run concurrently via `asyncio.gather()`
2. **Dedup** — O(n) hash-based deduplication (URL + fingerprint index)
3. **Categorize + Score** — keyword categorization + rule-based scoring (backward compatible)
4. **Per-chain LLM analyze** — 27 parallel LLM calls, each merges related signals into coherent observations
5. **Digest synthesize** — LLM prose for chains scoring ≥5, structured bullets for <5
6. **Deliver** — Telegram send + run log

### What's New in v2.0

- **Per-chain narrative**: Instead of raw signal bullets, the digest tells you *"Solana is pushing v2.3 with performance gains — watch for downstream DeFi migrations."*
- **Cross-source merging**: GitHub release + tweet + blog post about the same event = ONE merged observation with multiple sources
- **Parallel everything**: Collectors and chain analyzers both run concurrently
- **O(n) dedup**: Single-pass hash dedup replaces the old O(n*m) text similarity loop
- **Management CLI**: `scripts/chain_monitor_cli.py` for chains, cron, digest, health
- **Setup wizard**: `scripts/setup.py` interactive `.env` generator with LLM validation
- **Doctor**: `scripts/doctor.py` end-to-end health check with auto-fix hints

## Quick Start

```bash
cd chain-monitor

# Interactive setup (creates .env, validates LLM, checks Telegram)
python3 scripts/setup.py

# Health check
python3 scripts/doctor.py

# Run the full pipeline
python3 main.py

# Dry-run digest (no Telegram, print to stdout)
python3 scripts/chain_monitor_cli.py digest --dry-run --preview

# Install daily cron at 9am UTC
python3 scripts/chain_monitor_cli.py cron install --hour 9

# Run tests
python3 -m pytest tests/ -q
```

Chain Monitor uses local LLM inference (Ollama) for capabilities:

### 1. Per-Chain Semantic Analysis (v2.0)
Each chain gets an LLM analysis of all its signals:
- **Cross-source merging**: GitHub release + tweet + blog post about same event = ONE observation
- **Event classification**: TECH_EVENT, PARTNERSHIP, FINANCIAL, RISK_ALERT, REGULATORY, VISIBILITY
- **Priority scoring**: Chain-level score 0-15 based on highest-impact observation + cross-reinforcement
- **Trader narrative**: 2-3 sentence summary of WHY it matters, not just WHAT happened
- **Confidence score**: How certain the LLM is, driven by source count and agreement

### 2. Twitter Semantic Enrichment (v0.2+)
Every tweet, retweet, and quote-tweet is enriched with semantic understanding:
- **LLM categorization**: Categories assigned by semantic content, not keywords
  - Handles slang ("wen mainnet" → VISIBILITY), irony, cross-domain metaphors
  - Retweets inherit original author's semantic category
  - Confidence score + reasoning for every classification
- **7-day cache**: Same tweet re-scraped costs zero LLM tokens
- **Keyword fallback**: If LLM fails, keyword categorizer takes over seamlessly

### LLM Configuration
All LLM settings configurable via `.env`:

```bash
# Semantic enrichment
LLM_PROVIDER=ollama
LLM_MODEL=minimax-m2.7:cloud
LLM_FALLBACK_MODEL=gemma4:31b-cloud
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=30
LLM_CACHE_TTL_HOURS=168

# Digest generation
LLM_DIGEST_ENABLED=false
LLM_DIGEST_PROVIDER=ollama
LLM_DIGEST_MODEL=glm-5.1:cloud
LLM_DIGEST_TEMPERATURE=0.4
LLM_DIGEST_MAX_TOKENS=1500
LLM_DIGEST_TIMEOUT=45
```

To switch providers: change `LLM_PROVIDER` and `LLM_MODEL`. Zero code changes.

---

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

# Run tests
python3 -m pytest tests/
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
