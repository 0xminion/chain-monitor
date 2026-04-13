# Chain Monitor — Product Requirements Document v2.5

**Version:** 2.5
**Date:** 2026-04-13
**Scope:** 30-chain monitoring system
**Cadence:** Daily digest + weekly deep analysis
**Confidence target:** 95%+ data verification
**Purpose:** Strategic intelligence for traders/analysts — what chains are doing, where trends are converging, and where to look before the narrative hits mainstream

### Prerequisites — What You Need to Provide

| Item | Why | Cost | How to Get |
|------|-----|------|------------|
| **CoinGecko API key** | Market data (price, mcap, volume) | Free (Demo: 30 req/min, 10K/mo) | REDACTED_COINGECKO_KEY ✓ |
| **CoinGecko CLI** | Alternative for one-off queries | Free (installed + logged in) | Use `cg` commands directly |
| **CryptoRank API key** | Events calendar, project data | Free (Core tier) | cryptorank.io/public-api/pricing → Start Free |
| **YouTube Data API key** | Channel monitoring for visibility events | Free (10K units/day) | console.cloud.google.com → enable YouTube Data API v3 → create key |
| **Telegram Bot token** | Daily/weekly delivery | Free | @BotFather → /newbot → get token |
| **Telegram chat ID** | Where to deliver digests | Free | Send message to bot, check `getUpdates` API |

**Already available:** GitHub token (you have `gh` CLI @0xminion). CoinGecko CLI (installed + logged in). DefiLlama, SEC EDGAR, governance forums = no auth needed.

**Note on Messari:** Messari API is now enterprise-only (no free tier). Replaced with CryptoRank free tier + DefiLlama + CoinGecko for equivalent coverage. If you have or can get Messari enterprise access, it would improve partnership/event signal quality.

---

## 1. Problem

Tracking 30 chains manually is impossible. Information is fragmented across GitHub, blogs, Twitter, legal filings, on-chain data, governance forums, and news sites. By the time a human assembles the picture, the market has moved.

**Goal:** Automated ingestion → scored events → human-digestible output. A system that tells you what happened, how much it matters, and what to do about it.

---

## 2. Target Chains

### CEX Affiliated / Trading
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| Base | gov.optimism.io (OP Stack governance) | OP-style proposals |
| BSC | github.com/bnb-chain/BEPs | BEPs |
| Mantle | forum.mantle.xyz | MIPs |
| Hyperliquid | hyperliquid.gitbook.io | HIPs |
| Ink | N/A — enterprise-controlled (Kraken OP Stack L2, too early) | — |
| X Layer | N/A — enterprise-controlled (OKX) | — |
| Morph Network | N/A — too early | — |

### Majors
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| Ethereum | ethereum-magicians.org + eips.ethereum.org | EIPs |
| Bitcoin | github.com/bitcoin/bips | BIPs |
| Solana | github.com/solana-foundation/solana-improvement-documents | SIMDs |
| Arbitrum | forum.arbitrum.foundation | AIPs |
| Starknet | community.starknet.io | SNIPs |

### Payment
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| Tempo | N/A — enterprise-controlled (Stripe, no native token) | — |
| Plasma | N/A — enterprise-controlled (launched Sept 2025, centralized governance) | — |
| Stablechain (stable.xyz) | N/A — enterprise-controlled | — |
| Polygon | forum.polygon.technology | PIPs |
| Gnosis | forum.gnosis.io | GIPs |

### High TPS Chains
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| MegaETH | N/A — pre-launch, no governance yet | — |
| Monad | forum.monad.xyz | MIPs |
| Sei | N/A — no dedicated forum (on-chain governance via Cosmos SDK) | — |
| Sui | forums.sui.io/c/sips/27 | SIPs |
| Aptos | github.com/aptos-foundation/AIPs | AIPs |

### AI / Infra
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| Virtuals | gov.virtuals.io | VIPs |
| Bittensor | github.com/opentensor/bits | BITs |

### Others
| Chain | Governance Forum | Proposal Name |
|-------|-----------------|---------------|
| TON | github.com/ton-blockchain/TIPs | TIPs |
| OP Mainnet | gov.optimism.io | OPs |
| NEAR | gov.near.org | NEPs |

### Governance Coverage Summary
- **18 chains** with identifiable governance forums/docs
- **11 chains** without dedicated governance (enterprise-controlled, pre-launch, or Cosmos SDK on-chain only): Ink, X Layer, Morph Network, Tempo, Plasma, Stablechain, MegaETH, Sei, Base (inherits OP governance), OP Mainnet (shares gov.optimism.io with Base), BSC (GitHub BEPs only, no standalone portal)
- For chains without forums: monitor via GitHub repos, official X accounts, and blog posts instead

---

## 2.1 Chain Source Configuration

**Note:** RSS feed URLs marked with ⚠️ are estimated patterns — verify with `curl` during implementation. URLs marked with ✓ are confirmed. N/A means source does not exist or is not publicly accessible.

### CEX Affiliated / Trading

**Base**
- GitHub: `base-org/node` ✓, `ethereum-optimism/optimism` (shared OP Stack code) ✓
- Blog RSS: `https://base.mirror.xyz/feed/atom` ⚠️ (Mirror.xyz, Atom format)
- YouTube: `@Base` ✓
- Status: `https://status.base.org/` ⚠️
- Governance: `gov.optimism.io` (shared with OP Mainnet — filter by Base tags)
- DefiLlama slug: `base`
- CoinGecko ID: N/A (no native token)

**BSC**
- GitHub: `bnb-chain/bsc` ✓, `bnb-chain/BEPs` (governance) ✓
- Blog RSS: `https://www.bnbchain.org/en/blog/rss.xml` ⚠️
- YouTube: `@BNBChain` ✓
- Status: N/A (use bscscan.com for on-chain monitoring)
- Governance: GitHub BEPs only
- DefiLlama slug: `bsc`
- CoinGecko ID: `binancecoin`

**Mantle**
- GitHub: `mantlenetworkio/mantle` ⚠️
- Blog RSS: `https://www.mantle.xyz/blog/rss.xml` ⚠️
- YouTube: `@Mantle` ⚠️
- Status: N/A
- Governance: `forum.mantle.xyz` (Discourse) ⚠️
- DefiLlama slug: `mantle`
- CoinGecko ID: `mantle`

**Hyperliquid**
- GitHub: `hyperliquid-dex/hyperliquid-rust-sdk` ⚠️ (limited public repos)
- Blog RSS: N/A (announcements at `https://app.hyperliquid.xyz/announcements` — scrape, no RSS)
- YouTube: `@HyperliquidX` ✓
- Status: `https://hyperliquid.statuspage.io/` ⚠️
- Governance: `hyperliquid.gitbook.io` (docs-based HIPs)
- DefiLlama slug: `hyperliquid`
- CoinGecko ID: `hyperliquid`

**Ink**
- GitHub: `inkonchain/node` ⚠️, `inkonchain/docs` ⚠️
- Blog RSS: `https://inkonchain.com/blog/rss.xml` ⚠️
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled)
- DefiLlama slug: `ink`
- CoinGecko ID: N/A (no native token yet)

**X Layer**
- GitHub: `x-layer/x-layer` ⚠️ (may be limited)
- Blog RSS: N/A (OKX announcements at `https://www.okx.com/help/section/announcements-latest-announcements` — scrape, no RSS. Filter for X Layer keywords)
- YouTube: N/A (use OKX channel `@OKXOfficial` ⚠️ for X Layer content)
- Status: N/A
- Governance: N/A (enterprise-controlled)
- DefiLlama slug: `xlayer`
- CoinGecko ID: N/A (uses OKB)

**Morph Network**
- GitHub: `morph-l2/morph` ⚠️, `morph-l2/go-morph` ⚠️
- Blog RSS: `https://www.morphl2.io/blog/rss.xml` ⚠️
- YouTube: N/A
- Status: N/A
- Governance: N/A (too early)
- DefiLlama slug: `morph`
- CoinGecko ID: `morph` ⚠️

### Majors

**Ethereum**
- GitHub: `ethereum/go-ethereum` ✓, `ethereum/consensus-specs` ✓, `ethereum/execution-specs` ✓
- Blog RSS: `https://blog.ethereum.org/feed.xml` ✓
- YouTube: `@EthereumFoundation` ✓
- Status: `https://ethstats.net/` ⚠️ (not a traditional status page)
- Governance: `ethereum-magicians.org` (EIPs) ✓, `eips.ethereum.org` ✓
- DefiLlama slug: `ethereum`
- CoinGecko ID: `ethereum`

**Bitcoin**
- GitHub: `bitcoin/bitcoin` ✓
- Blog RSS: N/A (no official centralized blog)
- YouTube: N/A (no official channel)
- Status: N/A (use mempool.space for on-chain monitoring)
- Governance: `github.com/bitcoin/bips` (BIPs) ✓
- DefiLlama slug: N/A (no DeFi TVL)
- CoinGecko ID: `bitcoin`

**Solana**
- GitHub: `solana-labs/solana` ✓, `anza-xyz/agave` ✓
- Blog RSS: `https://solana.com/news/rss.xml` ⚠️
- YouTube: `@Solana` ✓
- Status: `https://status.solana.com/` ✓
- Governance: `github.com/solana-foundation/solana-improvement-documents` (SIMDs) ✓
- DefiLlama slug: `solana`
- CoinGecko ID: `solana`

**Arbitrum**
- GitHub: `OffchainLabs/nitro` ✓, `OffchainLabs/arbitrum-sdk` ✓
- Blog RSS: `https://medium.com/feed/@arbitrum` ⚠️ (Medium RSS)
- YouTube: `@Arbitrum` ⚠️
- Status: `https://status.arbitrum.io/` ⚠️
- Governance: `forum.arbitrum.foundation` (Discourse) ⚠️
- DefiLlama slug: `arbitrum`
- CoinGecko ID: `arbitrum`

