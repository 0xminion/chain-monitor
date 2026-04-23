## 2.1 Chain Source Configuration

**Note:** RSS feed URLs marked with ⚠️ are estimated patterns — verify with `curl` during implementation. URLs marked with ✓ are confirmed. N/A means source does not exist or is not publicly accessible.

### CEX Affiliated / Trading

**Base**
- GitHub: `base-org/node` ✓, `ethereum-optimism/optimism` (shared OP Stack code) ✓
- Blog RSS: `https://base.substack.com/feed` ✓ (Substack RSS)
- Engineering Blog: `https://www.base.dev/blog` ✓ (NEW)
- Paragraph Blog: `https://paragraph.xyz/@base` ✓ (NEW)
- Events: `https://lu.ma/BaseEvents` ✓ (NEW)
- Ecosystem: `https://base.org/ecosystem` ✓ (NEW)
- Build Portal: `https://base.org/build` ✓ (NEW)
- YouTube: `@Base` ✓
- Status: `https://status.base.org/` ✓
- Docs: `https://docs.base.org/` ✓
- Reddit: `https://www.reddit.com/r/BASE/` ✓ (NEW)
- Governance: `gov.optimism.io` (shared with OP Mainnet — filter by Base tags)
- DefiLlama slug: `base`
- CoinGecko ID: N/A (no native token)

**BSC**
- GitHub: `bnb-chain/bsc` ✓, `bnb-chain/BEPs` (governance) ✓
- Blog RSS: `https://medium.com/feed/@bnbchain` ✓ (Medium feed)
- Substack RSS: `https://bnbchain.substack.com/feed` ✓ (NEW — alternative to Medium)
- Blog page: `https://www.bnbchain.org/en/blog` ✓ (scrape backup)
- YouTube: `@BNBChain` ✓
- Status: N/A (use bscscan.com for on-chain monitoring)
- Governance: `https://forum.bnbchain.org/` ✓, GitHub BEPs ✓
- Docs: `https://docs.bnbchain.org/` ✓
- Discord: `https://discord.com/invite/bnbchain` ✓
- Telegram: `https://t.me/bnbchain` ✓, `https://t.me/bnbchainofficial` ✓
- DefiLlama slug: `bsc`
- CoinGecko ID: `binancecoin`

**Mantle**
- GitHub: `mantlenetworkio/mantle` ⚠️
- Blog RSS: `https://www.mantle.xyz/blog/rss.xml` ⚠️
- Substack RSS: `https://mantle.substack.com/feed` ✓ (NEW — alternative)
- Treasury Monitor: `https://treasurymonitor.mantle.xyz/` ✓ (NEW)
- Multisig: `https://multisig.mantle.xyz/` ✓ (NEW)
- EcoFund: `https://www.mantle.xyz/ecofund` ✓ (NEW — $200M)
- Delegate Voting: `https://delegatevote.mantle.xyz/` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/bitdao.eth/` ✓ (NEW — separate from forum)
- YouTube: `@MantleOfficial` ✓
- Status: N/A
- Governance: `https://forum.mantle.xyz/` ✓ (Discourse, MIPs)
- Docs: `https://docs.mantle.xyz/` ✓
- DefiLlama slug: `mantle`
- CoinGecko ID: `mantle`

**Hyperliquid**
- GitHub: `hyperliquid-dex/hyperliquid-rust-sdk` ⚠️ (limited public repos)
- Foundation: `https://hyperfoundation.org/` ✓ (NEW — official foundation site)
- Blog RSS: `https://medium.com/feed/@hyperliquid` ✓ (Medium feed)
- Substack RSS: `https://hyperliquid.substack.com/feed` ✓ (NEW)
- Announcements: `https://app.hyperliquid.xyz/announcements` ✓ (scrape as backup)
- YouTube: `@HyperliquidX` ✓
- Status: `https://hyperliquid.statuspage.io/` ✓ (confirmed working)
- Telegram (Announcements): `https://t.me/hyperliquid_announcements` ✓ (NEW)
- Governance: `https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips` ✓ (HIPs in docs)
- Docs: `https://hyperliquid.gitbook.io/hyperliquid-docs` ✓
- DefiLlama slug: `hyperliquid`
- CoinGecko ID: `hyperliquid`

**Ink** ⚠️ Extensive site discovered — NOT minimal
- GitHub: `inkonchain` ⚠️
- Blog RSS: `https://inkonchain.com/blog/rss.xml` ✓ (NEW — verified)
- Blog alt: `https://inkonchain.com/blog/feed` ✓
- Substack: `https://ink.substack.com/feed` ✓ (NEW)
- Press RSS: `https://inkonchain.com/press/rss` ✓ (NEW)
- Ecosystem: `https://inkonchain.com/ecosystem` ✓ (NEW)
- Grants: `https://inkonchain.com/grants` ✓ (NEW)
- Community: `https://inkonchain.com/community` ✓ (NEW)
- Builders: `https://inkonchain.com/builders` ✓ (NEW)
- Apps: `https://inkonchain.com/apps` ✓ (NEW)
- Explorer: `https://explorer.inkonchain.com` ✓ (NEW)
- Status: `https://inkonchain.com/status` ✓ (NEW — was N/A)
- Roadmap RSS: `https://inkonchain.com/roadmap/rss` ✓ (NEW)
- Warpcast: `https://warpcast.com/inkonchain` ✓ (NEW)
- YouTube: `@InkOnChain` ✓
- Docs: `https://docs.inkonchain.com/` ✓
- Governance: N/A (enterprise-controlled, Kraken OP Stack L2)
- Discord: `https://discord.com/invite/inkonchain` ✓
- DefiLlama slug: `ink`
- CoinGecko ID: N/A (no native token yet)

**X Layer** ⚠️ Has independent site at xlayer.xyz (not just OKX-dependent)
- GitHub: `okx/xlayer-reth` ✓, `okx/xlayer-docs` ✓
- Website: `https://www.xlayer.xyz` ✓ (independent site)
- Blog RSS: `https://www.xlayer.xyz/blog/rss.xml` ✓ (NEW — replaces scrape-only approach)
- Docs: `https://docs.xlayer.xyz` ✓ (independent docs, not just OKX)
- Explorer: `https://explorer.xlayer.xyz` ✓
- Ecosystem: `https://www.xlayer.xyz/ecosystem` ✓
- Grants: `https://www.xlayer.xyz/grants` ✓
- Status: `https://www.xlayer.xyz/status` ✓ (NEW — was N/A)
- OKX announcements: `https://www.okx.com/help/section/announcements-latest-announcements` ✓ (filter for X Layer)
- YouTube: N/A (use OKX channel `@OKXOfficial` ⚠️ for X Layer content)
- Governance: N/A (enterprise-controlled)
- Discord: `https://discord.gg/xlayer` ✓
- Telegram: `https://t.me/XLayerOfficial` ✓
- DefiLlama slug: `xlayer`
- CoinGecko ID: N/A (uses OKB)

