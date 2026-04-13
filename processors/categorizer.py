"""Event categorizer — classifies raw events into categories."""

import logging

logger = logging.getLogger(__name__)

# Keywords mapping to categories (order matters — first match wins)
CATEGORY_KEYWORDS = {
    "RISK_ALERT": [
        "hack", "exploit", "vulnerability", "outage", "downtime", "halt",
        "critical bug", "drained", "stolen", "attack", "compromised",
        "bridge hack", "rug pull", "scam",
    ],
    "REGULATORY": [
        "sec enforcement", "sec charges", "sec sues", "sec filing",
        "enforcement", "lawsuit", "ban", "prohibition", "license",
        "approval", "regulation", "compliance", "fine", "penalty",
        "wells notice", "subpoena", "mica", "fatf", "sfc",
    ],
    "FINANCIAL": [
        "tvl", "volume", "funding", "raised", "grant", "airdrop",
        "tge", "token launch", "token sale", "milestone", "$",
        "million", "billion", "inflows", "outflows",
    ],
    "PARTNERSHIP": [
        "partnership", "integration", "collaboration", "co-launch",
        "joint", "together with", "teams up", "announce",
    ],
    "TECH_EVENT": [
        "upgrade", "mainnet", "testnet", "launch", "release",
        "audit", "eip", "bip", "simd", "mip", "aip", "pip",
        "hard fork", "soft fork", "deploy", "proposal", "vote",
        "governance", "feature", "update", "version",
    ],
    "VISIBILITY": [
        "conference", "hackathon", "ama", "interview", "keynote",
        "hired", "joined", "departed", "appointed", "podcast",
        "speaker", "panel", "summit",
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

        # Don't override categories already set by collectors (e.g., DefiLlama → FINANCIAL)
        # EXCEPT for NEWS — re-categorize these
        existing = event.get("category", "")
        if existing and existing not in ("NEWS", "TECH_EVENT"):
            event["subcategory"] = self._detect_subcategory(text, existing)
            return event

        category = self._detect_category(text)
        subcategory = self._detect_subcategory(text, category)
        event["category"] = category
        event["subcategory"] = subcategory
        return event

    def _detect_category(self, text: str) -> str:
        """Detect primary category from text."""
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