**Starknet**
- GitHub: `starkware-libs/starknet` ✓, `starkware-libs/cairo` ✓
- Blog RSS: `https://www.starknet.io/en/blog/rss.xml` ⚠️
- YouTube: `@StarknetFndn` ⚠️
- Status: `https://status.starknet.io/` ⚠️
- Governance: `community.starknet.io` (Discourse, SNIPs) ✓
- DefiLlama slug: `starknet`
- CoinGecko ID: `starknet`

### Payment

**Tempo**
- GitHub: `tempoxyz` ✓ (user-provided org)
- Blog RSS: `https://tempo.xyz/blog/` ✓ (user-provided, verify RSS endpoint)
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled, Stripe)
- DefiLlama slug: N/A (may not be indexed yet)
- CoinGecko ID: N/A (no native token)
- Note: Monitor via X announcements

**Plasma**
- GitHub: `PlasmaLaboratories` ✓ (user-provided org)
- Blog RSS: `https://www.plasma.to/insights` ✓ (user-provided, verify RSS endpoint)
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled)
- DefiLlama slug: `plasma` ⚠️ (check if indexed)
- CoinGecko ID: `plasma` ⚠️

**Stablechain (stable.xyz)**
- GitHub: `stable-xyz` ⚠️ (org, check for active repos)
- Blog RSS: `https://blog.stable.xyz/` ✓ (verify RSS endpoint)
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled)
- DefiLlama slug: N/A (check if indexed)
- CoinGecko ID: N/A (may not have native token)

**Polygon**
- GitHub: `maticnetwork/bor` ✓, `0xPolygonHermez/zkevm-node` ✓, `0xPolygon/pol` ✓
- Blog RSS: `https://polygon.technology/blog/feed/` ⚠️
- YouTube: `@0xPolygon` ⚠️
- Status: `https://status.polygon.technology/` ⚠️
- Governance: `forum.polygon.technology` (Discourse, PIPs) ⚠️
- DefiLlama slug: `polygon`
- CoinGecko ID: `matic-network`

**Gnosis**
- GitHub: `gnosischain/specs` ⚠️, `gnosischain/beacon-chain` ⚠️
- Blog RSS: `https://www.gnosis.io/blog/rss.xml` ⚠️
- YouTube: `@GnosisChain` ⚠️
- Status: `https://status.gnosischain.com/` ⚠️
- Governance: `forum.gnosis.io` (Discourse, GIPs) ⚠️
- DefiLlama slug: `xdai`
- CoinGecko ID: `gnosis`

### High TPS Chains

**MegaETH**
- GitHub: `megaeth-labs` ⚠️ (org, check for active repos)
- Blog RSS: `https://megaeth.com/blog/rss.xml` ⚠️
- YouTube: N/A
- Status: N/A
- Governance: N/A (pre-launch)
- DefiLlama slug: N/A (pre-mainnet)
- CoinGecko ID: N/A (pre-TGE)

**Monad**
- GitHub: `monadxyz` ⚠️ (org, check for most-active repo)
- Blog RSS: `https://www.monad.xyz/blog/rss.xml` ⚠️
- YouTube: `@monad_xyz` ⚠️
- Status: N/A
- Governance: `forum.monad.xyz` (Discourse, MIPs) ⚠️
- DefiLlama slug: `monad` ⚠️ (check if indexed post-mainnet)
- CoinGecko ID: `monad` ⚠️

**Sei**
- GitHub: `sei-protocol/sei-chain` ✓, `sei-protocol/sei-cosmos` ⚠️
- Blog RSS: `https://blog.sei.io/rss.xml` ⚠️
- YouTube: `@SeiNetwork` ⚠️
- Status: `https://status.sei.io/` ⚠️
- Governance: On-chain only (Cosmos SDK). Public RPC: `https://rpc.sei.io` ⚠️ for `cosmos.gov.v1beta1` queries
- DefiLlama slug: `sei`
- CoinGecko ID: `sei-network`

**Sui**
- GitHub: `MystenLabs/sui` ✓
- Blog RSS: `https://blog.sui.io/feed/` ⚠️
- YouTube: `@SuiNetwork` ⚠️
- Status: `https://status.sui.io/` ⚠️
- Governance: `forums.sui.io/c/sips/27` (SIPs) ⚠️
- DefiLlama slug: `sui`
- CoinGecko ID: `sui`

**Aptos**
- GitHub: `aptos-labs/aptos-core` ✓
- Blog RSS: `https://aptosfoundation.org/news/rss.xml` ⚠️
- YouTube: `@AptosLabs` ⚠️
- Status: `https://status.aptoslabs.com/` ⚠️
- Governance: `github.com/aptos-foundation/AIPs` (AIPs) ✓
- DefiLlama slug: `aptos`
- CoinGecko ID: `aptos`

### AI / Infra

**Virtuals**
- GitHub: `virtuals-protocol` ⚠️ (org, limited public repos)
- Blog RSS: `https://virtuals.substack.com/` ✓ (user-provided, Substack → `/feed` endpoint)
- YouTube: N/A
- Status: N/A
- Governance: `gov.virtuals.io` (token-gated, skip per decision)
- DefiLlama slug: N/A (protocol on Base)
- CoinGecko ID: `virtuals-protocol` ⚠️

**Bittensor**
- GitHub: `opentensor/bittensor` ✓, `opentensor/subtensor` ✓, `opentensor/bits` (governance) ✓
- Blog RSS: `https://bittensor.com/blog/rss.xml` ⚠️
- YouTube: `@bittensor` ⚠️
- Status: `https://status.bittensor.com/` ⚠️
- Governance: `github.com/opentensor/bits` (BITs) ✓
- DefiLlama slug: N/A (subnet-based)
- CoinGecko ID: `bittensor`

### Others

**TON**
- GitHub: `ton-blockchain/ton` ✓, `ton-blockchain/TIPs` (governance) ✓
- Blog RSS: `https://ton.org/blog/rss.xml` ⚠️
- YouTube: `@tonblockchain` ⚠️
- Status: `https://status.ton.org/` ⚠️
- Governance: GitHub TIPs ✓
- DefiLlama slug: `ton`
- CoinGecko ID: `the-open-network`

**OP Mainnet**
- GitHub: `ethereum-optimism/optimism` ✓, `ethereum-optimism/specs` ✓
- Blog RSS: `https://optimism.mirror.xyz/feed/atom` ⚠️ (Mirror.xyz, Atom format)
- YouTube: `@OptimismCollective` ⚠️
- Status: `https://status.optimism.io/` ⚠️
- Governance: `gov.optimism.io` ✓ (shared with Base — filter by OP tags)
- DefiLlama slug: `optimism`
- CoinGecko ID: `optimism`

**NEAR**
- GitHub: `near/nearcore` ✓
- Blog RSS: `https://near.org/blog/rss.xml` ⚠️
- YouTube: `@NEARProtocol` ⚠️
- Status: `https://status.near.org/` ⚠️
- Governance: `gov.near.org` (Discourse, NEPs) ⚠️
- DefiLlama slug: `near`
- CoinGecko ID: `near`

### Source Coverage Summary

| Dimension | Chains with source | Chains without |
|-----------|-------------------|----------------|
| GitHub repos | 30/30 | None (all resolved) |
| Blog RSS / announcements | 26/30 | Bitcoin (no central blog), Hyperliquid (scrape announcements page), X Layer (scrape OKX announcements), Morph (verify RSS exists) |
| YouTube channel | 20/30 | Bitcoin, X Layer (use OKX), Ink, MegaETH, Virtuals, Morph (verify), Stablechain + 3 TBD |
| Status page | 14/30 | Bitcoin, Mantle, X Layer, Morph, Tempo, Plasma, Stablechain, MegaETH, Monad, Virtuals + 6 TBD |
| Governance forum | 19/30 | 11 enterprise/early (see section 2) |

**Chains with NO blog RSS (need scraping workaround):**
1. **Bitcoin** — no official blog. Monitor bitcoin.org/news + GitHub releases
2. **Hyperliquid** — scrape `https://app.hyperliquid.xyz/announcements` (no RSS)
3. **X Layer** — scrape OKX announcements page, filter for "X Layer" keywords
4. **Morph** — blog exists at morphl2.io but RSS endpoint unverified

**Chains with NO YouTube channel:**
1. Bitcoin
2. X Layer (use OKX channel as proxy)
3. Ink (Kraken channel as proxy)
4. MegaETH
5. Virtuals
6. Stablechain
7. Morph (need to verify if "Morph Network" channel is the right project)

### Verification Required Before Implementation

All RSS feed URLs need verification. Run during setup:
```bash
# Verify RSS feed exists and returns XML
curl -s -o /dev/null -w "%{http_code}" "https://blog.ethereum.org/feed.xml"
# Should return 200

# Check if URL returns valid RSS/Atom
curl -s "https://blog.ethereum.org/feed.xml" | head -5
# Should show <?xml or <rss or <feed
```

For Discourse forums, verify JSON endpoint:
```bash
curl -s "https://forum.arbitrum.foundation/latest.json" | jq '.topic_list.topics[0].title'
# Should return a topic title
```

For GitHub orgs, find the most-active repo:
```bash
gh repo list monadxyz --sort updated --limit 5
# Shows most recently updated repos
```

Verify DefiLlama chain slugs:
```bash
# Get all chains from DefiLlama and check our chains exist
curl -s "https://api.llama.fi/chains" | python3 -c "
import json, sys
chains = json.load(sys.stdin)
slugs = {c['name'].lower(): c for c in chains}
our_chains = ['ethereum','bitcoin','solana','arbitrum','starknet','base','bsc',
  'mantle','hyperliquid','polygon','gnosis','monad','sei','sui','aptos',
  'ton','optimism','near']
for c in our_chains:
    found = any(c in s.lower() or s.lower() in c for s in slugs.keys())
    print(f'{c}: {\"✓\" if found else \"✗ NOT FOUND — need to find correct slug\"}')"
```

