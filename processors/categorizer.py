"""Event categorizer — agent-native.

No keyword matching. No LLM calls. No deterministic rules.
The running agent reads prepared tasks and provides all categorization reasoning.

This module still exports CATEGORY_KEYWORDS, SUBCATEGORY_MAP, and related
reference data — but ONLY for inclusion in agent prompts as guidance.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from processors.agent_native import save_agent_task, find_agent_output, load_agent_output

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference data — included in agent prompts, NOT used for code-side matching
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "RISK_ALERT",
    "REGULATORY",
    "FINANCIAL",
    "PARTNERSHIP",
    "TECH_EVENT",
    "VISIBILITY",
    "NOISE",
    "NEWS",
]

CATEGORY_DESCRIPTIONS = {
    "RISK_ALERT": "Security incidents: hacks, exploits, vulnerabilities, outages, critical bugs, bridge compromises",
    "REGULATORY": "Government actions: SEC/CFTC/DOJ enforcement, licensing, compliance, legislation, Wells notices",
    "FINANCIAL": "Capital events: TVL milestones, funding rounds, token launches, airdrops, treasury, revenue, grants",
    "PARTNERSHIP": "Business development: integrations, collaborations, deployments on chain, ecosystem joins, alliances",
    "TECH_EVENT": "Protocol changes: mainnet launches, upgrades, hard forks, audits, governance proposals, EIP/BIP",
    "VISIBILITY": "Community presence: conferences, AMAs, keynotes, hires, departures, podcasts, hackathons",
    "NOISE": "Low-signal content: engagement bait, price predictions, memes, gm/gn, threadooors, follow-for-alpha",
    "NEWS": "General news that does not fit the above categories",
}

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
        "partnership", "partners with", "in partnership", "partnered",
        "integration", "integrate with", "integrated into",
        "collaboration", "collaborates with", "co-launch",
        "joint", "together with", "teams up", "joins forces",
        "deployed on", "live on", "launches on", "available on",
        "adds support for", "now on", "now live on", "goes live on",
        "expands to", "enters", "comes to", "migrates to",
        "built on", "powered by", "powered on",
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

SUBCATEGORY_MAP = {
    "RISK_ALERT": {
        "hack": "hack, exploit, drained, stolen, attack",
        "outage": "outage, downtime, halt, offline",
        "critical_bug": "critical bug, vulnerability, cve",
    },
    "REGULATORY": {
        "enforcement": "enforcement, lawsuit, subpoena, wells notice, fine, penalty",
        "license": "license, approval, authorized",
        "comment_period": "comment period, proposed rule, consultation",
    },
    "FINANCIAL": {
        "tvl_milestone": "tvl crosses/reaches milestone",
        "tvl_spike": "tvl up/increase/surge",
        "volume_breakout": "volume ath/record/breakout",
        "funding_round": "funding, raised, series, round",
        "airdrop": "airdrop, token distribution",
        "tge": "tge, token launch, token generation",
    },
    "TECH_EVENT": {
        "mainnet_launch": "mainnet launch, mainnet live, genesis",
        "upgrade": "upgrade, hard fork, eip, bip, simd",
        "release": "release, version, v0, v1, v2",
        "governance_submitted": "proposal submitted, draft, rfc",
        "governance_passed": "proposal passed, approved, accepted",
        "audit": "audit, audited, security review",
    },
    "PARTNERSHIP": {
        "integration": "integration, integrate, deploy on",
        "collaboration": "partnership, collaboration, teams up",
    },
    "VISIBILITY": {
        "keynote": "keynote, conference talk, speaker",
        "ama": "ama, ask me anything, community call",
        "hire": "hired, joined, appointed, new cto, new ceo",
        "departure": "departed, left, stepped down, resigned",
        "podcast": "podcast, interview, episode",
    },
}

TWITTER_NOISE_PHRASES = [
    "gm ", "gm!", "gn ", "gn!", "wagmi", "ngmi",
    "number go up", "number go down", "buy the dip", "sell the top",
    "to the moon", "moon soon", "lambo", "wen lambo",
    "threadooor", "threadoor", "1/ 🧵", "1/ thread", "1/\n🧵",
    "like + rt", "like and rt", "like and retweet", "like + retweet",
    "follow for", "follow me", "follow us", "don't miss", "don't skip",
    "drop a", "comment below", "let us know", "what do you think",
    "rate this", "top 10", "top 5", "list thread", "mini thread",
    "alpha inside", "free alpha", "here is alpha",
]

PRICE_NOISE_KEYWORDS = [
    "price prediction", "price forecast", "price target", "price analysis",
    "technical analysis", "chart pattern", "support level", "resistance level",
    "bull case", "bear case", "bullish", "bearish", "rally", "selloff",
    "bottom", "top signal", "breakout", "consolidation", "pullback",
    "correction", "dip", "surge", "plunge", "soars", "tumbles",
    "slides", "falls", "rises", "drops", "jumps", "gains", "loses",
    "what the", "here's what", "what you should", "what to",
    "should you buy", "should you sell", "is it time to",
    "analysts say", "traders bet", "market sentiment",
    "funding rate", "open interest", "long position", "short position",
    "liquidation", "leverage", "margin call",
    "could hit", "could reach", "might", "set to", "poised to",
    "what's next for", "where", "headed", "outlook",
    "relief rally", "selling pressure", "buying pressure",
    "whale transaction", "whale moves", "whale transfers",
    "can .* defend", "can .* survive", "can .* hold",
    "defend $", "survive $", "hold $", "above $", "below $",
    "support test", "resistance test", "price falls", "price slides",
    "price drops", "price jumps", "price surges",
]

# ---------------------------------------------------------------------------
# Agent-native EventCategorizer
# ---------------------------------------------------------------------------

class EventCategorizer:
    """Agent-native event categorizer.

    No keyword matching. Prepares structured tasks for the running agent,
    loads agent-completed results, and applies them to raw events.

    Usage (pipeline):
        categorizer = EventCategorizer()
        task_path = categorizer.prepare_agent_task(events)
        # AGENT CHECKPOINT: running agent processes task and saves output
        results = categorizer.try_load_results()
        categorized_events = categorizer.apply_categories(events, results)
    """

    TASK_TYPE = "categorize"

    def categorize(self, event: dict) -> dict:
        """DEPRECATED — agent-native pipeline does not use keyword categorization.

        Raises RuntimeError with instructions for the agent-native flow.
        """
        raise RuntimeError(
            "EventCategorizer is agent-native. Keyword categorization has been removed.\n"
            "Use: prepare_agent_task() → agent processes → try_load_results() → apply_categories()\n"
            "The running agent must provide all categorization reasoning."
        )

    # -- Agent task preparation ------------------------------------------------

    def prepare_agent_task(self, events: list[dict]) -> Path:
        """Build and save a categorization task for the running agent.

        Returns the path to the saved task file.
        """
        task_events = []
        for i, ev in enumerate(events):
            task_ev = {
                "id": i,
                "chain": ev.get("chain", "unknown"),
                "source": ev.get("source", "") or ev.get("source_name", ""),
                "description": ev.get("description", ""),
                "reliability": ev.get("reliability", 0.5),
                "evidence": self._flatten_evidence(ev.get("evidence", {})),
                "is_twitter": "twitter" in str(ev.get("source", "")).lower(),
            }
            # Include tweet-specific metadata when present
            evidence = ev.get("evidence", {}) if isinstance(ev.get("evidence"), dict) else {}
            if evidence.get("is_retweet"):
                task_ev["twitter_metadata"] = {
                    "is_retweet": True,
                    "original_author": evidence.get("original_author", ""),
                }
            if evidence.get("is_quote"):
                task_ev["twitter_metadata"] = task_ev.get("twitter_metadata", {})
                task_ev["twitter_metadata"]["is_quote"] = True
                task_ev["twitter_metadata"]["quoted_text"] = evidence.get("quoted_text", "")
            if evidence.get("author"):
                task_ev["twitter_metadata"] = task_ev.get("twitter_metadata", {})
                task_ev["twitter_metadata"]["author"] = evidence.get("author", "")
                task_ev["twitter_metadata"]["role"] = evidence.get("role", "unknown")

            task_events.append(task_ev)

        payload = {
            "instructions": self._build_agent_instructions(),
            "events": task_events,
            "output_format": self._build_output_format(),
        }
        return save_agent_task(self.TASK_TYPE, payload)

    def try_load_results(self, task_id: Optional[str] = None) -> Optional[list[dict]]:
        """Attempt to load agent categorization results.

        Returns None if no output is available yet.
        """
        output_path = find_agent_output(self.TASK_TYPE, task_id=task_id)
        if output_path is None:
            return None
        try:
            data = load_agent_output(output_path)
            results = data.get("results", [])
            logger.info(f"[categorizer] Loaded {len(results)} agent-categorized events from {output_path}")
            return results
        except Exception as exc:
            logger.warning(f"[categorizer] Failed to load agent output: {exc}")
            return None

    def apply_categories(self, events: list[dict], categorized_results: list[dict]) -> list[dict]:
        """Apply agent categorization results to raw events.

        Returns a new list of event dicts with category, subcategory, and semantic fields.
        """
        result_map = {r["id"]: r for r in categorized_results if "id" in r}
        enriched = []

        for i, ev in enumerate(events):
            ev_copy = dict(ev)
            if i in result_map:
                r = result_map[i]
                cat = r.get("category", "NEWS")
                sub = r.get("subcategory", "general")
                ev_copy["category"] = cat
                ev_copy["subcategory"] = sub
                ev_copy["semantic"] = {
                    "category": cat,
                    "subcategory": sub,
                    "confidence": 0.85,
                    "reasoning": r.get("reasoning", ""),
                    "is_noise": r.get("is_noise", False),
                    "primary_mentions": r.get("primary_mentions", []),
                }
            else:
                # Event was not categorized by agent — mark as NEWS/general
                ev_copy["category"] = "NEWS"
                ev_copy["subcategory"] = "general"
                ev_copy["semantic"] = {
                    "category": "NEWS",
                    "subcategory": "general",
                    "confidence": 0.0,
                    "reasoning": "Not categorized by agent",
                    "is_noise": False,
                    "primary_mentions": [],
                }
            enriched.append(ev_copy)

        categorized_count = sum(1 for e in enriched if e.get("semantic", {}).get("confidence", 0) > 0)
        logger.info(f"[categorizer] Applied agent categories to {categorized_count}/{len(events)} events")
        return enriched

    # -- Instruction builders --------------------------------------------------

    def _build_agent_instructions(self) -> str:
        """Build rich categorization instructions for the agent prompt."""
        cat_lines = []
        for cat in CATEGORY_ORDER:
            desc = CATEGORY_DESCRIPTIONS.get(cat, "")
            cat_lines.append(f"  - {cat}: {desc}")

        subcat_lines = []
        for cat, subcats in SUBCATEGORY_MAP.items():
            subcat_lines.append(f"  {cat}:")
            for sub, desc in subcats.items():
                subcat_lines.append(f"    - {sub}: {desc}")

        noise_lines = "\n    ".join(f"- '{phrase}'" for phrase in TWITTER_NOISE_PHRASES[:10])
        price_lines = "\n    ".join(f"- '{kw}'" for kw in PRICE_NOISE_KEYWORDS[:10])

        return (
            "You are an expert crypto-industry analyst. Categorize each event into exactly one category and subcategory.\n\n"
            "Categories (ordered by priority — first match wins when multiple could apply):\n"
            f"{chr(10).join(cat_lines)}\n\n"
            "Subcategories:\n"
            f"{chr(10).join(subcat_lines)}\n\n"
            "Rules:\n"
            "1. Categorize by SEMANTIC CONTENT, not keyword presence.\n"
            "2. A 'wen mainnet' reply to a mainnet announcement is VISIBILITY, not TECH_EVENT.\n"
            "3. A retweet of official news inherits the original's category.\n"
            "4. Funding announcements with amounts >= $1M receive FINANCIAL.\n"
            "5. 'Audit complete' without findings → TECH_EVENT. 'Audit finding' → RISK_ALERT.\n"
            "6. Engagement bait, price predictions, memes → NOISE.\n"
            "7. If chain-agnostic (mentions no specific chain), set primary_mentions to [].\n"
            "8. For retweets: categorize based on the ORIGINAL content, not the reposter's commentary.\n"
            "9. For quote tweets: categorize based on the new commentary + quoted content combined.\n"
            "10. When in doubt between two categories, pick the one with higher real-world impact.\n\n"
            "Noise filters (mark as NOISE / is_noise=true if primarily these):\n"
            f"    {noise_lines}\n"
            "    ... (and similar low-value phrases)\n\n"
            "Price noise filters (mark as NOISE if primarily these):\n"
            f"    {price_lines}\n"
            "    ... (and similar price-commentary phrases)\n"
        )

    def _build_output_format(self) -> str:
        return (
            "Return a JSON array of results, one per event, in the SAME ORDER as the input events.\n"
            "Each result must be:\n"
            "{\n"
            '  "id": <event id from input>,\n'
            '  "category": "<CATEGORY>",\n'
            '  "subcategory": "<subcategory>",\n'
            '  "reasoning": "<1 sentence explaining the classification>",\n'
            '  "is_noise": <true/false>,\n'
            '  "primary_mentions": [<list of chain names mentioned, or []>]\n'
            "}\n\n"
            "CRITICAL: every event in the input must have a corresponding result with the correct id.\n"
            "Do not skip events. Do not invent events. Do not return markdown fences.\n"
        )

    @staticmethod
    def _flatten_evidence(evidence) -> dict:
        """Normalize evidence field to a flat dict for the agent prompt."""
        if isinstance(evidence, dict):
            return {k: str(v) for k, v in evidence.items()}
        return {"raw": str(evidence)}
