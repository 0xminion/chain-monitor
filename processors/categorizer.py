"""Event categorizer — classifies raw events into categories."""

import logging

logger = logging.getLogger(__name__)

# Keywords mapping to categories (order matters — first match wins)
CATEGORY_KEYWORDS = {
    "RISK_ALERT": [
        "hack", "exploit", "vulnerability", "outage", "downtime", "halt",
        "critical bug", "drained", "stolen", "attack", "compromised",
        "bridge hack", "rug pull", "scam", "breach", "incident",
        "emergency", "paused", "frozen", "blackhat", "whitehat",
        "bug bounty", "responsible disclosure",
    ],
    "REGULATORY": [
        "sec enforcement", "sec charges", "sec sues", "sec filing",
        "enforcement", "lawsuit", "ban", "prohibition", "license",
        "approval", "regulation", "compliance", "fine", "penalty",
        "wells notice", "subpoena", "mica", "fatf", "sfc",
        "broker registration", "cftc", "doj", "treasury",
        "stablecoin bill", "crypto bill", "executive order",
        "comment period", "proposed rule",
    ],
    "FINANCIAL": [
        "tvl", "volume", "funding", "raised", "grant", "airdrop",
        "tge", "token launch", "token sale", "milestone", "$",
        "million", "billion", "inflows", "outflows",
        "buyback", "treasury", "yield", "revenue",
    ],
    "PARTNERSHIP": [
        # Explicit partnership language
        "partnership", "partners with", "in partnership", "partnered",
        "integration", "integrate with", "integrated into",
        "collaboration", "collaborates with", "co-launch",
        "joint", "together with", "teams up", "joins forces",
        # Deployment / availability language (implies integration)
        "deployed on", "live on", "launches on", "available on",
        "adds support for", "now on", "now live on", "goes live on",
        "expands to", "enters", "comes to", "migrates to",
        "built on", "powered by", "powered on",
        # Business development language
        "alliance", "consortium", "works with", "works alongside",
        "signs mou", "memorandum", "strategic", "cooperation",
        "ecosystem partner", "joins ecosystem", "joins network",
    ],
    "TECH_EVENT": [
        "upgrade", "mainnet", "testnet", "launch", "release",
        "audit", "eip", "bip", "simd", "mip", "aip", "pip",
        "hard fork", "soft fork", "deploy", "proposal", "vote",
        "governance", "feature", "update", "version",
        "devnet", "canary", "release candidate", "rc1", "rc2",
    ],
    "VISIBILITY": [
        "conference", "hackathon", "ama", "interview", "keynote",
        "hired", "joined", "departed", "appointed", "podcast",
        "speaker", "panel", "summit", "workshop", "demo day",
        "live stream", "community call", "town hall",
        "new ceo", "new cto", "new coo", "new head of",
        "resigned", "stepped down", "leaving", "replacement",
    ],
}

# Subcategory detection
SUBCATEGORY_MAP = {
    "RISK_ALERT": {
        "hack": ["hack", "exploit", "drained", "stolen", "attack"],
        "outage": ["outage", "downtime", "halt", "offline"],
        "critical_bug": ["critical bug", "vulnerability", "cve"],
    },
    "REGULATORY": {
        "enforcement": ["enforcement", "lawsuit", "subpoena", "wells notice", "fine", "penalty"],
        "license": ["license", "approval", "authorized"],
        "comment_period": ["comment period", "proposed rule", "consultation"],
    },
    "FINANCIAL": {
        "tvl_milestone": ["tvl", "crosses", "reaches", "milestone"],
        "tvl_spike": ["tvl", "up", "increase", "surge"],
        "volume_breakout": ["volume", "ath", "record", "breakout"],
        "funding_round": ["funding", "raised", "series", "round"],
        "airdrop": ["airdrop", "token distribution"],
        "tge": ["tge", "token launch", "token generation"],
    },
    "TECH_EVENT": {
        "mainnet_launch": ["mainnet launch", "mainnet live", "genesis"],
        "upgrade": ["upgrade", "hard fork", "eip", "bip", "simd"],
        "release": ["release", "version", "v0", "v1", "v2"],
        "governance_submitted": ["proposal submitted", "draft", "rfc"],
        "governance_passed": ["proposal passed", "approved", "accepted"],
        "audit": ["audit", "audited", "security review"],
    },
    "PARTNERSHIP": {
        "integration": ["integration", "integrate", "deploy on"],
        "collaboration": ["partnership", "collaboration", "teams up"],
    },
    "VISIBILITY": {
        "keynote": ["keynote", "conference talk", "speaker"],
        "ama": ["ama", "ask me anything", "community call"],
        "hire": ["hired", "joined", "appointed", "new cto", "new ceo"],
        "departure": ["departed", "left", "stepped down", "resigned"],
        "podcast": ["podcast", "interview", "episode"],
    },
}