### 2.2 Per-Chain Baseline Configs

Scoring thresholds differ per chain based on maturity, volatility, and data availability. An emerging chain at $200M TVL growing 30% is a different signal than Ethereum at $60B growing 3%.

**Tier 1 — Majors (lower thresholds, established patterns)**

```yaml
ethereum:
  tvl_absolute_milestone: 60_000_000_000  # $60B round numbers
  tvl_change_notable: 10    # 10% WoW = notable
  tvl_change_spike: 25      # 25% WoW = spike
  volume_spike_multiplier: 3  # 3x 7d avg = breakout
  fee_spike_multiplier: 2   # 2x 30d avg = usage surge
  upgrade_historical_move: "5-15% in 2 weeks pre-upgrade"
  regulatory_sensitivity: HIGH  # ETF flows, SEC actions
  upgrade_impact_floor: 4   # Any confirmed upgrade = minimum Impact 4
  trader_context_notes: "Watch gas fees, validator client diversity, L2 TVL impact"

bitcoin:
  tvl_absolute_milestone: null  # no DeFi TVL
  price_change_notable: 10
  price_change_spike: 20
  volume_spike_multiplier: 2.5
  regulatory_sensitivity: CRITICAL  # ETF is the narrative
  upgrade_impact_floor: 4   # Upgrades are rare and contentious
  trader_context_notes: "Regulatory news flows through ETF issuers. Watch IBIT flows."

solana:
  tvl_absolute_milestone: 10_000_000_000  # $10B
  tvl_change_notable: 15
  tvl_change_spike: 30
  volume_spike_multiplier: 3
  fee_spike_multiplier: 2
  upgrade_impact_floor: 3
  regulatory_sensitivity: HIGH
  trader_context_notes: "Watch for outage risk during upgrades. SOL price correlates with memecoin volume."

arbitrum:
  tvl_absolute_milestone: 15_000_000_000  # $15B
  tvl_change_notable: 15
  tvl_change_spike: 30
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "ARB token governance votes are high-signal. Watch treasury proposals."

starknet:
  tvl_absolute_milestone: 2_000_000_000  # $2B
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "Cairo ecosystem is distinct. Dev activity is the leading indicator."
```

**Tier 2 — CEX Affiliated (medium thresholds)**

```yaml
base:
  tvl_absolute_milestone: 5_000_000_000  # $5B
  tvl_change_notable: 15
  tvl_change_spike: 30
  volume_spike_multiplier: 3
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM  # Coinbase connection
  trader_context_notes: "Coinbase's chain. Any Coinbase regulatory news = Base impact."

bsc:
  tvl_absolute_milestone: 6_000_000_000  # $6B
  tvl_change_notable: 15
  tvl_change_spike: 30
  upgrade_impact_floor: 3
  regulatory_sensitivity: HIGH  # Binance regulatory overhang
  trader_context_notes: "BNB price is the BSC proxy. Binance regulatory news dominates."

mantle:
  tvl_absolute_milestone: 500_000_000  # $500M
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "Mantle = Bybit ecosystem. Watch Bybit exchange news."

hyperliquid:
  tvl_absolute_milestone: 1_000_000_000  # $1B
  tvl_change_notable: 20
  tvl_change_spike: 40
  volume_spike_multiplier: 2  # lower threshold — volume IS the product
  fee_spike_multiplier: 1.5
  upgrade_impact_floor: 3
  regulatory_sensitivity: CRITICAL  # no regulatory clarity
  regulatory_any_mention_impact: 5  # ANY regulatory mention = Impact 5
  trader_context_notes: "Volume ATH often precedes CEX listing rumors. Regulatory is THE risk."

ink:
  tvl_absolute_milestone: 100_000_000  # $100M
  tvl_change_notable: 30
  tvl_change_spike: 50
  upgrade_impact_floor: 2
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "Kraken's chain. Early stage. Watch for Kraken ecosystem announcements."

xlayer:
  tvl_absolute_milestone: 500_000_000  # $500M
  tvl_change_notable: 25
  tvl_change_spike: 50
  upgrade_impact_floor: 2
  regulatory_sensitivity: HIGH  # OKX HK-based
  trader_context_notes: "OKX deploying capital without announcement = stealth accumulation. TVL is proxy for OKX ecosystem bet."

morph:
  tvl_absolute_milestone: 50_000_000  # $50M
  tvl_change_notable: 30
  tvl_change_spike: 50
  upgrade_impact_floor: 2
  regulatory_sensitivity: LOW
  trader_context_notes: "Too early for meaningful baselines. Auto-adjust after 4 weeks of data."
```

**Tier 3 — Payment Chains (enterprise-controlled, adjust when data available)**

```yaml
tempo:
  tvl_absolute_milestone: null  # no native token, monitor stablecoin volume
  tvl_change_notable: 30
  upgrade_impact_floor: 2
  regulatory_sensitivity: HIGH  # Stripe is regulated
  trader_context_notes: "Stripe's chain. No native token. Monitor stablecoin settlement volume."

plasma:
  tvl_absolute_milestone: 2_000_000_000  # $2B (at launch)
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 2
  regulatory_sensitivity: HIGH
  trader_context_notes: "$2B at launch but no visibility. Institutional money in, retail hasn't noticed."

stablechain:
  tvl_absolute_milestone: 100_000_000
  tvl_change_notable: 30
  upgrade_impact_floor: 2
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "USDT-native chain. Monitor stablecoin transfer volume as primary metric."

polygon:
  tvl_absolute_milestone: 2_000_000_000  # $2B
  tvl_change_notable: 15
  tvl_change_spike: 30
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "POL token is the proxy. Enterprise partnerships are Polygon's moat."

gnosis:
  tvl_absolute_milestone: 500_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "GNO + Gnosis Pay = payments angle. Watch for European regulatory alignment."
```

**Tier 4 — High TPS Chains (higher thresholds, more volatile)**

```yaml
megaeth:
  tvl_absolute_milestone: null  # pre-mainnet
  tvl_change_notable: 50  # high volatility expected
  tvl_change_spike: 100
  upgrade_impact_floor: 2
  regulatory_sensitivity: LOW
  trader_context_notes: "Pre-mainnet. All signals are visibility/hype. First TVL data = high signal."

monad:
  tvl_absolute_milestone: 200_000_000  # $200M
  tvl_change_notable: 30
  tvl_change_spike: 50
  volume_spike_multiplier: 5  # volatile early stage
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "Governance proposals = pre-mainnet DeFi wave setup. Each passed proposal = capability unlocked."

sei:
  tvl_absolute_milestone: 500_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "EVM + Cosmos dual-vm is unique. Watch for EVM-native protocol migrations."

sui:
  tvl_absolute_milestone: 2_000_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "Move language ecosystem. SUI price correlates with gaming/NFT activity."

aptos:
  tvl_absolute_milestone: 1_000_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "Move language, like Sui. Watch APT price for gaming narrative correlation."
```

**Tier 5 — AI / Infra + Others (special handling)**

```yaml
virtuals:
  tvl_absolute_milestone: null  # protocol on Base
  tvl_change_notable: 30
  upgrade_impact_floor: 2
  regulatory_sensitivity: LOW
  trader_context_notes: "AI agent platform. VIRTUAL token is the proxy. Agent launches = token catalysts."

bittensor:
  tvl_absolute_milestone: null  # subnet-based, no traditional TVL
  tvl_change_notable: 30
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "TAO/wTAO price. Subnet activity is the real metric. New subnets = adoption signal."

ton:
  tvl_absolute_milestone: 500_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM  # Telegram connection
  trader_context_notes: "Telegram's chain. Any Telegram feature integration = TON catalyst."

optimism:
  tvl_absolute_milestone: 1_500_000_000
  tvl_change_notable: 15
  tvl_change_spike: 30
  upgrade_impact_floor: 3
  regulatory_sensitivity: MEDIUM
  trader_context_notes: "OP Stack = Base, Ink, etc share code. OP governance affects the entire Superchain."

near:
  tvl_absolute_milestone: 500_000_000
  tvl_change_notable: 20
  tvl_change_spike: 40
  upgrade_impact_floor: 3
  regulatory_sensitivity: LOW
  trader_context_notes: "NEAR AI narrative (Nightshade sharding + AI agents). Watch for AI partnerships."
```

**Baseline auto-adjustment rules:**
- After 4 weeks of data, recalculate thresholds based on actual signal distribution
- If >50% of signals for a chain are Impact 4+ → thresholds are too low, raise them
- If <10% of signals for a chain are Impact 4+ → thresholds are too high, lower them
- Log adjustments in weekly report methodology notes

---

## 3. Event Categories (6)

```
┌─────────────────────────────────────────────────────────┐
│                    EVENT TAXONOMY                        │
├──────────────┬──────────────────────────────────────────┤
│ TECH EVENT   │ Mainnet launches, upgrades, audits,      │
│              │ infrastructure changes, governance       │
│              │ proposals (EIPs, BIPs, SIMDs, etc.)      │
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
│ FINANCIAL    │ TVL/volume/fees milestones, TGEs,        │
│              │ funding rounds, grants, incentive        │
│              │ programs                                 │
└──────────────┴──────────────────────────────────────────┘
```

**Governance proposals are classified under TECH EVENT** — they represent proposed protocol changes. A governance proposal that passes is a TECH EVENT with higher urgency. A controversial proposal that splits the community may also get a RISK ALERT secondary tag.

---

## 4. Data Sources — Per Category

