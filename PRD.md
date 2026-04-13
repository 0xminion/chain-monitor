# Chain Monitor — Product Requirements Document

**Version:** 1.0
**Date:** 2026-04-13
**Scope:** 30-chain monitoring system (examples: Ethereum, Bitcoin, X Layer, Monad, Hyperliquid)
**Cadence:** Daily digest + weekly deep analysis
**Confidence target:** 95%+ data verification

---

## 1. Problem

Tracking 30 chains manually is impossible. Information is fragmented across GitHub, blogs, Twitter, legal filings, on-chain data, and news sites. By the time a human assembles the picture, the market has moved.

**Goal:** Automated ingestion → scored events → human-digestible output. A system that tells you what happened, how much it matters, and what to do about it.

---

## 2. Event Categories

Six categories, each with distinct data sources, scoring logic, and refresh cadence.

```
┌─────────────────────────────────────────────────────────┐
│                    EVENT TAXONOMY                        │
├──────────────┬──────────────────────────────────────────┤
│ TECH EVENT   │ Mainnet launches, upgrades, audits,      │
│              │ infrastructure changes                    │
├──────────────┼──────────────────────────────────────────┤
│ PARTNERSHIP  │ Integrations, collaborations, co-launches│
├──────────────┼──────────────────────────────────────────┤
│ REGULATORY   │ Licenses, approvals, bans, enforcement   │
├──────────────┼──────────────────────────────────────────┤
│ RISK ALERT   │ Hacks, exploits, outages, critical bugs  │
├──────────────┼──────────────────────────────────────────┤
│ VISIBILITY   │ Conferences, hackathons, AMAs, hires,    │
│              │ departures                               │
├──────────────┼──────────────────────────────────────────┤
│ FINANCIAL    │ TVL milestones, volume spikes, fees,     │
│              │ active addresses, TGEs, funding rounds,  │
│              │ grants, incentive programs               │
└──────────────┴──────────────────────────────────────────┘
```

---

## 3. Data Sources — Per Category

### 3.1 TECH EVENT

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| GitHub API (repos + releases) | Structured API | Free token (5000 req/hr) | All chains with public repos | Only source of truth for code activity. Commits, PRs, releases = ground truth for dev velocity. |
| Chain-specific blogs (RSS) | Semi-structured | None | Most chains | Official announcements land here first. Ethereum blog, Solana blog, etc. |
| Messari Protocol Research | Structured API | Free tier (500 req/day) | Top 200 assets | Curated research notes on upgrades. Human-vetted, reduces noise. |
| CryptoRank Events Calendar | Structured API | Free tier | Major chains | Aggregated calendar of forks, launches, migrations. |
| Artemis Developer Activity | Structured API | Free | ~20 chains | Normalized commit counts across repos. Good for trend comparison. |

**Example — Ethereum:**
- GitHub: `ethereum/go-ethereum` releases → Pectra upgrade tagged
- Blog: `ethereum.org/blog/rss` → official upgrade announcement
- Messari: ETH research feed → analyst note on EIP impacts
- CryptoRank: Fork date on calendar

**Example — Hyperliquid:**
- GitHub: `hyperliquid-dex/hyperliquid` (if public, otherwise community trackers)
- Blog: Hyperliquid blog / X announcements
- Messari: HYPE asset research