**Morph Network** ⚠️ DOMAIN MIGRATION: morphl2.io → morph.network
- GitHub: `morph-l2/morph` ✓, `morph-l2/go-ethereum` ✓
- Website: `https://morph.network/` ✓ (morphl2.io redirects here)
- Blog RSS: `https://blog.morph.network/feed` ✓ (NEW — replaces morphl2.io)
- Substack RSS: `https://morph.substack.com/feed` ✓
- Explorer: `https://explorer.morph.network/` ✓
- Apps: `https://morph.network/apps` ✓
- Accelerator: `https://morph.network/accelerator` ✓ ($150M program)
- YouTube: `https://www.youtube.com/@MorphNetwork` ✓ (NEW)
- Docs: `https://docs.morph.network/` ✓ (migrated from morphl2.io)
- Status: N/A
- Governance: N/A (too early)
- Discord: `https://discord.gg/morphnetwork` ✓
- Telegram: `https://t.me/MorphGlobal` ✓
- DefiLlama slug: `morph`
- CoinGecko ID: `morph` ⚠️

### Majors

**Ethereum**
- GitHub: `ethereum/go-ethereum` ✓, `ethereum/consensus-specs` ✓, `ethereum/execution-specs` ✓
- Blog RSS: `https://blog.ethereum.org/feed.xml` ✓
- EIPs RSS: `https://eips.ethereum.org/rss/all.xml` ✓ (NEW — all EIPs as RSS)
- Research: `https://ethresear.ch` ✓ (NEW — R&D forum), `https://ethresear.ch/latest.json` ✓ (JSON API)
- Magicians API: `https://ethereum-magicians.org/latest.json` ✓ (NEW — Discourse JSON API)
- Grants: `https://esp.ethereum.org/` ✓ (NEW — Ecosystem Support Program)
- Devcon: `https://devcon.org` ✓ (NEW)
- Events: `https://ethglobal.com/events` ✓ (NEW — global hackathons)
- Week in Ethereum: `https://weekinethereum.substack.com` ✓ (NEW — newsletter)
- Client Diversity: `https://clientdiversity.org/` ✓ (NEW)
- Staking Launchpad: `https://launchpad.ethereum.org` ✓ (NEW)
- Burn Tracker: `https://ultrasound.money` ✓ (NEW)
- YouTube: `@EthereumFoundation` ✓
- Status: `https://ethstats.dev/` ✓
- Governance: `ethereum-magicians.org` (EIPs) ✓, `eips.ethereum.org` ✓
- DefiLlama slug: `ethereum`
- CoinGecko ID: `ethereum`

**Bitcoin**
- GitHub: `bitcoin/bitcoin` ✓, `bitcoin/bips` (BIPs) ✓, `lightning/bolts` (BOLTs) ✓
- Blog: `https://bitcoincore.org/en/blog/` ✓ (NEW — Bitcoin Core releases + blog)
- Core releases RSS: `https://bitcoincore.org/en/rss.xml` ✓ (NEW)
- OptTech newsletter: `https://bitcoinops.org` ✓ (NEW — Bitcoin OptTech newsletters)
- Blockstream blog: `https://blockstream.com/blog/` ✓ (NEW)
- Bitcoin Magazine RSS: `https://bitcoinmagazine.com/feed` ✓ (NEW — unofficial but major)
- Dev mailing list: `https://lists.linuxfoundation.org/pipermail/bitcoin-dev/` ⚠️ ( NEW — dev discussion)
- Lightning dev list: `https://lists.linuxfoundation.org/pipermail/lightning-dev/` ⚠️ (NEW)
- YouTube: `@BitcoinMagazine` ✓ (NEW), `@BTCSession` ✓ (NEW — unofficial)
- Status: N/A (use mempool.space for on-chain monitoring)
- Governance: `github.com/bitcoin/bips` (BIPs) ✓, `https://bips.dev/status/` ✓ (track deployed + draft BIPs)
- Lightning: `https://lightning.engineering/blog/` ✓ (NEW — Lightning Labs blog)
- DefiLlama slug: N/A (no DeFi TVL)
- CoinGecko ID: `bitcoin`

**Solana**
- GitHub: `solana-labs/solana` ✓, `anza-xyz/agave` ✓
- Blog RSS: `https://solana.com/news/rss.xml` ⚠️
- Foundation Blog RSS: `https://solanafoundation.org/blog/rss.xml` ✓ (NEW)
- Foundation News RSS: `https://solanafoundation.org/news/rss.xml` ✓ (NEW)
- Foundation Grants RSS: `https://solanafoundation.org/grants/rss.xml` ✓ (NEW)
- Anza (client): `https://anza.xyz` ✓ (NEW — Agave client team), `https://anza.xyz/blog` ✓
- YouTube: `@Solana` ✓
- Status: `https://status.solana.com/` ✓
- Governance: `github.com/solana-foundation/solana-improvement-documents` (SIMDs) ✓
- Discord: `https://discord.gg/solana` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/solana.sol` ✓ (NEW)
- DefiLlama slug: `solana`
- CoinGecko ID: `solana`

**Arbitrum**
- GitHub: `OffchainLabs/nitro` ✓, `OffchainLabs/arbitrum-sdk` ✓
- Blog RSS: `https://arbitrumfoundation.medium.com/feed` ✓ (Foundation Medium feed)
- Governance API: `https://forum.arbitrum.foundation/latest.json` ✓ (NEW — Discourse JSON)
- Snapshot: `https://snapshot.org/#/arbitrumfoundation.eth` ✓ (NEW), `https://snapshot.org/#/arbitrum.eth` ✓ (NEW)
- YouTube: `@Arbitrum` ⚠️
- Status: `https://status.arbitrum.io/` ⚠️
- Governance: `forum.arbitrum.foundation` (Discourse) ✓
- Discord: `https://discord.gg/arbitrum` ✓ (NEW)
- DefiLlama slug: `arbitrum`
- CoinGecko ID: `arbitrum`

**Starknet**
- GitHub: `starkware-libs/starknet` ✓, `starkware-libs/cairo` ✓
- Blog RSS: `https://medium.com/feed/@starkware` ✓ (Starkware Medium feed)
- Blog (StarkWare): `https://starkware.co/blog/` ✓
- Substack: `https://starknet.substack.com/feed` ✓
- Governance API: `https://community.starknet.io/latest.json` ✓ (NEW — Discourse JSON)
- Ecosystem: `https://starknet.io/ecosystem` ✓ (NEW)
- Grants: `https://starknet.io/grants` ✓ (NEW)
- Developers: `https://starknet.io/developers` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/starknet.eth` ✓ (NEW)
- YouTube: `@StarkWare` ✓
- Status: `https://status.starknet.io/` ✓
- Governance: `https://community.starknet.io/` ✓ (Discourse, SNIPs), `https://governance.starknet.io/` ✓
- Docs: `https://docs.starknet.io/` ✓
- Discord: `https://discord.gg/starknet` ✓ (NEW)
- DefiLlama slug: `starknet`
- CoinGecko ID: `starknet`