### 4.1 TECH EVENT (including Governance)

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| GitHub API (repos + releases) | Structured API | Free token (5000 req/hr) | All chains |
| Chain-specific blogs (RSS) | Semi-structured | None | Most chains |
| CryptoRank Events Calendar | Structured API | Free tier (Core) | Major chains |
| Artemis Developer Activity | Structured API | Free (contact for access) | ~20 chains |
| **Governance forums** | RSS/scraper | None | 18 chains (see table above) |
| **GitHub proposal repos** | Structured API | Free token | 7 chains (BIPs, SIMDs, BEPs, etc.) |

**Governance monitoring strategy:**

For chains with dedicated forums (Ethereum, Arbitrum, Polygon, OP, Mantle, Monad, Sui, Starknet, Gnosis, NEAR, Virtuals):
- RSS feed from forum (most Discourse-based forums expose /feed endpoints)
- Keyword filters: "proposal", "upgrade", "RFC", "vote", "final", "draft"
- Track proposal lifecycle: Draft → Review → Vote → Accepted/Rejected

For chains with GitHub-based proposals (Bitcoin, Solana, BSC, Aptos, TON, Bittensor):
- GitHub API: watch for new issues/PRs in proposal repos
- Label filters: "proposal", "accepted", "final"
- Release tags for finalized proposals

For chains without governance forums (Ink, X Layer, Morph, Tempo, Plasma, Stablechain, MegaETH, Sei):
- Monitor official GitHub repos for protocol changes
- Monitor blog RSS if available
- Sei: monitor on-chain governance via public Cosmos RPC endpoint (`cosmos.gov.v1beta1`)
- X/Twitter: Playwright backup only (fragile, not primary)
- Note: These chains are enterprise-controlled or too early. Governance decisions happen internally, not on forums. Focus monitoring on what they ship (GitHub) and what they announce (blog/RSS).

---

### 4.2 PARTNERSHIP

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| CryptoRank Events/News | Structured API | Free tier (Core) | Major chains |
| Official X/Twitter accounts | Playwright backup | None | All chains |
| CoinDesk / The Block RSS | Semi-structured | None | Major chains |
| Mirror.xyz / Substack (chain blogs) | Semi-structured | None | Emerging chains |
| DefiLlama Protocol pages | Structured API | None | All DeFi chains |

**Design thinking:** CryptoRank provides structured events data. RSS feeds for speed. DefiLlama is the "proof of life" — when TVL appears on a new chain, the partnership is real. X/Twitter via Playwright only as backup (fragile).

---

### 4.3 REGULATORY

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| SEC EDGAR RSS | Structured | None | US-focused |
| CoinCenter Tracker | Curated | None | US + global |
| DeFi Education Fund | Curated | None | US-focused |
| EU MiCA Portal | Structured | None | EU-focused |
| FATF Updates | Structured | None | Global |
| Lexology / Mondaq RSS | Semi-structured | None | Global |
| HK SFC Announcements | Structured | None | X Layer (OKX is HK-based) |

**Design thinking:** Regulatory is binary — either there's an active enforcement action or there isn't. SEC RSS + CoinCenter + 2-3 legal blogs covers 90%. Country-specific additions: HK SFC for X Layer/OKX.

**SEC EDGAR crypto-specific monitoring:**
- General RSS: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=40&action=getcompany` (keyword filter required)
- Crypto keyword filter: `crypto OR blockchain OR defi OR "digital asset" OR token OR stablecoin`
- Specific companies to watch: Coinbase, MicroStrategy, Grayscale, BlackRock (IBIT), Ripple
- HK SFC: `https://www.sfc.hk/en/Rules-and-standards/Circulars-and-announcements` (scrape)

---

### 4.4 RISK ALERT

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| DeFiLlama Hacks page | Structured API | None | All DeFi |
| Rekt News | Semi-structured | None | All chains |
| Immunefi Bug Bounty Dashboard | Structured | None | Chains with bounties |
| Chain status pages | Structured | Varies | Major chains |
| Security researcher X (backup) | Playwright | None | All chains |
| GitHub Issues (critical) | Structured API | Free token | All chains |

**Design thinking:** Speed matters. X security researchers for speed (Playwright backup only), DeFiLlama for verification ($ amounts), Rekt for post-mortems. Chain status pages are hit-or-miss.

---

### 4.5 VISIBILITY EVENT

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| Conference calendars | Manual + scraping | None | Major chains |
| YouTube (chain channels) | API | Free (quota-limited) | All chains |
| Podcast feeds (Bankless, Unchained, The Block, What Bitcoin Did) | RSS | None | Major chains |

**Podcast RSS URLs:**
- Bankless: `https://feeds.transistor.fm/bankless-podcast` ⚠️
- Unchained: `https://unchainedcrypto.com/feed/podcast` ⚠️
- The Block: `https://www.theblock.co/rss.xml` ⚠️
- What Bitcoin Did: `https://feeds.transistor.fm/what-bitcoin-did` ⚠️
- Lightspeed (Solana-focused): `https://feeds.transistor.fm/lightspeed` ⚠️
- The Defiant: `https://thedefiant.io/feed/podcast` ⚠️
| Official X accounts (backup) | Playwright | None | All chains |
| CryptoRank Events (team changes) | Structured API | Free tier (Core) | Major chains |

**Design thinking:** Visibility events are weakest individually, strongest in aggregate. Pattern detection > individual tracking. Conference + AMA + hiring cluster = momentum signal.

---

### 4.6 FINANCIAL

| Source | Type | Auth | Coverage |
|--------|------|------|----------|
| DefiLlama (TVL, fees, revenue, volume) | Structured API | None | 200+ chains |
| CoinGecko (market cap, price, volume) | Structured API | Free tier | All tokens |
| DefiLlama Stablecoins | Structured API | None | All chains |
| DefiLlama Unlocks | Structured API | None | Token-specific |

**Note:** Messari Asset Metrics removed (enterprise-only). DefiLlama + CoinGecko provide equivalent coverage for financial data.

**Milestone detection logic:**
```
TVL:      current > previous * 1.20  → 20% spike alert
          current < previous * 0.85  → 15% drop alert
Volume:   current > 7d_avg * 2.0    → volume breakout
Fees:     current > 30d_avg * 1.5   → fee spike (usage surge)
```

---

## 5. Signal Reinforcement Model

Adapted from AIXBT's approach. Multiple sources reporting the same event do not create duplicates — they reinforce a single signal.

### 5.1 How It Works

```
Event: "Ethereum Pectra upgrade date confirmed for May 7"

Source 1 (ethereum.org/blog RSS) — detected at 09:15 UTC
  → Signal created. Category: TECH EVENT. Impact: 4. Urgency: 2.

Source 2 (Messari Intel) — detected at 14:30 UTC
  → Signal reinforced. reinforcedAt updated. Activity log appended.
  → Source reliability boosted (multi-source confirmation)

Source 3 (CoinDesk RSS) — detected at 16:00 UTC
  → Signal reinforced. Activity log appended.
  → Composite confidence = max(reliabilities) × 1.25 (3 sources)
```

### 5.2 Signal Structure

```json
{
  "id": "eth-pectra-date-20260413",
  "chain": "ethereum",
  "category": "TECH_EVENT",
  "description": "Pectra upgrade date confirmed for May 7, 2026",
  "trader_context": "Expect gas fee volatility around upgrade date. Validators need to update client software — watch client diversity metrics. Historically, Ethereum upgrades see 5-15% price moves in the 2 weeks prior. EIP-7702 (account abstraction) is the headline feature for users.",
  "impact": 4,
  "urgency": 2,
  "priority_score": 8,
  "detectedAt": "2026-04-13T09:15:00Z",
  "reinforcedAt": "2026-04-13T16:00:00Z",
  "source_count": 3,
  "composite_confidence": 0.95,
  "hasOfficialSource": true,
  "secondary_tags": [],
  "activity": [
    {
      "timestamp": "2026-04-13T09:15:00Z",
      "source": "ethereum.org/blog",
      "reliability": 0.90,
      "evidence": "Blog post confirms May 7 mainnet date"
    },
    {
      "timestamp": "2026-04-13T14:30:00Z",
      "source": "cryptorank_events",
      "reliability": 0.80,
      "evidence": "Analyst note confirms date, adds 14 EIPs detail"
    },
    {
      "timestamp": "2026-04-13T16:00:00Z",
      "source": "coindesk_rss",
      "reliability": 0.80,
      "evidence": "Article adds validator adoption context"
    }
  ]
}
```

### 5.3 Trader Context Templates

Each category has a template that generates trader-relevant context. Chains with per-chain overrides use those instead.

**Template: TECH EVENT**
```
→ So what: [chain_name] upgrade/event affects [specific_impact].
  Historical pattern: [chain_name] [upgrades/hard_forks] typically see [X-Y%] price moves [timeframe].
  Watch: [specific_metrics_to_monitor]
```

**Template: PARTNERSHIP**
```
→ So what: [chain_name] + [partner_name] partnership signals [ecosystem_expansion/tech_adoption/market_access].
  If [partner] has token: [token_name] may see [correlation_effect].
  Follow-on: [what_to_expect_next]
```

**Template: FINANCIAL**
```
→ So what: [chain_name] [milestone_type] at [value]. [up/down] [X%] [timeframe].
  Context: This is [above/below/at] the [chain_name] baseline of [baseline_value].
  Signal: [capital_inflow/retail_fomo/institutional_positioning/ecosystem_growth]
```

**Template: RISK ALERT**
```
→ So what: [chain_name] [incident_type] — [amount_if_known] at risk.
  Immediate: [what_tokens_protocols_affected]
  Secondary: [contagion_risk, bridge_risk, trust_impact]
  Action: [check_exposure, monitor_withdrawals, watch_insurance]
```