# Price/trading noise to filter out of FINANCIAL category
PRICE_NOISE_KEYWORDS = [
    # Price predictions and analysis
    "price prediction", "price forecast", "price target", "price analysis",
    "technical analysis", "chart pattern", "support level", "resistance level",
    "bull case", "bear case", "bullish", "bearish", "rally", "selloff",
    "bottom", "top signal", "breakout", "consolidation", "pullback",
    "correction", "dip", "surge", "plunge", "soars", "tumbles",
    "slides", "falls", "rises", "drops", "jumps", "gains", "loses",
    # Market commentary
    "what the", "here's what", "what you should", "what to",
    "should you buy", "should you sell", "is it time to",
    "analysts say", "traders bet", "market sentiment",
    "funding rate", "open interest", "long position", "short position",
    "liquidation", "leverage", "margin call",
    # Speculative content
    "could hit", "could reach", "might", "set to", "poised to",
    "what's next for", "where", "headed", "outlook",
    "relief rally", "selling pressure", "buying pressure",
    "whale transaction", "whale moves", "whale transfers",
    # Price defense/milestone rhetoric
    "can .* defend", "can .* survive", "can .* hold",
    "defend $", "survive $", "hold $", "above $", "below $",
    "support test", "resistance test", "price falls", "price slides",
    "price drops", "price jumps", "price surges",
]


class EventCategorizer:
    """Classifies raw events into categories and subcategories."""

    def categorize(self, event: dict) -> dict:
        """Add category and subcategory to event dict."""
        # Build text for matching from all available fields
        text_parts = [event.get("description", "")]

        # Handle evidence as dict (extract title, summary) or string
        evidence = event.get("evidence", "")
        if isinstance(evidence, dict):
            text_parts.append(evidence.get("title", ""))
            text_parts.append(evidence.get("summary", ""))
            text_parts.append(evidence.get("pr_title", ""))
            text_parts.append(evidence.get("link", ""))
        else:
            text_parts.append(str(evidence))

        text = " ".join(str(p) for p in text_parts if p).lower()

        # Filter out price/trading noise from FINANCIAL
        # But NEVER filter DefiLlama TVL data (it's real on-chain data)
        source = event.get("source", "") or event.get("source_name", "")
        is_defillama = source in ("DefiLlama", "defillama") or "defillama" in str(event.get("evidence","")).lower()
        
        existing = event.get("category", "")
        if (existing == "FINANCIAL" or existing == "NEWS") and not is_defillama:
            for noise_kw in PRICE_NOISE_KEYWORDS:
                if noise_kw in text:
                    # Mark as filtered — digest can skip these
                    event["_filtered_price_noise"] = True
                    event["category"] = "PRICE_NOISE"
                    event["subcategory"] = "price_commentary"
                    return event

        # Don't override categories already set by collectors (e.g., DefiLlama → FINANCIAL)
        # EXCEPT for generic categories — re-categorize these into specific ones
        GENERIC_CATEGORIES = {"NEWS", "TECH_EVENT", "INFRASTRUCTURE", "ECOSYSTEM"}
        if existing and existing not in GENERIC_CATEGORIES:
            event["subcategory"] = self._detect_subcategory(text, existing)
            return event

        category = self._detect_category(text)
        subcategory = self._detect_subcategory(text, category)
        event["category"] = category
        event["subcategory"] = subcategory
        return event

    def _detect_category(self, text: str) -> str:
        """Detect primary category from text."""
        # Specific overrides: "live on mainnet/testnet" is tech, not partnership
        if "live on mainnet" in text or "live on testnet" in text or "goes live on mainnet" in text:
            return "TECH_EVENT"

        # Standard order: RISK > REGULATORY > FINANCIAL > PARTNERSHIP > TECH > VISIBILITY
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        return "TECH_EVENT"  # default

    def _detect_subcategory(self, text: str, category: str) -> str:
        """Detect subcategory within a category."""
        subcats = SUBCATEGORY_MAP.get(category, {})
        for subcat, keywords in subcats.items():
            for keyword in keywords:
                if keyword in text:
                    return subcat
        return "general"