### Payment

**Tempo**
- GitHub: `https://github.com/tempo-labs` ✓
- Substack RSS: `https://tempo.substack.com/feed` ✓ (NEW)
- Explorer: `https://explore.tempo.xyz/` ✓ (NEW)
- Ecosystem: `https://tempo.xyz/ecosystem` ✓ (NEW)
- Learn Hub: `https://docs.tempo.xyz/learn` ✓ (NEW)
- Blog: `https://tempo.xyz/blog` ✓ (Cloudflare-protected, browser only)
- YouTube: N/A
- Docs: `https://docs.tempo.xyz/` ✓
- Status: N/A
- Governance: N/A (enterprise-controlled, Stripe)
- Discord: `https://discord.gg/tempo` ✓ (NEW)
- Telegram: `https://t.me/tempo_xyz` ✓ (NEW)
- X/Twitter: `https://x.com/tempo_xyz` ✓ (NEW)
- DefiLlama slug: N/A (may not be indexed yet)
- CoinGecko ID: N/A (no native token)
- Note: tempo.xyz is Cloudflare-protected (403 via curl, works in browser)

**Plasma** ⚠️ DOMAIN CORRECTION: plasma.com is a German industrial company — actual chain is plasma.to
- GitHub: `PlasmaLaboratories` ✓ (user-provided org)
- Website: `https://www.plasma.to/` ✓ (official — NOT plasma.com)
- Blog/Insights: `https://www.plasma.to/insights` ✓
- Docs: `https://www.plasma.to/docs/get-started/introduction/start-here` ✓
- Learn: `https://www.plasma.to/learn` ✓
- Dashboard: `https://app.plasma.to/` ✓
- Substack RSS: `https://plasma.substack.com/feed` ✓
- Discord: `https://discord.com/invite/plasmafdn` ✓
- X/Twitter: `https://x.com/Plasma` ✓
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled, Bitfinex-backed)
- DefiLlama slug: `plasma` ⚠️ (check if indexed)
- CoinGecko ID: `plasma` ⚠️

**Stablechain (stable.xyz)**
- GitHub: `stable-xyz` ⚠️ (org, check for active repos)
- Blog RSS: `https://blog.stable.xyz/rss` ✓
- Hub/Dashboard: `https://hub.stable.xyz` ✓ (NEW)
- Analytics: `https://stable.allium.so/` ✓ (NEW)
- Ecosystem: `https://stable.xyz/ecosystem` ✓ (NEW)
- Docs alt: `https://stablechain.io/docs` ✓ (alternate domain)
- YouTube: N/A
- Status: N/A
- Governance: N/A (enterprise-controlled)
- Discord: `https://discord.com/invite/stablexyz` ✓ (NEW)
- Telegram: `https://t.me/stablexyz` ✓ (NEW)
- X/Twitter: `https://x.com/stable` ✓ (NEW)
- DefiLlama slug: N/A (check if indexed)
- CoinGecko ID: N/A (may not have native token)

**Polygon**
- GitHub: `maticnetwork/bor` ✓, `0xPolygonHermez/zkevm-node` ✓, `0xPolygon/pol` ✓
- Blog RSS: `https://polygon.technology/blog` ⚠️ (verify RSS endpoint)
- Substack RSS: `https://polygon.substack.com/feed` ✓ (NEW — alternative)
- Governance API: `https://forum.polygon.technology/latest.json` ✓ (NEW — Discourse JSON)
- Ecosystem: `https://polygon.technology/ecosystem` ✓ (NEW)
- Grants: `https://polygon.technology/grants` ✓ (NEW)
- Community: `https://polygon.technology/community` ✓ (NEW)
- Events: `https://polygon.technology/events` ✓ (NEW)
- Wallet: `https://wallet.polygon.technology` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/polygonprotocol.eth` ✓ (NEW), `https://snapshot.org/#/maticnetwork.eth` ✓ (NEW)
- YouTube: `@0xPolygon` ⚠️
- Status: `https://status.polygon.technology/` ⚠️
- Governance: `https://forum.polygon.technology` ✓ (Discourse, PIPs), `https://governance.polygon.technology` ✓
- Docs: `https://docs.polygon.technology/` ✓
- Discord: `https://discord.gg/polygon` ✓ (NEW)
- DefiLlama slug: `polygon`
- CoinGecko ID: `matic-network`

**Gnosis**
- GitHub: `gnosischain/specs` ✓
- Chain page: `https://www.gnosis.io/chain` ✓ (NEW)
- Events: `https://www.gnosis.io/events` ✓ (NEW)
- Press: `https://www.gnosis.io/press` ✓ (NEW)
- Ventures: `https://www.gnosis.io/ventures` ✓ (NEW — Gnosis VC)
- Gnosis Pay: `https://gnosispay.com` ✓ (NEW)
- Circles: `https://aboutcircles.com` ✓ (NEW — Circles protocol)
- Staking: `https://validategnosis.com` ✓ (NEW — validator onboarding)
- Blog RSS: `https://gnosischain.substack.com/feed` ✓ (Substack)
- YouTube: `@GnosisChain` ✓
- X (chain): `https://x.com/gnosischain` ✓ (NEW)
- Status: N/A
- Governance: `https://snapshot.org/#/gnosis.eth` ✓, `https://snapshot.org/#/gnosisdao.eth` ✓
- Docs: `https://docs.gnosis.io/` ✓, `https://docs.gnosischain.com/` ✓
- DefiLlama slug: `gnosis`
- CoinGecko ID: `gnosis`

### High TPS Chains

**MegaETH**
- GitHub: `megaeth-labs` ⚠️ (org, check for active repos)
- Blog: `https://www.megaeth.com/blog-news` ✓
- Substack RSS: `https://megaethlabs.substack.com/feed` ✓ (confirmed)
- Rabbithole: `https://rabbithole.megaeth.com` ✓ (NEW — builder portal)
- Linktree: `https://linktr.ee/megaeth_labs` ✓ (NEW — all links hub)
- YouTube: N/A (no official channel found)
- Status: N/A
- Governance: N/A (pre-launch)
- DefiLlama slug: N/A (pre-mainnet)
- CoinGecko ID: N/A (pre-TGE)