**Template: REGULATORY**
```
→ So what: [jurisdiction] [action_type] affects [chain_name/sector].
  Direct impact: [token_listing_risk, exchange_access, compliance_cost]
  Timeline: [immediate/30_days/90_days/ongoing]
  Chains affected: [list_all_chains_in_jurisdiction]
```

**Template: VISIBILITY**
```
→ So what: [person/project] at [event] signals [marketing_push/talent_acquisition/community_building].
  Pattern: Chains with [X+] visibility events in [timeframe] often see [narrative_forming].
  Watch: [what_to_track_for_confirmation]
```

**Per-chain trader_context overrides:**

Ethereum:
- Upgrades: "Historically ETH sees 5-15% moves in 2 weeks pre-upgrade. Watch gas fees, validator client diversity, L2 TVL impact."
- TVL milestones: "Ethereum TVL at $X = X% of total DeFi TVL. Dominance shift signal."

Hyperliquid:
- Volume milestones: "HYPE volume at $X. Perps market share = X%. Watch for CEX listing rumors — volume ATH often precedes."
- Regulatory: "No regulatory clarity is the single biggest risk. Any SEC/regulatory mention is Impact 5 regardless of severity."

Monad:
- Governance: "Monad governance proposals = pre-mainnet DeFi wave setup. Each passed proposal = capability unlocked for ecosystem."
- Partnerships: "Every major protocol on Monad = ecosystem validation. Track which top-50 protocols deploy."

X Layer:
- Financial: "OKX deploying capital without announcement = stealth accumulation. Watch for OKX ecosystem fund reveal."
- TVL: "X Layer TVL is proxy for OKX ecosystem bet size."

Bitcoin:
- Regulatory: "BTC regulatory news flows through ETF issuers (BlackRock, Fidelity). Watch ETF inflows/outflows as proxy."
- Technical: "Bitcoin upgrades are rare and contentious. Any upgrade proposal is Impact 4 minimum."
```

### 5.4 Deduplication vs Reinforcement

**Old approach (dedup):** Same event from 3 sources → merge into 1, keep best source, discard others.

**New approach (reinforcement):** Same event from 3 sources → 1 signal with 3 activity entries. You can now answer:
- Who broke the story? (first activity entry)
- How confirmed is it? (source_count, composite_confidence)
- How did the narrative evolve? (activity log evidence strings)
- Is it still being discussed? (reinforcedAt vs now)

### 5.4 Reinforcement Rules

1. **Same chain + same category + similar description within 48h** → reinforce existing signal
2. **Similarity threshold:** >70% text overlap on key entities (chain name, event type, dates/names)
3. **New evidence adds detail** → update description if new source adds specifics (e.g., first source says "upgrade coming", second says "May 7, 14 EIPs")
4. **Echo detection:** Conference talk re-announcing known event → tag as "echo", don't alert
5. **Official source detection:** If chain's official X account or blog appears in activity → set hasOfficialSource: true (boosts confidence)

---

## 6. Importance Ranking System

### 6.1 Impact Score (1-5)

| Score | Label | Criteria |
|-------|-------|----------|
| 5 | CRITICAL | Fundamentals change. Protocol survival at stake. Major hack (>$10M), SEC enforcement, mainnet outage >2h, hard fork failure |
| 4 | HIGH | Significant capability or market position change. Major upgrade, Tier-1 partnership, TVL milestone, regulatory approval, governance proposal passed |
| 3 | NOTABLE | Meaningful but not transformative. New protocol deployment, conference keynote, funding round <$50M, audit completion, governance proposal in draft |
| 2 | MODERATE | Incremental progress. Minor upgrade, small partnership, AMA, grant program |
| 1 | LOW | Background activity. Routine commits, minor blog post |

### 6.2 Urgency Score (1-3)

| Score | Label | Criteria | Response Time |
|-------|-------|----------|---------------|
| 3 | IMMEDIATE | Active incident, market-moving, time-sensitive | <1 hour |
| 2 | SAME-DAY | Important but not breaking | <24 hours |
| 1 | WEEKLY | Background context, trend data | Weekly digest |

### 6.3 Final Priority = Impact × Urgency

| Score Range | Delivery |
|-------------|----------|
| ≥10 | Immediate Telegram alert |
| 6-9 | Daily digest |
| 3-5 | Weekly report |
| <3 | Log only |

### 6.4 Scoring Examples

| Event | Chain | Impact | Urgency | Score | Delivery |
|-------|-------|--------|---------|-------|----------|
| Pectra upgrade date confirmed | Ethereum | 4 | 2 | 8 | Daily digest |
| $50M bridge exploit | Hyperliquid | 5 | 3 | 15 | Immediate alert |
| Founder speaks at Token2049 | Monad | 3 | 1 | 3 | Weekly |
| TVL crosses $500M | X Layer | 4 | 2 | 8 | Daily digest |
| SEC wells notice | Bitcoin (ETF issuer) | 5 | 3 | 15 | Immediate alert |
| Governance proposal submitted | Arbitrum | 3 | 1 | 3 | Weekly |
| Governance proposal passed | Ethereum | 4 | 2 | 8 | Daily digest |
| Core dev departure | Ethereum | 4 | 2 | 8 | Daily digest |
| Routine commits | All chains | 1 | 1 | 1 | Log only |

---

## 7. Categorization Logic

### 7.1 Classification Rules

**Primary category = highest-impact dimension. Secondary tags are metadata.**

1. If money is at risk → RISK ALERT (primary)
2. If government/law involved → REGULATORY (primary)
3. If code changes or governance proposals → TECH EVENT (primary)
4. If two orgs collaborate → PARTNERSHIP (primary)
5. If people are involved → VISIBILITY (primary)
6. If numbers move → FINANCIAL (primary)

**Governance-specific rules:**
- Governance proposal submitted → TECH EVENT, Impact 3, Urgency 1
- Governance proposal in voting → TECH EVENT, Impact 3, Urgency 2
- Governance proposal passed → TECH EVENT, Impact 4, Urgency 2
- Governance proposal rejected after heated debate → TECH EVENT + RISK ALERT secondary (community split signal)
- Governance proposal that changes token economics → TECH EVENT primary, no separate category needed

### 7.2 Chain Tiering

```
TIER 1 — Deep monitoring (daily, all sources, governance forums)
  Ethereum, Bitcoin, Solana, Base, Hyperliquid, Arbitrum

TIER 2 — Standard monitoring (daily financials, weekly events)
  BSC, Mantle, X Layer, Monad, Sui, Optimism, Polygon, Starknet, Aptos

TIER 3 — Pulse check (weekly, key sources only)
  Ink, Morph, Tempo, Plasma, Stablechain, MegaETH, Sei, Gnosis,
  TON, NEAR, Virtuals, Bittensor
```

Monthly tier review. 3+ notable events in a month → promote. 30 days quiet → demote.

---

## 8. Source Reliability Ratings

| Source | Reliability |
|--------|-------------|
| GitHub API | 0.95 |
| DefiLlama API | 0.95 |
| SEC EDGAR | 0.95 |
| Chain status pages | 0.90 |
| CoinGecko | 0.90 |
| Messari (research + intel) | 0.85 | Human-curated but can lag. No longer free (enterprise-only). |
| CryptoRank | 0.80 | Good coverage, free tier available. |
| Official governance forums | 0.85 |
| CoinDesk / The Block | 0.80 |
| Rekt News | 0.80 |
| Official X accounts | 0.75 |
| Security researcher X | 0.70 |
| Podcast appearances | 0.65 |
| Community forums | 0.50 |

**Composite confidence** = max(source reliabilities) × multiplier:
- 1 source: ×1.0
- 2 sources: ×1.15
- 3+ sources: ×1.25
- Capped at 0.95
- +0.05 bonus if hasOfficialSource = true

---

## 9. Delivery Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  COLLECTORS  │────▶│  PROCESSORS  │────▶│   OUTPUT     │
│              │     │              │     │              │
│ • GitHub     │     │ • Classify   │     │ • Telegram   │
│ • DefiLlama  │     │ • Score      │     │   alerts +   │
│ • Messari    │     │ • Reinforce  │     │   daily +    │
│ • RSS feeds  │     │ • Enrich     │     │   bot v2     │
│ • Gov forums │     │              │     │ • Markdown   │
│ • SEC EDGAR  │     │              │     │   (weekly)   │
│ • CoinGecko  │     │              │     │ • JSON       │
│ • Playwright │     │              │     │   (archive)  │
│   (X backup) │     │              │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
   4h refresh         Real-time           Daily 9am GMT+8
   (staggered)        processing          Weekly Sunday
```

### 9.1 Cadence

| Task | Schedule | What |
|------|----------|------|
| Financial data pull | Every 4 hours | DefiLlama TVL/fees/volume + CoinGecko prices |
| GitHub activity scan | Every 6 hours | New releases, critical issues, commit velocity |
| RSS feed check | Every 4 hours | Blog posts, news articles |
| Governance forum scan | Every 6 hours | New proposals, votes, discussions |
| Scraping check (Bitcoin, Hyperliquid, X Layer, Morph) | Every 6 hours | Announcements, releases |
| YouTube channel check | Every 24 hours | New videos, AMAs, conference uploads |
| CryptoRank events pull | Every 6 hours | Events, partnerships, funding |
| Regulatory scan | Daily (9am) | SEC + CoinCenter + legal blogs |
| Risk alert check | Every 2 hours | DeFiLlama hacks + security feeds |
| Daily digest generation | Daily (9am GMT+8) | Aggregate all events, score, format |
| Weekly report generation | Sunday (9:05am GMT+8) | Deep analysis + trends + upcoming calendar |

### 9.2 Governance Forum Monitoring

