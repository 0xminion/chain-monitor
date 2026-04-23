# Chain Monitor — Product Requirements Document

**Version:** v0.1
**Date:** 2026-04-14
**Scope:** 27-chain monitoring system
**Cadence:** Daily digest + weekly deep analysis
**Confidence target:** 95%+ data verification
**Purpose:** Strategic intelligence for traders/analysts — what chains are doing, where trends are converging, and where to look before the narrative hits mainstream

### Prerequisites — What You Need to Provide

| Item | Why | Cost | How to Get |
|------|-----|------|------------|
| **CoinGecko API key** | Market data (price, mcap, volume) | Free (Demo: 30 req/min, 10K/mo) | coingecko.com/en/api/pricing → get demo key |
| **CoinGecko CLI** | Alternative for one-off queries | Free (installed + logged in) | Use `cg` commands directly |
| **CryptoRank API key** | Events calendar, project data | Free (Core tier) | cryptorank.io/public-api/pricing → Start Free |
| **YouTube Data API key** | Channel monitoring for visibility events | Free (10K units/day) | console.cloud.google.com → enable YouTube Data API v3 → create key |
| **Telegram Bot token** | Daily/weekly delivery | Free | @BotFather → /newbot → get token |
| **Telegram chat ID** | Where to deliver digests | Free | Send message to bot, check `getUpdates` API |

**Already available:** GitHub token (you have `gh` CLI @0xminion). CoinGecko CLI (installed + logged in). DefiLlama, SEC EDGAR, governance forums = no auth needed.

**Note on Messari:** Messari API is now enterprise-only (no free tier). Replaced with CryptoRank free tier + DefiLlama + CoinGecko for equivalent coverage. If you have or can get Messari enterprise access, it would improve partnership/event signal quality.

**Note on CryptoRank Events API:** The CryptoRank Events endpoint (`/v1/events`) is dead (404 as of Apr 2026). CryptoRank is used for project data and rankings only. Events are sourced from Coinpedia Events RSS + RSS news feeds + TradingView scraper instead.

---

## 1. Problem

Tracking 27 chains manually is impossible. Information is fragmented across GitHub, blogs, Twitter, legal filings, on-chain data, governance forums, and news sites. By the time a human assembles the picture, the market has moved.

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


## Source Directory

See [docs/chain_sources.md](docs/chain_sources.md) for per-chain RSS feeds, GitHub repos, governance forums, and API endpoints.