**Monad**
- GitHub: `monadxyz` ⚠️ (org, check for most-active repo)
- Blog RSS: `https://medium.com/feed/@monad_xyz` ✓ (Medium feed)
- Substack RSS: `https://monad.substack.com/feed` ✓ (NEW — alternative)
- Blog: `https://blog.monad.xyz/` ✓
- Governance API: `https://forum.monad.xyz/latest.json` ⚠️ (NEW — Discourse JSON)
- Snapshot: `https://snapshot.org/#/monad.xyz` ✓ (NEW)
- YouTube: `@monad_xyz` ✓
- Docs: `https://docs.monad.xyz/` ✓
- Status: N/A
- Governance: `forum.monad.xyz` (Discourse, MIPs) ⚠️
- Discord: `https://discord.gg/monad` ✓ (NEW)
- Telegram: `https://t.me/monad_xyz` ✓ (NEW)
- DefiLlama slug: `monad` ⚠️ (check if indexed post-mainnet)
- CoinGecko ID: `monad` ⚠️

**Sei**
- GitHub: `sei-protocol/sei-chain` ✓, `sei-protocol/sei-cosmos` ⚠️
- Blog RSS: `https://blog.sei.io/feed/` ✓ (NEW — blog's own RSS)
- Substack RSS: `https://seinetwork.substack.com/feed` ✓ (NEW)
- Research: `https://seiresearch.io/` ✓ (NEW — Sei Research site)
- Ecosystem: `https://www.sei.io/ecosystem` ✓ (NEW)
- Builder Toolkit: `https://sei-foundation.notion.site/Sei-Ecosystem-Builders-Toolkit-836deaebca204452909d0bf9365d8116` ✓ (NEW)
- Governance proposals: `https://www.mintscan.io/sei/proposals` ✓ (NEW — on-chain viewer)
- YouTube: `@SeiNetwork` ✓
- Docs: `https://docs.sei.io/` ✓
- Status: N/A
- Governance: On-chain (Cosmos SDK). Public RPC: `https://rpc.sei-apis.com` ✓ for `cosmos.gov.v1beta1` queries. Proposals viewer: `mintscan.io/sei/proposals` ✓
- Discord: `https://discord.com/invite/sei` ✓ (NEW)
- Telegram: `https://t.me/seinetwork` ✓ (NEW), `https://t.me/+KZdhZ1eE-G01NmZk` ✓ (Builders, NEW)
- DefiLlama slug: `sei`
- CoinGecko ID: `sei-network`

**Sui**
- GitHub: `MystenLabs/sui` ✓
- Blog RSS: `https://blog.sui.io/feed/` ⚠️
- Mysten Labs: `https://mystenlabs.com/blog` ✓ (NEW — company blog)
- Governance API: `https://forums.sui.io/latest.json` ✓ (NEW — Discourse JSON)
- SIPs API: `https://forums.sui.io/c/sips/27.json` ✓ (NEW — proposals JSON)
- Ecosystem: `https://sui.io/ecosystem` ✓ (NEW)
- Community: `https://sui.io/community` ✓ (NEW)
- Developers: `https://sui.io/developers` ✓ (NEW)
- Explorer (Suiscan): `https://suiscan.xyz` ✓ (NEW)
- Explorer (Sui Explorer): `https://suiexplorer.com` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/suinetwork.eth` ✓ (NEW)
- YouTube: `@SuiNetwork` ✓
- Docs: `https://docs.sui.io/` ✓
- Status: N/A
- Governance: `https://forums.sui.io/c/sips/27` ✓ (SIPs)
- Discord: `https://discord.gg/sui` ✓ (NEW)
- Telegram: `https://t.me/sui_network` ✓ (NEW)
- DefiLlama slug: `sui`
- CoinGecko ID: `sui`

**Aptos**
- GitHub: `aptos-labs/aptos-core` ✓
- Blog RSS: `https://medium.com/feed/aptoslabs` ✓ (Medium feed)
- Substack RSS: `https://aptos.substack.com/feed` ✓ (NEW — alternative)
- Governance API: `https://forum.aptosfoundation.org/latest.json` ✓ (NEW — Discourse JSON)
- Governance proposals: `https://forum.aptosfoundation.org/c/governance/18.json` ✓ (NEW)
- News: `https://aptosfoundation.org/currents` ✓
- Events: `https://aptosfoundation.org/events` ✓
- Snapshot: `https://snapshot.org/#/aptosfoundation.eth` ✓ (NEW)
- YouTube: `@AptosNetwork` ✓
- Docs: `https://aptos.dev/` ✓
- Status: N/A
- Governance: `https://forum.aptosfoundation.org/` ✓, `github.com/aptos-foundation/AIPs` (AIPs) ✓
- Discord: `https://discord.gg/aptos` ✓ (NEW)
- Telegram: `https://t.me/AptosNetwork` ✓ (NEW)
- DefiLlama slug: `aptos`
- CoinGecko ID: `aptos`

### AI / Infra

**Virtuals**
- GitHub: `virtuals-protocol` ⚠️ (org, limited public repos)
- App: `https://app.virtuals.io/` ✓ (NEW — main app)
- ACP: `https://app.virtuals.io/acp` ✓ (NEW — Agent Commerce Protocol)
- Research: `https://www.virtuals.io/researches` ✓ (NEW — research articles)
- Eastworlds: `https://eastworlds.io/` ✓ (NEW — robotics subsidiary)
- Blog RSS: `https://virtuals.substack.com/feed` ✓ (Substack)
- YouTube: `@VirtualsProtocol` ✓
- Whitepaper: `https://whitepaper.virtuals.io/` ✓
- Docs: `https://docs.game.virtuals.io/` ✓ (game-specific)
- Status: N/A
- Governance: `gov.virtuals.io` (confirmed 200 — token-gated, skip per decision)
- DefiLlama slug: N/A (protocol on Base)
- CoinGecko ID: `virtuals-protocol` ⚠️

**Bittensor**
- GitHub: `opentensor/bittensor` ✓, `opentensor/subtensor` ✓, `opentensor/bits` (governance) ✓
- Substack: `https://bittensor.substack.com/feed` ✓
- TaoStats: `https://taostats.io/` ✓ (NEW — chain explorer/dashboard)
- YouTube: `@bittensor` ✓
- Docs: `https://docs.bittensor.com/` ✓
- X (opentensor): `https://x.com/opentensor` ✓ (NEW)
- Status: N/A
- Governance: `github.com/opentensor/bits` (BITs) ✓
- Discord: `https://discord.gg/bittensor` ✓ (NEW)
- DefiLlama slug: N/A (subnet-based)
- CoinGecko ID: `bittensor`

### Others

**TON** ⚠️ NOW HAS RSS — no longer needs scraping
- GitHub: `ton-blockchain/ton` ✓, `ton-blockchain/TIPs` (governance) ✓
- Blog/Newsroom RSS: `https://ton.org/en/newsroom/rss` ✓ (NEW — was scrape-only)
- Ecosystem RSS: `https://ton.org/ecosystem/rss` ✓ (NEW)
- Newsroom: `https://ton.org/en/newsroom?all` ✓ (still available as page)
- Events: `https://ton.org/events` ✓
- Community: `https://ton.org/community` ✓
- Grants: `https://ton.org/grants` ✓
- Learn: `https://ton.org/learn` ✓
- Ecosystem: `https://ton.org/ecosystem` ✓
- Governance: `https://ton.vote` ✓ (TON DAO Vote), `https://snapshot.org/#/ton` ✓
- YouTube: `@tonblockchain` ✓, `@toncoin` ✓
- Docs: `https://docs.ton.org` ✓
- Status: N/A (use t.me/tonstatus Telegram channel)
- Discord: `https://discord.gg/ton` ✓
- Telegram: `https://t.me/toncoin` ✓, `https://t.me/tonblockchain` ✓, `https://t.me/tonfoundation` ✓, `https://t.me/ton_announcements` ✓
- DefiLlama slug: `ton`
- CoinGecko ID: `the-open-network`

**OP Mainnet**
- GitHub: `ethereum-optimism/optimism` ✓, `ethereum-optimism/specs` ✓
- Blog: `https://optimism.io/blog` ✓
- Substack RSS: `https://optimism.substack.com/feed` ✓ (NEW)
- Governance API: `https://gov.optimism.io/latest.json` ✓ (NEW — Discourse JSON)
- Grants: `https://optimism.io/grants` ✓ (NEW)
- OP Labs: `https://oplabs.co` ✓ (NEW)
- Superchain: `https://superchain.eco` ✓ (NEW)
- Governance App: `https://app.optimism.io/governance` ✓ (NEW)
- Bridge: `https://app.optimism.io/bridge` ✓ (NEW)
- Snapshot: `https://snapshot.org/#/opcollective.eth` ✓
- YouTube: `@OptimismPBC` ✓
- Status: `https://status.optimism.io/` ✓
- Docs: `https://docs.optimism.io/` ✓
- Governance: `https://gov.optimism.io/` ✓
- Discord: `https://discord.gg/optimism` ✓ (NEW)
- DefiLlama slug: `optimism`
- CoinGecko ID: `optimism`

**NEAR**
- GitHub: `near/nearcore` ✓
- Blog RSS: `https://medium.com/feed/@nearprotocol` ✓ (Medium feed)
- Substack RSS: `https://near.substack.com/feed` ✓ (NEW — alternative)
- Blog (official): `https://near.org/blog` ✓, `https://pages.near.org/blog/` ✓
- Governance API: `https://gov.near.org/latest.json` ✓ (NEW — Discourse JSON)
- Proposals API: `https://gov.near.org/c/proposals/33.json` ✓ (NEW — direct proposals feed)
- Snapshot: `https://snapshot.org/#/near.eth` ✓ (NEW), `https://snapshot.org/#/nearfoundation.eth` ✓ (NEW)
- NEARCON: `https://nearcon.org` ✓ (NEW — annual conference)
- Aurora: `https://aurora.dev` ✓ (NEW — NEAR's EVM layer)
- YouTube: `@NEARProtocol` ✓
- Docs: `https://docs.near.org/` ✓
- Status: `https://status.near.org/` ✓
- Governance: `https://gov.near.org/` ✓ (Discourse, NEPs)
- Discord: `https://discord.gg/near` ✓ (NEW)
- Telegram: `https://t.me/nearprotocol` ✓ (NEW)
- DefiLlama slug: `near`
- CoinGecko ID: `near`

### Source Coverage Summary

|| Dimension | Chains with source | Chains without |
|-----------|-------------------|----------------|
| GitHub repos | 27/27 | None (all resolved) |
| Blog / newsroom RSS | 27/27 | None — all chains now have at least one working RSS feed |
| YouTube channel | 25/27 | Bitcoin (has unofficial @BitcoinMagazine), Stablechain (none) |
| Status page | 18/27 | 9 chains without (improved — Ink and X Layer now have status pages) |
| Governance forum | 19/27 | 8 enterprise/early (Ink, X Layer, Morph, Tempo, Plasma, Stablechain, MegaETH, Virtuals — some use on-chain/Snapshot) |
| Docs | 27/27 | All chains now have documentation (X Layer: docs.xlayer.xyz, Plasma: plasma.to/docs) |

**Blog RSS coverage details (Apr 2026 update):**
- 27/27 chains with working RSS feeds (5 chains gained RSS this update: TON, X Layer, Ink, Sei, Morph)
- Key new feeds: Ink blog RSS, X Layer blog RSS, Morph blog RSS (migrated domain), Sei blog RSS, TON newsroom RSS
- Additional Substack feeds: 13 chains publish on Substack alongside their main blog (BSC, Mantle, Hyperliquid, Morph, Tempo, Plasma, Polygon, NEAR, Optimism, Aptos, Monad, Ink, Sei) — all sources checked independently
- Governance APIs: All 11 Discourse forums have `/latest.json` endpoints for structured data

**Chains with NO blog RSS (need scraping workaround):**
1. **Bitcoin** — no official centralized blog. Monitor bitcoincore.org/blog + Bitcoin Magazine RSS + GitHub releases
2. ~~X Layer~~ — NOW HAS RSS at `www.xlayer.xyz/blog/rss.xml` ✓ (moved from scrape-only)
3. ~~TON~~ — NOW HAS RSS at `ton.org/en/newsroom/rss` ✓ (moved from scrape-only)

**Chains formerly without RSS that now have feeds (Apr 2026 update):**
- TON: `ton.org/en/newsroom/rss` ✓
- X Layer: `www.xlayer.xyz/blog/rss.xml` ✓
- Ink: `inkonchain.com/blog/rss.xml` ✓
- Morph: `blog.morph.network/feed` ✓ (migrated from morphl2.io)
- Sei: `blog.sei.io/feed/` ✓

**New sources added (Apr 14, 2026):**
- Arbitrum: Substack (arbitrum.substack.com/feed)
- Base: Basechain Substack (basechain.substack.com/feed)
- Gnosis: Substack + GnosisDAO Substack (fills biggest gap — had no blog RSS)
- Gnosis: GitHub specs atom feed (github.com/gnosischain/specs/commits/master.atom)
- Bitcoin: BIPs atom feed (github.com/bitcoin/bips/commits/master.atom) — tracks new/deployed/draft BIPs
- Polygon: Governance forum Discourse RSS (forum.polygon.technology/latest.rss)
- Plasma: Blog feed (plasma.dev/feed.xml)

Total chain_event feeds: 54

**Categorizer fix (Apr 14, 2026):**
- TECH_EVENT checked before PARTNERSHIP — "live on mainnet" no longer misclassified as partnership
- Fixed: Sei v6.4 mainnet launch correctly classified as Tech event (was Partnership)

### 3.3 Feed Verification Health
**Chains with NO YouTube channel:**
1. Bitcoin
2. Plasma
3. Stablechain

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

## 3. Event Categories (7)

```
┌─────────────────────────────────────────────────────────┐
│                    EVENT TAXONOMY                        │
├──────────────┬──────────────────────────────────────────┤
│ Tech event   │ Mainnet launches, upgrades, audits,      │
│              │ infrastructure changes, governance       │
│              │ proposals (EIPs, BIPs, SIMDs, etc.)      │
├──────────────┼──────────────────────────────────────────┤
│ Partnership  │ Integrations, collaborations, co-launches│
├──────────────┼──────────────────────────────────────────┤
│ Regulatory   │ Licenses, approvals, bans, enforcement   │
├──────────────┼──────────────────────────────────────────┤
│ Risk alert   │ Hacks, exploits, outages, critical bugs  │
├──────────────┼──────────────────────────────────────────┤
│ Visibility   │ Conferences, hackathons, AMAs, hires,    │
│              │ departures                               │
├──────────────┼──────────────────────────────────────────┤
│ Financial    │ TVL/volume/fees milestones, TGEs,        │
│              │ funding rounds, grants, incentive        │
│              │ programs                                 │
├──────────────┼──────────────────────────────────────────┤
│ NEWS         │ General crypto news without specific     │
│              │ chain attribution or category match      │
└──────────────┴──────────────────────────────────────────┘
```

**Governance proposals are classified under TECH EVENT** — they represent proposed protocol changes. A governance proposal that passes is a TECH EVENT with higher urgency. A controversial proposal that splits the community may also get a RISK ALERT secondary tag.

---

## 4. Data Sources — Per Category

### 4.1 TECH EVENT (including Governance)

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| GitHub API (repos + releases) | Structured API | Free token (5000 req/hr) | All chains | ✓ Implemented |
| Chain-specific blogs (RSS) | Semi-structured | None | 28 chains (see Section 2.1) | ✓ Implemented |
| Coinpedia Events RSS | Semi-structured | None | General events | ✓ In sources.yaml |
| TradingView (Playwright scraper) | Scraped | None | All crypto news | ✓ Implemented (Chromium) |
| **Governance forums** | RSS/scraper | None | 18 chains (see table above) | Partially implemented |
| **GitHub proposal repos** | Structured API | Free token | 7 chains (BIPs, SIMDs, BEPs, etc.) | Partially implemented |
| CryptoRank | Structured API | Free tier (Core) | Major chains | ✓ For project data only (Events API dead) |

**Note:** CryptoRank Events API (`/v1/events`) returns 404 — dead as of Apr 2026. CryptoRank used for project data/rankings only. Events sourced from Coinpedia RSS + news feeds + TradingView scraper.

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

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| RSS News feeds | Semi-structured | None | All chains | ✓ Implemented (7 feeds: CoinDesk, The Block, Cointelegraph, NewsBTC, 99Bitcoins, Decrypt, Blockworks) |
| CryptoSlate RSS | Semi-structured | None | All chains | ✓ In sources.yaml |
| CoinGape RSS | Semi-structured | None | All chains | ✓ In sources.yaml |
| Bitcoin.com News RSS | Semi-structured | None | All chains | ✓ In sources.yaml |
| AMBCrypto RSS | Semi-structured | None | All chains | ✓ In sources.yaml |
| DefiLlama Protocol pages | Structured API | None | All DeFi chains | ✓ Implemented |
| TradingView (Playwright scraper) | Scraped | None | All crypto news | ✓ Implemented (Chromium) |
| CryptoRank | Structured API | Free tier (Core) | Major chains | ✓ For project data (Events API dead) |

**Design thinking:** News RSS feeds catch partnership announcements. DefiLlama is the "proof of life" — when TVL appears on a new chain, the partnership is real. TradingView scraper catches additional stories not in RSS feeds. CryptoRank Events API is dead — don't use it.

---

### 4.3 REGULATORY

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| CoinCenter RSS | Curated | None | US + global | ✓ In sources.yaml |
| DeFi Education Fund RSS | Curated | None | US-focused | ✓ In sources.yaml |
| SEC EDGAR EFTS | Structured | None | US-focused | ⚠️ Planned (not yet in sources.yaml) |
| EU MiCA Portal | Structured | None | EU-focused | ⚠️ Planned |
| FATF Updates | Structured | None | Global | ⚠️ Planned |
| Lexology / Mondaq RSS | Semi-structured | None | Global | ⚠️ Planned |
| HK SFC Announcements | Structured | None | X Layer (OKX is HK-based) | ⚠️ Planned |
| RSS News feeds (filtered) | Semi-structured | None | All chains | ✓ Implemented (categorizer classifies regulatory items) |

**Design thinking:** Regulatory is binary — either there's an active enforcement action or there isn't. CoinCenter + DeFi Education Fund RSS covers policy blog posts. News feeds catch breaking regulatory stories via categorizer keyword matching.

**SEC EDGAR crypto-specific monitoring:**
- General RSS: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=40&action=getcompany` (keyword filter required)
- Crypto keyword filter: `crypto OR blockchain OR defi OR "digital asset" OR token OR stablecoin`
- Specific companies to watch: Coinbase, MicroStrategy, Grayscale, BlackRock (IBIT), Ripple
- HK SFC: `https://www.sfc.hk/en/Rules-and-standards/Circulars-and-announcements` (scrape)

---

### 4.4 RISK ALERT

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| DefiLlama protocols (TVL crash detection) | Structured API | None | All DeFi | ✓ Implemented (>50% TVL drop on $1M+ protocols) |
| RSS News feeds (filtered) | Semi-structured | None | All chains | ✓ Implemented (categorizer classifies risk items) |
| Rekt News | Semi-structured | None | All chains | ⚠️ Planned |
| Immunefi Bug Bounty Dashboard | Structured | None | Chains with bounties | ⚠️ Planned |
| Chain status pages | Structured | Varies | Major chains | ⚠️ Planned |
| GitHub Issues (critical) | Structured API | Free token | All chains | ⚠️ Planned |
| DeFiLlama Hacks endpoint | Structured API | Paid (402) | All DeFi | ✗ Paid endpoint — use TVL crash detection instead |

**Design thinking:** DefiLlama `/hacks` endpoint requires paid plan (402). Alternative: detect >50% TVL drops on $1M+ protocols from free `/protocols` endpoint. News feeds catch security incidents via categorizer keyword matching.

---

### 4.5 VISIBILITY EVENT

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| RSS News feeds (filtered) | Semi-structured | None | All chains | ✓ Implemented (categorizer classifies visibility items) |
| CryptoRank | Structured API | Free tier (Core) | Major chains | ✓ For team/org data (Events API dead) |
| Conference calendars (ethereum.org, ETHGlobal) | Scraped | None | Ethereum + ecosystem | ✓ Implemented (Camoufox for ETHGlobal) |
| Hackathon outcomes (ETHGlobal, Solana, Devpost) | Scraped | Camoufox | Past events | ✓ Implemented |
| YouTube (chain channels) | API | Free (quota-limited) | 20 chains | ⚠️ Planned (YouTube API key available) |
| Podcast RSS feeds | RSS | None | 13 feeds | ✓ Implemented |

**Verified podcast feeds (in sources.yaml under `rss_feeds.podcasts`):**
- Bankless: `https://feeds.simplecast.com/82FI35Px` ✓ (496 eps, general crypto)
- Unchained: `https://unchained.libsyn.com/rss` ✓ (1121 eps, general crypto)
- What Bitcoin Did: `https://whatbitcoindid.libsyn.com/rss` ✓ (1042 eps, bitcoin)
- Lightspeed: `https://feeds.megaphone.fm/lightspeed` ✓ (277 eps, solana)
- The Defiant: `https://thedefiant.io/api/feed` ✓ (100 eps, defi)
- The Scoop: `https://feeds.megaphone.fm/the-scoop` ✓ (105 eps, general)
- Empire: `https://feeds.megaphone.fm/empire` ✓ (634 eps, general)
- 0xResearch: `https://feeds.megaphone.fm/0xresearch` ✓ (303 eps, research)
- Bell Curve: `https://feeds.megaphone.fm/bellcurve` ✓ (341 eps, general)
- Tales from the Crypt: `https://talesfromthecrypt.libsyn.com/rss` ✓ (100 eps, bitcoin)
- Thinking Crypto: `https://www.thinkingcrypto.com/feed` ✓ (general)
- Week in Ethereum: `https://weekinethereum.substack.com/feed` ✓ (ethereum)
- The Breakdown: `https://feeds.megaphone.fm/the-breakdown` ✓ (general)

**Design thinking:** Visibility events are weakest individually, strongest in aggregate. Conference + AMA + hiring cluster = momentum signal. Conference dates filtered to 2-week window (past events clutter the digest). Hackathon outcomes show where developer attention is going.

---

### 4.6 FINANCIAL

| Source | Type | Auth | Coverage | Status |
|--------|------|------|----------|--------|
| DefiLlama (TVL, fees, revenue, volume) | Structured API | None | 200+ chains | ✓ Implemented |
| CoinGecko (market cap, price, volume) | Structured API | Free tier (30 req/min) | All tokens | ✓ Implemented |
| DefiLlama Stablecoins | Structured API | None | All chains | ✓ Implemented |
| DefiLlama Unlocks | Structured API | None | Token-specific | ⚠️ Planned |
| CoinGecko CLI | CLI | Free (installed) | One-off queries | ✓ Available |

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
| 5 | Critical | Fundamentals change. Protocol survival at stake. Major hack (>$10M), SEC enforcement, mainnet outage >2h, hard fork failure |
| 4 | High | Significant capability or market position change. Major upgrade, Tier-1 partnership, TVL milestone, regulatory approval, governance proposal passed |
| 3 | Notable | Meaningful but not transformative. New protocol deployment, conference keynote, funding round <$50M, audit completion, governance proposal in draft |
| 2 | Moderate | Incremental progress. Minor upgrade, small partnership, AMA, grant program |
| 1 | Low | Background activity. Routine commits, minor blog post |

### 6.2 Urgency Score (1-3)

| Score | Label | Criteria | Response Time |
|-------|-------|----------|---------------|
| 3 | Immediate | Active incident, market-moving, time-sensitive | <1 hour |
| 2 | Same-day | Important but not breaking | <24 hours |
| 1 | Weekly | Background context, trend data | Weekly digest |

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

| Source | Reliability | Notes |
|--------|-------------|-------|
| GitHub API | 0.95 | |
| DefiLlama API | 0.95 | |
| SEC EDGAR | 0.95 | |
| Chain status pages | 0.90 | |
| CoinGecko | 0.90 | |
| CryptoRank | 0.80 | Good coverage, free tier. Events API dead — use for project data only. |
| Official governance forums | 0.85 | |
| CoinDesk / The Block | 0.80 | |
| Rekt News | 0.80 | |
| RSS News feeds (general) | 0.75 | Categorizer re-classifies into specific categories |
| TradingView scraper | 0.75 | JS-rendered, requires Playwright |
| Coinpedia Events | 0.65 | |
| Community forums | 0.50 | |

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
│ • DefiLlama  │     │ • Classify   │     │ • Telegram   │
│ • CoinGecko  │     │ • Score      │     │   daily +    │
│ • GitHub     │     │ • Reinforce  │     │   weekly     │
│ • RSS (12    │     │ • Enrich     │     │ • Markdown   │
│   feeds +    │     │              │     │   (weekly)   │
│   15 chain   │     │              │     │ • JSON       │
│   blogs)     │     │              │     │   (archive)  │
│ • Regulatory │     │              │     │              │
│ • RiskAlert  │     │              │     │              │
│ • TradingView│     │              │     │              │
│   (Playwright│     │              │     │              │
│   Chromium)  │     │              │     │              │
│ • Events     │     │              │     │              │
│   (ETHGlobal,│     │              │     │              │
│   ethereum.  │     │              │     │              │
│   org, Devpost│    │              │     │              │
│   via Camoufox│    │              │     │              │
│ • Hackathon  │     │              │     │              │
│   Outcomes   │     │              │     │              │
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

**Verified Discourse JSON API endpoints:**
| Forum | URL | Status |
|-------|-----|--------|
| Ethereum Magicians | `ethereum-magicians.org/latest.json` | ✓ |
| Arbitrum | `forum.arbitrum.foundation/latest.json` | ✓ |
| Polygon | `forum.polygon.technology/latest.json` | ✓ |
| OP Mainnet | `gov.optimism.io/latest.json` | ✓ |
| Mantle | `forum.mantle.xyz/latest.json` | ⚠️ |
| Monad | `forum.monad.xyz/latest.json` | ⚠️ |
| Sui | `forums.sui.io/latest.json` | ✓ |
| Starknet | `community.starknet.io/latest.json` | ✓ |
| Gnosis | forum.gnosis.io (Snapshot-based, no Discourse) | ✗ |
| NEAR | `gov.near.org/latest.json` | ✓ |
| Aptos | `forum.aptosfoundation.org/latest.json` | ✓ |

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

Only 1 chain requires scraping: Bitcoin. X Layer now has RSS (`www.xlayer.xyz/blog/rss.xml`). TON now has RSS (`ton.org/en/newsroom/rss`). Hyperliquid and Morph have RSS feeds (Medium and blog.morph.network respectively).

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
- RSS: `https://medium.com/feed/@hyperliquid` ✓ (in sources.yaml — no scraping needed)
- Scrape fallback: `https://app.hyperliquid.xyz/announcements` (only if RSS fails)
- Check for hidden JSON endpoint: `https://api.hyperliquid.xyz/info` (may expose announcements)

X Layer:
- RSS: `https://www.xlayer.xyz/blog/rss.xml` ✓ (NEW — in sources.yaml)
- Website: `https://www.xlayer.xyz` ✓ (independent site, not just OKX)
- Fallback scrape: `https://www.okx.com/help/section/announcements-latest-announcements` (filter for X Layer)
- Status page: `https://www.xlayer.xyz/status` ✓

Morph:
- RSS: `https://blog.morph.network/feed` ✓ (migrated from morphl2.io — in sources.yaml)
- Substack: `https://morph.substack.com/feed` ✓ (additional source, peer-level)

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

🧠 Today's theme
AI/Agents convergence: 3 chains entered AI this week (Monad, Base, Virtuals).
Attention is shifting from L2 infrastructure to application-specific chains.

🔴 Critical (Score ≥10)
[none today]

🟠 High (Score 8-9)
• Ethereum: Pectra upgrade date confirmed for May 7 [ethereum.org, Messari, CoinDesk — 3x]
  Category: Tech event | Impact: 4 | Urgency: 2

• X Layer: TVL crosses $500M, up 34% this week [DefiLlama]
  Category: Financial | Impact: 4 | Urgency: 2

🟡 Notable (Score 6-7)
• Monad: announces 12 new ecosystem partners at Token2049 [X, Messari — 2x]
  Category: Partnership | Impact: 3 | Urgency: 2

• Arbitrum: AIP-112 "Treasury diversification" enters voting [forum.arbitrum.foundation]
  Category: Tech event | Impact: 3 | Urgency: 2

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

**Digest formatting rules:**
- Telegram delivery: Markdown parse_mode with [Title](URL) links embedded on signal titles
- Never HTML <a> tags (Telegram doesn't render them)
- No "Why" lines in digest output (low value)
- No price/financial content in digests
- Partnerships shown as separate section
- Only major releases with release notes in tech events (filter fix/feat/build PRs)

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

🟠 High
• MIP-3 "Validator incentive restructuring" passed vote
  Sources: forum.monad.xyz (3x reinforced)
  Detected: Apr 12 | Confidence: 0.95

🟡 Notable
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
| Daily digest completeness | All 7 categories represented when events exist | Daily review |
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

| Category | Primary Sources | Backup Sources | Chains Covered | Status |
|----------|----------------|----------------|----------------|--------|
| TECH EVENT | GitHub API (27 chains), RSS blogs (27 chains), TradingView scraper, Coinpedia Events | CryptoRank (project data) | 27/27 (scrape for Bitcoin/XLayer) | ✓ |
| PARTNERSHIP | RSS news (11 feeds), TradingView scraper | DefiLlama (indirect — TVL appearance = proof) | 27/27 | ✓ |
| REGULATORY | CoinCenter RSS, DeFi Education Fund RSS, RSS news (filtered) | SEC EDGAR, HK SFC (planned) | Global | Partial |
| RISK ALERT | DefiLlama TVL crash detection, RSS news (filtered) | Rekt News, Immunefi (planned) | 27/27 | Partial |
| VISIBILITY | Conference calendars (ethereum.org, ETHGlobal), Hackathon outcomes, RSS news (filtered), Podcast RSS (13 feeds) | YouTube API (planned) | 27/27 | ✓ |
| FINANCIAL | DefiLlama (27 chains), CoinGecko (23 tokens) | CoinGecko CLI (installed) | 23/27 with token data | ✓ |

**RSS Feeds Implemented (82 total: 7 news + 2 regulatory + 4 partnership + 1 event + 55 chain blogs + 13 podcasts):**
- News: CoinDesk, The Block, Cointelegraph, NewsBTC, 99Bitcoins, Decrypt, Blockworks
- Regulatory: CoinCenter, DeFi Education Fund
- Partnerships: CryptoSlate, CoinGape, Bitcoin.com News, AMBCrypto
- Events: Coinpedia Events
- **New chain blogs (Apr 2026):** TON newsroom, X Layer blog, Ink blog, Sei blog, Morph blog (migrated domain)
- **New Substack feeds (Apr 2026):** BSC, Mantle, Hyperliquid, Morph, Tempo, Plasma, Polygon, NEAR, Optimism, Aptos, Monad, Ink, Sei
- **New governance APIs:** 10 Discourse forums with `/latest.json` endpoints
- **New status pages:** Ink (inkonchain.com/status), X Layer (xlayer.xyz/status)
- **New foundations/sites:** Hyperliquid Foundation (hyperfoundation.org), X Layer (xlayer.xyz), Morph (morph.network)

**Key domain corrections (Apr 2026):**
- Plasma: `.com` → `.to` (plasma.com is a German company, chain is plasma.to)
- Morph: `morphl2.io` → `morph.network` (domain migrated)

**Collectors Implemented:** DefiLlama, CoinGecko, GitHub, RSS (all categories), Regulatory (CoinCenter + DeFi Education Fund), RiskAlert (TVL crash), TradingView (Playwright Chromium), Events (ethereum.org + ETHGlobal via Camoufox), HackathonOutcomes (ETHGlobal + Solana + Devpost)

**Planned (not yet in sources.yaml):** SEC EDGAR EFTS, YouTube API, Rekt News, Immunefi, EU MiCA portal, FATF updates, HK SFC announcements

**Newly added to sources.yaml (Apr 2026):** TON newsroom RSS, TON ecosystem RSS, BSC Substack, Mantle Substack, Hyperliquid Substack, Morph blog RSS (migrated), Morph Substack, Tempo Substack, Plasma Substack, Sei blog RSS, Sei Substack, Ink blog RSS, Ink Substack, Ink press RSS, X Layer blog RSS, Polygon Substack, NEAR Substack, Optimism Substack, Aptos Substack, Monad Substack, Bitcoin Core releases RSS, EIPs RSS, Solana Foundation RSS (blog/news/grants)

**Per-chain source config:** See Section 2.1 for complete GitHub repos, RSS URLs, YouTube channels, and status pages for all 27 chains.

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