For Discourse-based forums (Ethereum Magicians, Arbitrum, Polygon, OP, Mantle, Monad, Sui, Starknet, Gnosis, NEAR, Virtuals):
- Endpoint: `{forum_url}/latest.json` or `{forum_url}/categories.json`
- Filter by category (e.g., "governance", "proposals", "EIPs")
- Parse topic titles for proposal keywords
- Track topic lifecycle: created → replied → closed/accepted

For GitHub-based proposals (Bitcoin, Solana, BSC, Aptos, TON, Bittensor, Hyperliquid):
- GitHub API: `GET /repos/{owner}/{repo}/issues?labels=proposal&state=all&sort=created&direction=desc`
- Watch for label changes (draft → review → accepted → final)
- Watch for new releases tagged with proposal numbers

### 9.3 Governance Proposal Lifecycle

Track proposals through defined stages. Detect transitions via keywords/labels.

**Discourse forums — keyword-based detection:**
```
DRAFT:    Title contains "draft", "RFC", "wip", "idea"
REVIEW:   Title contains "review", "feedback", "discussion"
VOTING:   Title contains "vote", "ballot", "snapshot", "tally"
          OR post contains links to snapshot.org, tally.xyz
ACCEPTED: Title contains "accepted", "approved", "passed", "final"
          OR topic closed with "accepted" tag
REJECTED: Title contains "rejected", "declined", "withdrawn"
          OR topic closed without acceptance
IMPLEMENTED: New release tag references proposal number
```

**GitHub proposals — label-based detection:**
```
DRAFT:     label="draft" OR label="wip" OR state="open" + no labels
REVIEW:    label="review" OR label="rfc" OR state="open" + "ready-for-review"
VOTING:    label="voting" OR label="final-comment-period"
ACCEPTED:  label="accepted" OR label="approved" OR state="closed" + merged PR
REJECTED:  label="rejected" OR state="closed" + unmerged
IMPLEMENTED: Referenced in release notes or changelog
```

**Lifecycle logging:**
Each transition is logged as a signal event:
- DRAFT → REVIEW: Impact 2, Urgency 1 (background)
- REVIEW → VOTING: Impact 3, Urgency 2 (daily digest)
- VOTING → ACCEPTED: Impact 4, Urgency 2 (daily digest)
- VOTING → REJECTED: Impact 3, Urgency 1 (weekly)
- ACCEPTED → IMPLEMENTED: Impact 4, Urgency 2 (daily digest)

### 9.4 Scraping Strategy (for chains without RSS)

4 chains require scraping: Bitcoin, Hyperliquid, X Layer, Morph.

**Anti-bot protection handling:**
- Cloudflare-protected sites: Use Camoufox (anti-detect browser)
- Standard sites: Use cloudscraper (Python) first, fallback to Camoufox
- Rate limit scrapers: 1 req/min per domain

**Per-chain scraping config:**

Bitcoin:
- Scrape: `https://bitcoin.org/en/release` (release announcements)
- Fallback: Monitor `bitcoin/bitcoin` GitHub releases API (primary anyway)
- No blog. GitHub is the real source.

Hyperliquid:
- Scrape: `https://app.hyperliquid.xyz/announcements`
- Check for hidden JSON endpoint: `https://api.hyperliquid.xyz/info` (may expose announcements)
- Camoufox if Cloudflare-protected

X Layer:
- Scrape: `https://www.okx.com/help/section/announcements-latest-announcements`
- Filter: Only keep items containing "X Layer" or "xlayer" keywords
- Cloudflare-protected → Camoufox required

Morph:
- Scrape: `https://www.morphl2.io/blog`
- Check common RSS paths: `/feed`, `/rss.xml`, `/feed.xml`, `/blog/rss`
- If RSS found, switch to RSS mode

**Scraping fallback chain:**
```
1. Try RSS feed URL → if 200 + valid XML → use RSS
2. Try cloudscraper → if 200 + parseable HTML → use scraper
3. Try Camoufox → if page loads → extract content
4. All failed → log error, skip source for this cycle
```

### 9.5 Error Handling Strategy

**Collector retry logic:**
```python
# Every collector call uses exponential backoff
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds

for attempt in range(MAX_RETRIES):
    try:
        result = fetch_data(source)
        break
    except Exception as e:
        wait = BACKOFF_BASE ** attempt  # 2s, 4s, 8s
        log_error(source, attempt, e, wait)
        sleep(wait)
else:
    # All retries failed
    mark_source_unhealthy(source)
    skip_source_for_cycle(source)
```

**Source health tracking:**
```python
source_health = {
    "defillama": {"status": "healthy", "last_success": "2026-04-13T09:00:00Z", "failures_24h": 0},
    "coingecko": {"status": "healthy", "last_success": "2026-04-13T09:00:00Z", "failures_24h": 0},
    "forum_arbitrum": {"status": "degraded", "last_success": "2026-04-13T03:00:00Z", "failures_24h": 2},
    "hyperliquid_scrape": {"status": "down", "last_success": "2026-04-12T15:00:00Z", "failures_24h": 8},
}
```

**Error summary in digest:**
```
⚠️ Source Health (last 24h)
  Healthy: 14/18 sources
  Degraded: forum.arbitrum (2 failures, last success 6h ago)
  Down: hyperliquid_announcements (8 failures, last success 18h ago)
  Retried: 3 sources, 7 total retry attempts
```

---

## 10. Output Formats

### 10.0 Strategic Intelligence Processing Layer

The raw event pipeline (collectors → scoring → reinforcement) produces structured signals. The strategic intelligence layer sits on top and answers the 4 key questions: What are chains doing? What's their focus? Where are trends converging? Where should I look before the breakout?

No new data sources needed. All derivable from existing event data + financial metrics.

#### 10.0.1 Narrative Clustering

**Purpose:** Group chains by what they're building toward, not by chain category.

**How it works:**
- After weekly events are scored, extract keywords/themes from signal descriptions
- Group chains that share signal themes (e.g., "AI", "payments", "DeFi", "RWA")
- Track signal count per narrative theme per week
- Calculate velocity: this week vs trailing 3-week average

**Seed narrative categories (pre-defined, system discovers new ones):**
- AI/Agents (agent frameworks, AI infra, autonomous agents)
- Payments/Stablecoins (stablecoin rails, payment chains, remittance)
- DeFi (lending, DEX, yield, derivatives, liquid staking)
- L2 Infrastructure (rollups, sequencers, bridges, cross-chain)
- RWA (tokenized assets, treasuries, real-world integration)
- Gaming (on-chain gaming, NFTs, metaverse)
- Privacy (ZK proofs, private transactions, mixers)
- Security/Audits (bug bounties, formal verification, audit reports)

**New theme detection:** If 5+ signals share keywords not matching any seed category, auto-create new theme. Human review in weekly report to confirm/discard.

**Output:**
```
NARRATIVE MAP — Week of Apr 7-13

🔥 AI + Agents (accelerating)
  Chains: Virtuals, Bittensor, Monad (new: AI infra grants), Base (new: agent framework)
  Signals: 14 this week (6 last week, 5 the week before)
  Velocity: +133% vs 3-week avg

💰 Payments + Stablecoins (steady)
  Chains: Tempo, Plasma, X Layer, Polygon
  Signals: 8 this week
  Velocity: +5% vs 3-week avg

📉 L2 Infrastructure (fading)
  Chains: Base, Arbitrum, OP, Starknet, Ink
  Signals: 5 this week (12 two weeks ago)
  Velocity: -50% vs 3-week avg
```

**Scoring rules:**
- 3+ chains entering same narrative in one week = convergence flag (high conviction)
- Narrative velocity >+50% = accelerating (watch closely)
- Narrative velocity <-30% = fading (rotate out attention)

#### 10.0.2 Before the Breakout

**Purpose:** Detect asymmetric opportunities before mainstream coverage.

**Detection rules (any 2 triggers = flag):**

1. **Stealth capital:** High financial activity (TVL spike, volume breakout) but low visibility events. Someone is deploying capital quietly.
2. **Acceleration without attention:** Signal count accelerating but chain is still Tier 2/3. Infrastructure building before narrative.
3. **Pending catalysts:** Governance proposals in final vote that could unlock new capability (staking changes, fee structure, new features).
4. **Pre-TGE pattern:** High visibility events (conference talks, AMAs) but zero financial data or token. Building hype before launch.
5. **Cross-chain deployment:** Same protocol deploying on 3+ chains simultaneously. That protocol's narrative may be the next theme.

**Output:**
```
🔍 BEFORE THE BREAKOUT

• X Layer: Stablecoin TVL doubled this week, no announcement.
  Trigger: stealth capital. Quiet institutional deployment.
  Confidence: medium. Action: monitor for partnership reveal.

• MegaETH: 4 visibility events in 2 weeks, zero TVL.
  Trigger: pre-TGE pattern. Classic hype-building.
  Confidence: low. Action: track, don't chase.

• Monad: 3 governance proposals in final vote, all validator incentives.
  Trigger: pending catalyst. If passed, staking narrative unlock.
  Confidence: high. Action: deep-dive on proposals.
```

#### 10.0.3 Chain Focus Radar

**Purpose:** Answer "what is each chain focused on right now?"

**How it works:**
- Take all signals for a chain in the current week
- Synthesize into a 1-2 sentence focus statement using dominant signal categories
- Compare to previous week's focus statement
- Flag focus shifts (chain pivoting attention = significant)

**Scoring:**
- If TECH EVENT dominates → "building" mode
- If PARTNERSHIP dominates → "ecosystem expansion" mode
- If FINANCIAL dominates → "growth/capital attraction" mode
- If REGULATORY dominates → "compliance/defense" mode
- If VISIBILITY dominates → "marketing/hype" mode
- If RISK ALERT dominates → "damage control" mode