**Design thinking:** GitHub is the highest-signal source because code doesn't lie. Blogs are second because they're official but can be vague or delayed. Messari adds analyst context. CryptoRank is a fallback calendar. Artemis gives comparative velocity (is this chain's dev activity going up or down relative to peers?).

---

### 3.2 PARTNERSHIP

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| Messari Intel (Events feed) | Structured API | Free tier | Top 200 | Structured partnership/integration events with classification. Best single source. |
| Official X/Twitter accounts | Social | X API or scraping | All chains | Partnerships announced here first, before blogs. |
| CoinDesk / The Block RSS | Semi-structured | None | Major chains | Journalist-verified partnership coverage. |
| Mirror.xyz / Substack (chain blogs) | Semi-structured | None | Emerging chains | Smaller chains announce on personal blogs. Monad, X Layer often here. |
| DefiLlama Protocol pages | Structured API | None | All DeFi chains | When a protocol deploys on a new chain, DefiLlama picks it up as TVL appears. Indirect signal. |

**Example — X Layer:**
- Messari Intel: "OKX integrates X Layer bridge v2"
- X: @XLayerHQ announces partnership
- CoinDesk: coverage of OKX ecosystem expansion
- DefiLlama: new protocol appears on X Layer chain page

**Example — Monad:**
- X: @monad_xyz announces ecosystem partner
- Mirror.xyz: founder blog post explaining integration
- Messari: may or may not have it (emerging chain)

**Design thinking:** Messari Intel is the best structured source but lags 12-48 hours. X/Twitter is fastest but noisiest. The pattern: X for speed, Messari for verification, CoinDesk/The Block for confirmation. DefiLlama is the "proof of life" — when TVL appears on a new chain, the partnership is real.

---

### 3.3 REGULATORY

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| SEC EDGAR RSS | Structured | None | US-focused | Enforcement actions, no-action letters, proposed rules. Ground truth for US regulation. |
| CoinCenter Tracker | Curated | None | US + global | Non-profit tracking crypto legislation. Human-curated, high signal. |
| DeFi Education Fund | Curated | None | US-focused | Policy analysis with crypto-native lens. |
| EU MiCA Portal | Structured | None | EU-focused | MiCA regulation updates, licensing status. |
| FATF Updates | Structured | None | Global | Travel rule, AML guidance affecting all chains. |
| Messari Governance | Structured API | Free tier | DAOs | DAO proposals sometimes signal regulatory posture (e.g., "comply with X regulation"). |
| Lexology / Mondaq RSS | Semi-structured | None | Global | Law firm analysis of crypto regulation. |

**Example — Ethereum:**
- SEC EDGAR: spot ETF filings, staking guidance
- CoinCenter: analysis of SEC position on ETH classification
- EU MiCA: ETH-related compliance frameworks

**Example — Bitcoin:**
- SEC EDGAR: ETF flow data, custody rule changes
- FATF: mining-related AML guidance
- CoinCenter: legislative tracker for BTC-specific bills

**Example — X Layer:**
- OKX regulatory filings (if any)
- HK SFC announcements (OKX is HK-headquartered)
- MiCA if OKX seeks EU licensing

**Design thinking:** Regulatory is the most binary category. Either there's an active enforcement action or there isn't. The key insight: you don't need to monitor everything — you need keyword matching on a small set of high-signal sources. SEC RSS + CoinCenter + 2-3 legal blogs covers 90% of what matters. The remaining 10% is country-specific (HK SFC for X Layer, UAE VARA for chains with Middle East presence).

---

### 3.4 RISK ALERT

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| DeFiLlama Hacks page | Structured API | None | All DeFi | Real-time hack/exploit tracking with $ amounts. Most comprehensive. |
| Rekt News | Semi-structured | None | All chains | Investigative post-mortems. Highest quality hack coverage. |
| Immunefi Bug Bounty Dashboard | Structured | None | Chains with bounties | Active bounty activity = security posture indicator. |
| Chain status pages | Structured | Varies | Major chains | Official incident reports (e.g., status.solana.com). |
| X/Twitter (security researchers) | Social | Scraping | All chains | @samczsun, @zachxbt, @peckshield often break news first. |
| GitHub Issues (critical) | Structured API | Free token | All chains | Critical bug reports in core repos. |

**Example — Ethereum:**
- DeFiLlama: Lido exploit (hypothetical) tracked with $ amount
- Rekt: post-mortem analysis
- GitHub: critical consensus bug reported in geth issues
- status.ethereum.org: incident response

**Example — Hyperliquid:**
- DeFiLlama: if DEX exploit occurs
- X: @PeckShieldAlert or @CertiKAlert tweets
- Immunefi: active bounty status

**Design thinking:** Speed matters most here. Risk alerts have the highest urgency-to-noise ratio of any category. The strategy: X security researchers for speed (sub-minute), DeFiLlama for verification (structured data with $ amounts), Rekt for post-mortem quality (hours later but comprehensive). Chain status pages are hit-or-miss — some chains are transparent, others hide incidents.

---

### 3.5 VISIBILITY EVENT

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| Conference calendars (ETHDenver, Consensus, Token2049, etc.) | Manual + scraping | None | Major chains | Speaking slots = strategic positioning. |
| YouTube (chain channels + conference uploads) | API | Free (quota-limited) | All chains | AMAs, keynote talks, panel discussions. |
| Podcast feeds (Bankless, Unchained, The Block) | RSS | None | Major chains | Founder/lead appearances. High-signal for sentiment. |
| X/Twitter (founder accounts) | Social | Scraping | All chains | Departures, new hires, personal announcements. |
| Messari Intel (team changes) | Structured API | Free tier | Top 200 | Structured events for hires/departures. |
| LinkedIn (team pages) | Scraping | Cloudflare-blocked | Major chains | Last resort for team changes. Hard to automate. |

**Example — Monad:**
- ETHDenver: founder keynote announced
- YouTube: Monad ecosystem AMA uploaded
- X: @monad_xyz announces new CTO hire
- Bankless podcast: founder interview

**Example — Bitcoin:**
- Bitcoin 2026 conference: core dev panel
- Podcast: Bitcoin developer on What Bitcoin Did
- X: core contributor departure announced

**Design thinking:** Visibility events are the weakest signal individually but strongest in aggregate. A chain doing 3 conference talks + 2 AMAs + hiring 5 engineers in a month = ecosystem momentum. The trick is pattern detection, not individual event tracking. YouTube and podcast RSS are underutilized sources that most monitors ignore.

---

### 3.6 FINANCIAL

| Source | Type | Auth | Coverage | Why This Source |
|--------|------|------|----------|-----------------|
| DefiLlama (TVL, fees, revenue, volume) | Structured API | None | 200+ chains | Single best source for DeFi financial data. Free, no auth, comprehensive. |
| CoinGecko (market cap, price, volume) | Structured API | Free tier | All tokens | Market data. Complements DefiLlama with token-level metrics. |
| DefiLlama Stablecoins | Structured API | None | All chains | Stablecoin supply per chain = capital flow indicator. |
| DefiLlama Unlocks | Structured API | None | Token-specific | Token unlock schedules. Predictable sell pressure. |
| Token Terminal | Structured API | Free tier | Major protocols | Revenue/P/E ratios. Protocol-level financials. |
| Dune Analytics | GraphQL API | Free tier (2500 exec/mo) | Custom | Active addresses, unique users, transaction counts. Custom queries you can't get elsewhere. |
| Crunchbase / RootData | Scraping | Varies | Projects | Funding rounds, grant programs. |
| Messari Asset Metrics | Structured API | Free tier | Top 200 | Normalized financial metrics with historical data. |

**Milestone detection logic:**
```
TVL:      current > previous * 1.20  → 20% spike alert
          current < previous * 0.85  → 15% drop alert
Volume:   current > 7d_avg * 2.0    → volume breakout
Fees:     current > 30d_avg * 1.5   → fee spike (usage surge)
Addr:     daily_active > 30d_avg * 1.3 → adoption signal
```

**Example — Ethereum:**
- DefiLlama: TVL crosses $60B milestone
- CoinGecko: ETH market cap re-enters top 3
- Dune: daily active addresses hit 500K
- DefiLlama Unlocks: large unlock approaching

**Example — X Layer:**
- DefiLlama: TVL crosses $100M (milestone for emerging chain)
- CoinGecko: OKB volume spike
- RootData: new ecosystem fund announced

**Design thinking:** DefiLlama is the backbone — 80% of financial monitoring comes from this one API. CoinGecko fills token-level gaps. Dune is the wildcard: hard to automate but gives you data nobody else has (custom on-chain queries). The milestone system prevents alert fatigue — you don't notify on every 2% move, only on structurally significant shifts.

---

## 4. Importance Ranking System

Every event gets scored on two axes: **Impact** (how much it changes the chain's trajectory) and **Urgency** (how fast you need to know).

### 4.1 Impact Score (1-5)

| Score | Label | Criteria | Examples |
|-------|-------|----------|----------|
| 5 | CRITICAL | Fundamentals change. Protocol survival at stake. | Major hack (>$10M), SEC enforcement action, mainnet outage >2h, hard fork failure |
| 4 | HIGH | Significant capability or market position change. | Major upgrade (Pectra), Tier-1 partnership (Visa, Coinbase), TVL milestone, regulatory approval |
| 3 | NOTABLE | Meaningful but not transformative. | New protocol deployment, conference keynote, funding round <$50M, audit completion |
| 2 | MODERATE | Incremental progress. | Minor upgrade, small partnership, AMA appearance, grant program launch |
| 1 | LOW | Background activity. | Routine commits, minor blog post, team member LinkedIn update |

### 4.2 Urgency Score (1-3)

| Score | Label | Criteria | Response Time |
|-------|-------|----------|---------------|
| 3 | IMMEDIATE | Active incident, market-moving, time-sensitive | <1 hour |
| 2 | SAME-DAY | Important but not breaking | <24 hours |
| 1 | WEEKLY | Background context, trend data | Weekly digest |

### 4.3 Final Priority = Impact × Urgency

```
PRIORITY MATRIX:

           Urgency 1    Urgency 2    Urgency 3
           (Weekly)     (Same-Day)   (Immediate)
Impact 5   5 (daily)    10 (alert)   15 (ALERT)
Impact 4   4 (weekly)   8 (daily)    12 (alert)
Impact 3   3 (weekly)   6 (daily)    9 (daily)
Impact 2   2 (weekly)   4 (weekly)   6 (daily)
Impact 1   1 (skip)     2 (weekly)   3 (weekly)
```

**Thresholds:**
- Score ≥10: Push alert immediately (Telegram)
- Score 6-9: Include in daily digest
- Score 3-5: Include in weekly report
- Score <3: Log only, don't surface

### 4.4 Scoring Examples

| Event | Chain | Impact | Urgency | Score | Delivery |
|-------|-------|--------|---------|-------|----------|
| Pectra upgrade date confirmed | Ethereum | 4 | 2 | 8 | Daily digest |
| $50M bridge exploit | Hyperliquid | 5 | 3 | 15 | Immediate alert |
| Founder speaks at Token2049 | Monad | 3 | 1 | 3 | Weekly |
| TVL crosses $1B | X Layer | 4 | 2 | 8 | Daily digest |
| SEC issues wells notice | Bitcoin (via ETF issuer) | 5 | 3 | 15 | Immediate alert |
| Routine weekly commits | All chains | 1 | 1 | 1 | Log only |
| New stablecoin deployment | X Layer | 3 | 2 | 6 | Daily digest |
| Core dev departure | Ethereum | 4 | 2 | 8 | Daily digest |

---

## 5. Categorization Logic

### 5.1 How Events Get Classified

Events don't always fit neatly. A "partnership to build regulatory-compliant infrastructure" is PARTNERSHIP + REGULATORY. A "hack during a mainnet upgrade" is TECH EVENT + RISK ALERT.

**Rule: Primary category = highest-impact dimension. Secondary tags are metadata.**

```
CLASSIFICATION RULES:

1. If money is at risk → RISK ALERT (primary)
   Secondary: TECH EVENT if caused by upgrade

2. If government/law involved → REGULATORY (primary)
   Secondary: FINANCIAL if market impact

3. If code changes → TECH EVENT (primary)
   Secondary: RISK ALERT if breaking change

4. If two orgs collaborate → PARTNERSHIP (primary)
   Secondary: FINANCIAL if includes investment

5. If people are involved (talks, hires) → VISIBILITY (primary)
   Secondary: TECH EVENT if hire is engineering lead

6. If numbers move → FINANCIAL (primary)
   Secondary: RISK ALERT if negative movement
```

### 5.2 Multi-Category Events

Tag with all applicable categories, score by primary only:

```
Example: "Ethereum Foundation hires ex-SEC lawyer as compliance lead"
  Primary:   VISIBILITY (hire)
  Secondary: REGULATORY (compliance signal)
  Score:     Impact 3, Urgency 1 → 3 (weekly)

Example: "Hyperliquid suffers $20M exploit during upgrade"
  Primary:   RISK ALERT (exploit)
  Secondary: TECH EVENT (upgrade context)
  Score:     Impact 5, Urgency 3 → 15 (IMMEDIATE ALERT)
```

### 5.3 Chain Classification (affects monitoring depth)

Not all 30 chains get equal treatment.

```
TIER 1 — Deep monitoring (daily, all sources)
  Ethereum, Bitcoin, Solana, Base, Hyperliquid
  Why: largest ecosystems, most events, highest market impact

TIER 2 — Standard monitoring (daily financials, weekly events)
  Arbitrum, Optimism, Polygon, Avalanche, X Layer, Monad
  Why: growing ecosystems, regular activity

TIER 3 — Pulse check (weekly, key sources only)
  Remaining 19 chains
  Why: lower activity, alert on anomalies only
```

**Tier promotion/demotion:** Monthly review. If a Tier 3 chain shows 3+ notable events in a month, promote to Tier 2. If a Tier 1 chain goes quiet for 30 days, demote.

---

## 6. Source Reliability Ratings

Not all data sources are equal. Each source gets a reliability score that affects how events are weighted.

| Source | Reliability | Reasoning |
|--------|-------------|-----------|
| GitHub API | 0.95 | Ground truth. Code is code. |
| DefiLlama API | 0.95 | Community-verified, open-source methodology. |
| Chain status pages | 0.90 | Official but sometimes delayed or incomplete. |
| Messari (research + intel) | 0.85 | Human-curated but can lag. |
| SEC EDGAR | 0.95 | Government source. Unquestionable. |
| CoinGecko | 0.90 | Reliable for market data, occasionally delayed. |
| Rekt News | 0.80 | High quality but not always first. |
| Official X accounts | 0.75 | Official but unstructured, sometimes hype. |
| CoinDesk / The Block | 0.80 | Journalist-verified but editorial bias exists. |
| Security researcher X | 0.70 | Fast but unverified until confirmed. |
| Podcast appearances | 0.65 | Self-reported information, promotional. |
| LinkedIn scraping | 0.60 | Data quality issues, lag. |
| Community forums | 0.50 | High noise, occasional gem. |

**Composite event confidence** = source_reliability × (1 if single source, 1.15 if 2+ sources confirm, 1.25 if 3+ sources confirm)

Example: Partnership announced on X (0.75) + confirmed by Messari (0.85) + CoinDesk covers it (0.80)
→ Composite = max(0.75, 0.85, 0.80) × 1.25 = 0.85 × 1.25 = capped at 0.95

---

## 7. Delivery Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  COLLECTORS  │────▶│  PROCESSORS  │────▶│   OUTPUT     │
│              │     │              │     │              │
│ • GitHub     │     │ • Dedup      │     │ • Telegram   │
│ • DefiLlama  │     │ • Classify   │     │   (alerts +  │
│ • Messari    │     │ • Score      │     │    daily)    │
│ • RSS feeds  │     │ • Enrich     │     │ • Markdown   │
│ • SEC EDGAR  │     │              │     │   (weekly)   │
│ • X scraper  │     │              │     │ • JSON       │
│ • CoinGecko  │     │              │     │   (archive)  │
└─────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
   4h refresh         Real-time           Daily 9am GMT+8
   (staggered)        processing          Weekly Sunday
```

### 7.1 Cadence

| Task | Schedule | What |
|------|----------|------|
| Financial data pull | Every 4 hours | DefiLlama TVL/fees/volume + CoinGecko prices |
| GitHub activity scan | Every 6 hours | New releases, critical issues, commit velocity |
| RSS feed check | Every 4 hours | Blog posts, news articles |
| Messari intel pull | Every 6 hours | Partnership and research events |
| Regulatory scan | Daily (9am) | SEC + CoinCenter + legal blogs |
| Risk alert check | Every 2 hours | DeFiLlama hacks + X security accounts |
| Daily digest generation | Daily (9am GMT+8) | Aggregate all events, score, format |
| Weekly report generation | Sunday (9:05am GMT+8) | Deep analysis + trends + upcoming calendar |

### 7.2 Deduplication Rules

1. Same event from multiple sources → merge into single event, combine source reliability
2. Same chain, same category, within 24 hours → group if related (e.g., "3 partnership announcements" → single entry with count)
3. Re-announcements (conference talk about already-known upgrade) → tag as "echo", don't re-alert

---

## 8. Output Formats

### 8.1 Daily Digest (Telegram)

```
📊 Chain Monitor — Apr 13, 2026

🔴 CRITICAL (Score ≥10)
[none today]

🟠 HIGH (Score 8-9)
• Ethereum: Pectra upgrade date confirmed for May 7
  Sources: ethereum.org, Messari, CoinDesk
  Category: TECH EVENT | Impact: 4 | Urgency: 2

• X Layer: TVL crosses $500M, up 34% this week
  Sources: DefiLlama
  Category: FINANCIAL | Impact: 4 | Urgency: 2

🟡 NOTABLE (Score 6-7)
• Monad: announces 12 new ecosystem partners at Token2049
  Sources: X, Messari
  Category: PARTNERSHIP | Impact: 3 | Urgency: 2

• Hyperliquid: new audit report published by Trail of Bits
  Sources: GitHub, Immunefi
  Category: TECH EVENT | Impact: 3 | Urgency: 2

📈 Financial Snapshot
  TVL ↑: X Layer (+34%), Base (+12%), Monad (+8%)
  TVL ↓: Fantom (-6%), Cronos (-4%)
  Volume: Hyperliquid 24h volume hits $2.1B (ATH)

⚖️ Regulatory
  • SEC extends comment period on DeFi custody rules (90 days)
  • EU: 3 more exchanges received MiCA authorization

📅 Upcoming (next 7 days)
  • Apr 15: Ethereum Pectra testnet upgrade
  • Apr 17: Monad ecosystem demo day
  • Apr 18: Bitcoin core dev meeting
```

### 8.2 Weekly Report (Markdown file)

```
# Chain Monitor Weekly — Apr 7-13, 2026

## Narrative of the Week
L2 consolidation accelerates. X Layer and Base both hit TVL milestones
while smaller L2s lose share. Hyperliquid dominates perps volume with
85% market share on-chain.

## Per-Chain Deep Dives

### Ethereum
- Tech: Pectra upgrade confirmed. 14 EIPs included.
- Financial: TVL stable at $58B. Gas fees down 22%.
- Risk: None this week.
- Outlook: Pectra is the catalyst. Watch validator adoption rate.

### Hyperliquid
- Tech: Audit completed. No critical findings.
- Financial: Volume ATH at $2.1B/24h.
- Partnership: [details]
- Outlook: Regulatory risk remains the overhang.

[...remaining chains...]

## Regulatory Heat Map
🟢 Favorable: Ethereum (ETF flows positive), Bitcoin (ETF)
🟡 Neutral: X Layer, Monad
🔴 Watch: Hyperliquid (no regulatory clarity)

## Upcoming Events (next 14 days)
[calendar view]

## Methodology Notes
- 47 events tracked this week
- 12 sources queried
- 3 events scored 8+ (high priority)
```

---

## 9. Data Retention

- Raw event data: 30 days
- Aggregated metrics (TVL, volume): 90 days
- Weekly reports: indefinite
- Alert history: 90 days

---

## 10. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Event capture rate | >90% of events that appear in mainstream crypto media within 48h | Weekly spot-check against CoinDesk/The Block headlines |
| False positive rate | <10% of alerted events are non-material | User feedback + manual review |
| Time-to-alert (critical) | <2 hours from event to Telegram delivery | Timestamp comparison |
| Daily digest completeness | All 6 categories represented when events exist | Daily review |
| Source uptime | >95% API success rate | Collector error logging |

---

## 11. Implementation Priority

| Phase | Scope | Effort | Value |
|-------|-------|--------|-------|
| 1 | Financial (DefiLlama + CoinGecko) + Daily digest | 1 day | 40% of total value |
| 2 | Tech Events (GitHub + RSS) | 1 day | +20% |
| 3 | Risk Alerts (DeFiLlama hacks + X security) | 0.5 day | +15% |
| 4 | Partnerships (Messari Intel + RSS) | 0.5 day | +10% |
| 5 | Regulatory (SEC + CoinCenter + legal RSS) | 0.5 day | +10% |
| 6 | Visibility (YouTube + podcasts + conference calendars) | 1 day | +5% |
| 7 | Scoring system + priority matrix | 1 day | Multiplicative |
| 8 | Weekly report generation | 0.5 day | Compounding |

**Total estimated effort: ~6 days to full system.**

---

## 12. Open Questions

1. **X/Twitter access:** Scraping vs API? API costs $100/mo for basic. Scraping is free but fragile. Decision needed before Phase 4.

2. **Monad source availability:** Monad is pre-mainnet. GitHub may be partially private. Rely more on X + community sources until launch.

3. **Multi-language sources:** Some chains (especially Asian L1s) publish primarily in Chinese/Korean. Need translation layer or accept coverage gaps.

4. **Custom Dune queries:** Worth the 2500 exec/mo budget for active address tracking? Only if financial milestones need on-chain verification.

5. **Alert fatigue threshold:** Start conservative (only score ≥10 gets pushed). Adjust based on user feedback after 2 weeks.