**Output:**
```
🎯 CHAIN FOCUS RADAR

Ethereum: Protocol maturity. Pectra execution on May 7.
          [TECH EVENT dominant] Building mode.
          Shift from last week: no change.

Hyperliquid: Market dominance vs regulatory risk.
          [FINANCIAL + RISK ALERT dominant] Growth + defense mode.
          Shift from last week: added regulatory dimension.

X Layer: Quiet capital accumulation.
          [FINANCIAL dominant] Growth mode (stealth).
          Shift from last week: shifted from partnerships to financials.
```

#### 10.0.4 Competitive Positioning Matrix

**Purpose:** Compare chains within the same category to identify leaders and laggards.

**Categories to compare:**
- CEX Affiliated: Base vs BSC vs Mantle vs Hyperliquid vs Ink vs X Layer vs Morph
- Majors: ETH vs BTC vs SOL vs ARB vs STARK
- Payment: Tempo vs Plasma vs Stablechain vs Polygon vs Gnosis
- High TPS: MegaETH vs Monad vs Sei vs Sui vs Aptos
- AI/Infra: Virtuals vs Bittensor

**Metrics per chain (weekly):**
- TVL + WoW change
- Dev activity (GitHub commits/releases count)
- Governance activity (proposals submitted/moved/passed)
- Partnership count
- Visibility event count
- Risk alert count (inverse — fewer = better)

**Output:**
```
⚔️ HIGH TPS CHAINS

         TVL      Dev   Gov   Partners   Risk
Monad    $180M    3x    3x    12         0
Sei      $320M    2x    1x    3          0
Sui      $1.2B    3x    2x    8          0
Aptos    $890M    2x    2x    5          1
MegaETH  $0       2x    0     2          0

Leader: Sui (TVL + partnerships). Fastest builder: Monad.
Wildcard: MegaETH (no TVL, all momentum).
```

#### 10.0.5 Ecosystem Capital Tracker

**Purpose:** Track where chains are deploying capital. Grants and ecosystem funds are the earliest signal of strategic bets.

**Sources:**
- Governance proposals for treasury/grants discussions
- CryptoRank for grant program announcements
- DefiLlama for unexplained TVL spikes (capital deployment without announcement)

**Detection rules:**
- New grants program announced → log with focus area
- Treasury proposal requesting funds → track amount + purpose
- TVL spike on chain with no corresponding partnership/visibility event → stealth capital flag
- Ecosystem fund announcement → log size + focus

**Output:**
```
💸 ECOSYSTEM CAPITAL THIS WEEK

• Monad: $50M grants program (AI infra focus)
  Source: forum.monad.xyz governance proposal
  Signal: chain betting on AI before narrative mainstreams

• Base: 12 new grants approved
  Breakdown: 8 DeFi, 3 social, 1 AI
  Source: on-chain grants contract

• X Layer: Undisclosed capital movement
  TVL +$250M with no announcement
  Source: DefiLlama anomaly detection
  Signal: institutional deployment, partnership likely incoming
```

#### 10.0.6 Protocol Cross-Chain Deployment Tracker

**Purpose:** Detect when the same protocol deploys on multiple chains. This is the earliest signal of ecosystem convergence — before any blog post or announcement, DefiLlama picks up the TVL.

**How it works:**
- Poll DefiLlama protocols endpoint daily
- Compare protocol chain list: today vs yesterday
- If protocol X wasn't on chain Y yesterday but is today → log as cross-chain deployment event
- Track deployment clusters: if 3+ protocols deploy on the same new chain in the same week → ecosystem signal

**Detection rules:**
- Single deployment: Impact 2 (moderate), log only
- 3+ protocols on same chain in one week: Impact 3, daily digest
- Major protocol (top 50 TVL) deploying on new chain: Impact 3, daily digest
- Same protocol on 3+ new chains in one week: Impact 4 (narrative signal — this protocol IS the narrative)

**Output:**
```
🔗 CROSS-CHAIN DEPLOYMENTS THIS WEEK

New on Monad: Aave, Uniswap, Chainlink, Lido
  4 major protocols in one week = ecosystem validation signal

New on MegaETH: Aave only
  Single deployment, early signal. Monitor for more.

Expanding: Aave deployed on 4 new chains this week
  (Monad, MegaETH, Sei, Ink)
  Protocol-level narrative: Aave expansion wave
```

**Data source:** `https://api.llama.fi/protocols` — returns all protocols with their chain lists. Diff daily.

#### 10.0.7 8-Week Narrative Scorecard

**Purpose:** Track narrative themes over 8+ weeks with a cumulative leaderboard. Shows which narratives have lasting power vs which are spikes.

**How it works:**
- Maintain rolling 8-week signal count per narrative theme
- Calculate: current score, 8-week trend (% change from week 1 to week 8), entry point indicator
- Entry point = narrative is accelerating but not yet mainstream (velocity high, signal count moderate)

**Output:**
```
📊 NARRATIVE SCORECARD — 8-Week Trend

              Wk1→Wk8   Trend      Entry?
AI/Agents     3→34       📈 +1033%  Already mainstream
Payments      6→14       📈 +133%   Still early ✓
RWA           1→9        📈 +800%   Before mainstream ✓
DeFi          12→5       📉 -58%    Fading
Gaming        4→3        ➡️ -25%    Dead?
L2 Infra      14→4       📉 -71%    Background now

Entry Point Signals (highest opportunity):
1. Payments: +133% over 8 weeks, not yet mainstream
2. RWA: +800% but from low base, 3 new chains entering this week
```

**Scoring for "Entry Point":**
- 8-week velocity >+100% AND current week signal count <15 = entry point (accelerating, not mainstream)
- 8-week velocity >+100% AND current week signal count >20 = mainstream (already priced in)
- 8-week velocity <-30% = fading (rotate out)

#### 10.0.8 Source Quality Auto-Ranking

**Purpose:** After collecting data, automatically rank which sources produce the most high-value signals. Drop noise, double frequency on high-signal sources.

**How it works:**
- Track: total signals per source, signals with score ≥8 per source, false positive rate per source
- Calculate: signal quality ratio = (score ≥8 signals) / (total signals)
- Rank sources weekly

**Output (after 4+ weeks of data):**
```
📡 SOURCE QUALITY RANKING (4-week)

Source                    Signals   Score≥8   Quality
DefiLlama (financial)     89        23        26% ✓✓
GitHub (ethereum)         45        18        40% ✓✓✓
forum.arbitrum.foundation 12        5         42% ✓✓✓
CoinDesk RSS              67        11        16% ✓
CryptoRank events         34        8         24% ✓✓
Hyperliquid scrape        8         7         88% ✓✓✓ (low volume, high signal)
Morph blog scrape         3         0         0%  ✗ (consider dropping)
YouTube (Solana)          15        1         7%   ✗ (low value)

Actions:
- Hyperliquid scrape: increase frequency (6h → 4h)
- Morph blog: demote to weekly check
- YouTube (Solana): consider dropping unless conference season
```

### 10.1 Daily Digest (Telegram)

```
📊 Chain Monitor — Apr 13, 2026

🧠 TODAY'S THEME
AI/Agents convergence: 3 chains entered AI this week (Monad, Base, Virtuals).
Attention is shifting from L2 infrastructure to application-specific chains.

🔴 CRITICAL (Score ≥10)
[none today]

🟠 HIGH (Score 8-9)
• Ethereum: Pectra upgrade date confirmed for May 7 [ethereum.org, Messari, CoinDesk — 3x]
  Category: TECH EVENT | Impact: 4 | Urgency: 2

• X Layer: TVL crosses $500M, up 34% this week [DefiLlama]
  Category: FINANCIAL | Impact: 4 | Urgency: 2

🟡 NOTABLE (Score 6-7)
• Monad: announces 12 new ecosystem partners at Token2049 [X, Messari — 2x]
  Category: PARTNERSHIP | Impact: 3 | Urgency: 2

• Arbitrum: AIP-112 "Treasury diversification" enters voting [forum.arbitrum.foundation]
  Category: TECH EVENT | Impact: 3 | Urgency: 2

📈 Financial Snapshot
  TVL ↑: X Layer (+34%), Base (+12%), Monad (+8%)
  TVL ↓: Fantom (-6%), Cronos (-4%)
  Volume: Hyperliquid 24h volume hits $2.1B (ATH)

⚖️ Regulatory
  • SEC extends comment period on DeFi custody rules (90 days)
  • EU: 3 more exchanges received MiCA authorization

🏛️ Governance
  • Ethereum: EIP-7892 "Stateless clients" moved to Review
  • Solana: SIMD-0228 "Dynamic base fee" in community discussion

📅 Upcoming (next 7 days)
  • Apr 15: Ethereum Pectra testnet upgrade
  • Apr 17: Monad ecosystem demo day
  • Apr 18: Bitcoin core dev meeting

⚠️ Source Health
  Healthy: 16/18 | Degraded: 1 | Down: 1
  [Details: forum.arbitrum degraded (2 failures), hyperliquid_scrape down (8 failures)]
```

### 10.2 Weekly Report (Markdown)

The weekly report answers 4 strategic questions:
1. What are these chains doing? (highlights, directions)
2. What are their major focus points right now?
3. What are the trends? (Are top chains going into AI? DeFi? Payments?)
4. As a trader/analyst, what area should I look into before the big narrative hits?

```
# Chain Monitor Weekly — Apr 7-13, 2026

## 🎯 ACTION BRIEF
[Top 3 actionable items for the week ahead. What to watch, what to research, what to ignore.]

1. WATCH: Monad staking narrative
   Evidence: 3 governance proposals in final vote, all validator incentives
   Catalyst: Voting closes Apr 18
   Confidence: HIGH
   Action: Monitor MON price + TVL post-vote. If proposals pass,
   expect DeFi protocols to announce deployments within 1-2 weeks.

2. RESEARCH: Plasma stablecoin flows
   Evidence: $2B TVL at launch, zero visibility events, institutional money
   Catalyst: Unknown — but capital doesn't sit idle
   Confidence: MEDIUM
   Action: Check Plasma DeFi ecosystem for early yield opportunities.
   Who's deployed there? What's the TVL distribution?

3. IGNORE: L2 infrastructure narratives
   Evidence: 4-week declining trend, -71% signal velocity
   Confidence: HIGH
   Action: Don't rotate attention here. L2s are becoming
   background infrastructure. Attention is elsewhere.

## 🧠 NARRATIVE OF THE WEEK
[1-paragraph synthesis of the week's biggest pattern. What shifted?
What's the story that connects multiple chains?]

## 📈 NARRATIVE VELOCITY (4-week trend)
[Which themes are accelerating, steady, or fading?]

                    Wk1   Wk2   Wk3   Wk4   Trend
AI/Agents            3     5     8    14     📈 accelerating
Payments/Stable      6     7     7     8     ➡️ steady
DeFi (classic)      10     8     6     5     📉 fading
L2 Infrastructure   12    10     7     5     📉 fading
RWA                  2     3     5     7     📈 emerging

## 🔍 BEFORE THE BREAKOUT
[Signals that haven't hit mainstream yet. Where to look.]

• Monad: 3 governance proposals in final vote, all validator incentives.
  TVL still under $200M. Early. Watch for staking narrative.
• X Layer: Stablecoin TVL doubled with no announcement. Quiet capital
  deployment. Watch for partnership reveal.
• Plasma: $2B stablecoin TVL at launch but zero visibility events.
  Institutional money in, retail hasn't noticed.

## 🎯 CHAIN FOCUS RADAR
[Per-chain strategic synthesis: what is each chain focused on?]

Ethereum: Pectra upgrade execution. All attention on May 7.
          Focus: protocol maturity, not growth.
Hyperliquid: Perps volume ATH. Audit clean. Zero regulatory clarity.
          Focus: market dominance vs regulatory risk.
Monad:    Validator economics + ecosystem partnerships.
          Focus: infrastructure for mainnet DeFi wave.

## ⚔️ COMPETITIVE POSITIONING
[Category-level comparison. Who's winning within each group?]

HIGH TPS CHAINS:
         TVL      Dev Activity   Gov Activity   Partnerships
Monad    $180M    🔥🔥🔥         🔥🔥🔥          🔥🔥
Sei      $320M    🔥🔥           🔥              🔥
Sui      $1.2B    🔥🔥🔥         🔥🔥            🔥🔥🔥
Aptos    $890M    🔥🔥           🔥🔥            🔥🔥
MegaETH  $0       🔥🔥           —               🔥

Verdict: Sui leads on TVL + partnerships. Monad building fastest.
MegaETH is the wildcard — all hype, no TVL yet.

## 💸 ECOSYSTEM CAPITAL
[Grants, funds, capital deployment this week]

• Monad: $50M grants program (AI infra focus)
• Base: 12 new grants approved (8 DeFi, 3 social, 1 AI)
• X Layer: Undisclosed ecosystem fund (detected via TVL patterns)
• Arbitrum: $10M gaming grants round closed

## 🏛️ GOVERNANCE SUMMARY
| Chain | Active | New | Key Proposals |
|-------|--------|-----|---------------|
| Ethereum | 5 | 2 | EIP-7892 (Stateless clients) |
| Arbitrum | 3 | 1 | AIP-112 (Treasury diversification) |
| Solana | 2 | 1 | SIMD-0228 (Dynamic base fee) |
| Monad | 1 | 0 | MIP-3 (Validator incentives) |

## ⚖️ REGULATORY HEAT MAP
🟢 Favorable: Ethereum (ETF flows), Bitcoin (ETF)
🟡 Neutral: X Layer, Monad, Base
🔴 Watch: Hyperliquid (no clarity)

## 📅 UPCOMING EVENTS (next 14 days)
[calendar view]

## 📊 METHODOLOGY NOTES
- 47 events tracked this week
- 12 sources queried
- 3 events scored 8+ (high priority)
- 18 governance forums monitored
- Narrative velocity based on signal count per theme per week
```

### 10.3 On-Demand Queries (Telegram Bot — v2)

Phase 2 feature. Telegram bot commands:

```
/watch [chain]     — Show latest signals for a chain
/event [chain]     — Show latest events (all categories)
/gov [chain]       — Show governance activity
/financial [chain] — Show financial snapshot
/alerts            — Show active alerts (score ≥10)
/weekly            — Get latest weekly report
/status            — System health + last update times
```

Example interaction:
```
User: /watch monad

Bot: 📡 Monad — Latest Signals

🟠 HIGH
• MIP-3 "Validator incentive restructuring" passed vote
  Sources: forum.monad.xyz (3x reinforced)
  Detected: Apr 12 | Confidence: 0.95

🟡 NOTABLE
• 12 new ecosystem partners announced at Token2049
  Sources: X, Messari (2x reinforced)
  Detected: Apr 11 | Confidence: 0.88

• TVL crosses $200M milestone
  Sources: DefiLlama
  Detected: Apr 10 | Confidence: 0.95

📈 Financial
  TVL: $218M (+8% WoW)
  Volume: $45M (24h)
  Active addresses: 12,400 (+15% WoW)
```

---

## 11. Data Retention

- Raw event data: 30 days
- Aggregated metrics (TVL, volume): 90 days
- Weekly reports: indefinite
- Alert history: 90 days
- Governance proposal tracking: 90 days (covers full proposal lifecycle)

---

## 12. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Event capture rate | >90% of events in mainstream crypto media within 48h | Weekly spot-check |
| False positive rate | <10% of alerted events are non-material | Manual review |
| Time-to-alert (critical) | <2 hours from event to Telegram delivery | Timestamp comparison |
| Governance coverage | 100% of passed proposals captured within 24h | Cross-check against forum activity |
| Daily digest completeness | All 6 categories represented when events exist | Daily review |
| Source uptime | >95% API success rate | Collector error logging |

---

## 13. Implementation Priority

| Phase | Scope | Effort | Value |
|-------|-------|--------|-------|
| 1 | Financial (DefiLlama + CoinGecko) + Daily digest | 1 day | 25% |
| 2 | Tech Events (GitHub + RSS) | 1 day | +12% |
| 3 | Governance forums (18 forums) | 1 day | +8% |
| 4 | Risk Alerts (DeFiLlama hacks + security feeds) | 0.5 day | +10% |
| 5 | Partnerships (Messari Intel + RSS) | 0.5 day | +6% |
| 6 | Regulatory (SEC + CoinCenter + legal RSS) | 0.5 day | +6% |
| 7 | Visibility (YouTube + podcasts + conference calendars) | 1 day | +4% |
| 8 | Reinforcement model + scoring system | 1 day | Multiplicative |
| 9 | Weekly report generation | 0.5 day | Compounding |
| 10 | Strategic intelligence layer (narrative clustering, before the breakout, focus radar, competitive positioning, ecosystem capital, cross-chain tracker, 8-week scorecard, source ranking) | 3 days | +20% |
| 11 | Telegram bot on-demand queries (v2) | 2 days | Interactive layer |

**Total: ~12 days to full system. Bot (Phase 11) is v2.**

**Phase 10 is what differentiates this from a simple event feed.** Without it, you get "X happened on Y chain." With it, you get "AI narratives are accelerating across 4 chains, X Layer is quietly accumulating capital, and Monad's governance vote could unlock a staking narrative before anyone notices."

---

## 14. Source Summary — Quick Reference

| Category | Primary Sources | Backup Sources | Chains Covered |
|----------|----------------|----------------|----------------|
| TECH EVENT | GitHub API (30 chains), RSS blogs (26 chains), Governance forums (18 chains), CryptoRank | Artemis | 30/30 (scrape for chains without RSS) |
| PARTNERSHIP | CryptoRank Events/News, RSS (CoinDesk, The Block) | DefiLlama (indirect), X via Playwright | 30/30 |
| REGULATORY | SEC EDGAR, CoinCenter, legal blog RSS | HK SFC, MiCA portal, FATF | Global coverage |
| RISK ALERT | DeFiLlama hacks, Rekt News, GitHub issues | Immunefi, chain status pages (14 chains), X via Playwright | 30/30 |
| VISIBILITY | YouTube API (20 chains), podcast RSS, conference calendars | CryptoRank Events, X via Playwright | 28/30 (Bitcoin, Virtuals have no YouTube) |
| FINANCIAL | DefiLlama (30 chains), CoinGecko (26 tokens) | CoinGecko CLI (installed) | 26/30 with token data |

**Per-chain source config:** See Section 2.1 for complete GitHub repos, RSS URLs, YouTube channels, and status pages for all 30 chains.

---

## 15. Open Questions (resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | X/Twitter access | Playwright backup only, not primary |
| 2 | Monad status | Mainnet |
| 3 | Language | English only |
| 4 | Dune queries | Not needed |
| 5 | Alert threshold | Conservative (≥10 only) |
| 6 | AIXBT API | Not using (24h delay on free tier) |
| 7 | Interactive bot | v2 (after core pipeline) |
| 8 | Access model | Open (personal use, not product) |
| 9 | Governance forum rate limits | Non-issue. Each forum is a separate domain with its own limits. Poll every 6h per forum. |
| 10 | Sei governance | Public Cosmos RPC endpoint (`cosmos.gov.v1beta1`) |
| 11 | Tempo/Plasma coverage | Blog + X (Playwright backup) + financial data |
| 12 | Stablechain | stable.xyz — enterprise-controlled, no governance |
| 13 | Virtuals governance | Skip governance forum, not token-gated needed |
| 14 | Weekly report delivery | Both (Telegram inline + .md file) |

---

## 16. Remaining Open Questions

*None currently. All resolved in v2.1.*
