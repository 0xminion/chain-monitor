"""Weekly digest formatter — builds a rich markdown digest from cached daily
prompt files and standalone_summary JSONs.

No external LLM calls. Reads daily_prompt_*.md files from the past 7 days,
parses per-chain sections, dedupes events, and synthesizes one summary
bullet per chain under each theme.

Output rules:
  - Thematic heading gets a single emoji + bold text.
  - Chains: tag is on a new line immediately under the heading.
  - One bullet per chain under the theme.
  - Each bullet embeds a markdown link on the first content-bearing word.
  - Chain names in title case (not ALL CAPS).
  - Past tense.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
AGENT_INPUT_DIR = REPO_ROOT / "storage" / "agent_input"
DAILY_DIGEST_DIR = REPO_ROOT / "storage" / "twitter" / "summaries"

_STOP_WORDS = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "is", "are", "was",
    "were", "has", "have", "had", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "and", "or", "but", "it", "its", "we", "our", "your",
    "you", "can", "will", "now", "just", "here", "there", "what", "when", "they",
})


def _theme_of(text: str) -> tuple[str, str]:
    low = text.lower()
    rules = [
        (r"\bvisa|stablecoin.*settlement|payment.*rail|cross.border|remittance|xsgd|local.*stablecoin|cbMEGA\b", "💳", "Payments & Settlement"),
        (r"\bstablecoin.*credit|tokenized.*credit|credit.*fund|credit.*move|moving.*credit\b", "🏦", "Credit & Capital Markets"),
        (r"\bquantum|post.quantum|shrincs|shrimps|willow.*chip|quantum.*algorithm|cryptograph|quantic\b", "🔐", "Quantum & Security"),
        (r"\brwa|tokenized.*equit|real.world|asset.*tokeniz|tmo.*lab|securities|cmisa|bils\b", "🏛", "RWA & Tokenization"),
        (r"\bagentic|ai.*agent|nemo.claw|open.claw|iron.claw|claude.*code|agent.*commerce|agentic.*econom|moonagents\b", "🤖", "Agentic Commerce"),
        (r"\baave.*deposit|mega.eth|mega.*debut|tge|liquidity.*pour|perps|perpetual|jup_offerbook|defi.*standard|dex|derivative\b", "📊", "DeFi & Capital"),
        (r"\bclarity.*act|sec.*filing|sec.*etf|regulator|compliance|edgar|etp|senate.*clear|binance.*doj|etp|t\.rowe|wisdomtree|vaneck|etp\b", "⚖️", "Regulation & ETFs"),
        (r"\bconsensus|miami.*event|hackathon|squad.*america|sui.*live|conference|cohort|build.*x|accelerate\b", "🎯", "Events & Community"),
    ]
    for pattern, emoji, name in rules:
        if re.search(pattern, low):
            return (emoji, name)
    return ("📊", "Other Activity")


def _pick_anchor(text: str) -> Optional[str]:
    text = re.sub(r"[【】\[\]\(\)]", "", text)
    for w in re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", text):
        if len(w) >= 3 and w.lower() not in _STOP_WORDS:
            return w
    return None


def _to_past(text: str) -> str:
    subs = [
        (r"\bannounc(es|ed)\b", "announced"), (r"\blaunch(es)?\b", "launched"),
        (r"\bship(s|ped)\b", "shipped"), (r"\breleas(es)?\b", "released"),
        (r"\bdeploys?\b", "deployed"), (r"\bgoes live\b", "went live"),
        (r"\bintegrates?\b", "integrated"), (r"\bapproves?\b", "approved"),
        (r"\bcross(es)?\b", "crossed"), (r"\bhas been\b", "was"),
        (r"\bis now\b", "was"), (r"\bis currently\b", "was"),
        (r"\bplans to\b", "planned to"),
    ]
    for pat, repl in subs:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text


def _display_chain(chain: str) -> str:
    dc = chain.title()
    if dc == "Bsc":
        dc = "BSC"
    if dc == "Sei":
        dc = "SEI"
    if dc == "Near":
        dc = "NEAR"
    return dc


# ── Parse daily_prompt_*.md ────────────────────────────────────────────────

def _parse_daily_prompt(path: Path) -> list[dict]:
    """Parse a daily_prompt_*.md file, return list of event dicts."""
    text = path.read_text(encoding="utf-8")
    events = []
    lines = text.splitlines()
    i = 0
    current_chain = None
    current_topic = None

    while i < len(lines):
        line = lines[i]

        # Section header: ### N. CHAIN_NAME (Score: X, Sources: Y, Events: Z)
        m = re.match(r"###\s+\d+\.\s+(\w+)\s+\(", line)
        if m:
            current_chain = m.group(1).lower()
            i += 1
            continue

        # Dominant topic
        m = re.match(r"Dominant topic:\s*(.+)", line)
        if m:
            current_topic = m.group(1).strip()
            i += 1
            continue

        # Event lines
        m = re.match(r"\s+-\s+\[NEWS\]\s+(.+)", line)
        if m:
            current_event_text = m.group(1).strip()
            current_url = ""
            current_evidence = ""
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("-") and not re.match(r"###\s+\d+\.\s+\w+", lines[i].strip()):
                rest = lines[i].strip()
                if rest.startswith("URL:"):
                    url_match = re.search(r"URL:\s+(https?://\S+)", rest)
                    if url_match:
                        current_url = url_match.group(1)
                elif rest.startswith("Detail:"):
                    current_evidence = rest.replace("Detail:", "").strip()
                elif rest.startswith("###"):
                    break
                else:
                    current_event_text += " " + rest
                i += 1

            # Normalize text
            current_event_text = re.sub(r"\s+", " ", current_event_text)
            current_event_text = re.sub(r"\bhttps?:\S+", "", current_event_text).strip()
            # Remove source markers like "(P9, src: twitter) | URL: ..."
            current_event_text = re.sub(r"\s+\(\s*(?:P\d+,\s*)?src:\s*\w+.*?\)\s*", " ", current_event_text).strip()
            current_event_text = re.sub(r"\s+\|.*?$", "", current_event_text).strip()

            if current_event_text and len(current_event_text) >= 20:
                events.append({
                    "chain": current_chain or "unknown",
                    "text": current_event_text,
                    "url": current_url,
                    "topic": current_topic,
                    "source_type": "daily_prompt",
                })
            continue

        i += 1

    return events


def _parse_standalone_json(path: Path) -> list[dict]:
    """Parse standalone_summary JSON for raw tweets."""
    events = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for t in data.get("tweets", []):
            text = t.get("text", "").strip()
            if not text or len(text) < 40:
                continue
            low = text.lower()
            # skip baits
            if any(p in low for p in ["gpt image 2 prompt", "woke up based", "insanely viral"]):
                continue
            events.append({
                "chain": t.get("chain", "unknown").lower(),
                "text": text,
                "url": t.get("url", ""),
                "likes": t.get("likes", 0) or 0,
                "source_type": "standalone",
            })
    except Exception:
        pass
    return events


def _dedup_events(events: list[dict]) -> list[dict]:
    """Deduplicate by URL and then by text similarity."""
    seen_urls = set()
    kept = []
    for ev in events:
        url = ev.get("url", "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        txt = ev["text"].strip()
        if not txt or len(txt) < 20:
            continue
        dup = False
        for s in kept:
            a = set(txt.lower().split())
            b = set(s["text"].lower().split())
            union = a | b
            if not union:
                continue
            overlap = len(a & b) / len(union)
            if overlap > 0.70:
                dup = True
                break
        if not dup:
            kept.append(ev)
    return kept


def _synthesize_chain_events(chain: str, events: list[dict]) -> str:
    """Synthesize up to 10 chain events into ONE compact markdown bullet."""
    if not events:
        return f"- **{_display_chain(chain)}** (no text available)"

    events.sort(key=lambda e: (-bool(e.get("url")), -e.get("likes", 0), -len(e["text"])), reverse=True)

    sentences = []
    urls_used: set[str] = set()

    for ev in events[:10]:
        t = ev["text"].strip()
        t = re.sub(r"\n+", " ", t)
        t = t.replace("@", "").replace("#", "")
        t = re.sub(r"\|\s*URL:\s*https?://\S+", "", t)
        t = re.sub(r"https?://[^\s]+", "", t).strip()
        t = re.sub(r"\(\s*(?:P\d+,\s*)?src:.*?\)", "", t).strip()
        t = re.sub(r"\s+\|.*?$", "", t).strip()

        # More aggressive compacting
        t = re.sub(r"^(?:SolanaEvents|Aptos|Arbitrum|Base|Bitcoin|BSC|Ethereum|NEAR|Optimism|Polygon|SEI|Solana|Sui|Tempo)\s+(?:reposted|repost)\s+", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s{2,}", " ", t)
        if len(t) > 70:           # tighter per-event limit
            t = t[:70]
            t = t.rsplit(" ", 1)[0] + "..."
        t = t.strip(".,: ")
        if not t:
            continue

        t = _to_past(t)

        url = ev.get("url", "").strip()
        if url and url not in urls_used:
            anchor = _pick_anchor(t)
            if anchor:
                pat = re.compile(r"\b" + re.escape(anchor) + r"\b", re.IGNORECASE)
                t = pat.sub(f"[{anchor}]({url})", t, count=1)
            urls_used.add(url)

        sentences.append(t)

    if not sentences:
        return f"- **{_display_chain(chain)}** (no text available)"

    # Compact join — semicolons instead of periods between sentences
    compact = "; ".join(sentences)
    compact = re.sub(r"\.{3,}", "...", compact)
    compact = re.sub(r"\s{2,}", " ", compact)
    compact = re.sub(r";\s*;", ";", compact)
    compact = compact.strip("; ")

    return f"- **{_display_chain(chain)}** {compact}."


def build_digest() -> str:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # Load all sources
    all_events = []

    # Daily prompt .md files (non-Twitter + Twitter events processed by pipeline)
    for path in AGENT_INPUT_DIR.glob("daily_prompt_*.md"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                continue
            all_events.extend(_parse_daily_prompt(path))
        except Exception:
            pass

    # Standalone summary JSONs (Twitter raw)
    for path in DAILY_DIGEST_DIR.glob("standalone_summary_*.json"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                continue
            all_events.extend(_parse_standalone_json(path))
        except Exception:
            pass

    all_events = _dedup_events(all_events)
    logger.info(f"[weekly] {len(all_events)} unique events from cache")

    if not all_events:
        start = (now - timedelta(days=7)).strftime("%b %d")
        end = now.strftime("%b %d, %Y")
        return f"📈 Weekly Intelligence Brief — {start} – {end}\n\nNo cached data found. Run the pipeline first."

    # Bucket by (theme, chain)
    buckets = defaultdict(lambda: defaultdict(list))
    for ev in all_events:
        _, theme = _theme_of(ev["text"])
        buckets[theme][ev["chain"]].append(ev)

    # Order themes by total event count; Other Activity last
    theme_order = []
    other = None
    for theme, by_chain in buckets.items():
        total = sum(len(v) for v in by_chain.values())
        if theme == "Other Activity":
            other = (theme, by_chain, total)
        else:
            theme_order.append((theme, by_chain, total))
    theme_order.sort(key=lambda x: -x[2])

    start = (now - timedelta(days=7)).strftime("%b %d")
    end = now.strftime("%b %d, %Y")
    week_range = f"{start} – {end}"

    lines = [
        f"📈 Weekly Intelligence Brief — {week_range}",
        "",
        "🧠 Theme of the Week",
    ]
    top = [t for t, _, _ in theme_order[:3]]
    if top:
        tsent = ", ".join(top[:-1]) + f" and {top[-1]} dominated the narrative." if len(top) > 1 else f"{top[0]} dominated the narrative."
    else:
        tsent = "Limited thematic activity this week."
    lines.append(tsent)
    lines.append("")

    for theme, by_chain, _ in theme_order:
        emoji, _ = _theme_of(next(iter(by_chain.values()))[0]["text"])
        chain_list = [_display_chain(c) for c in sorted(by_chain)]
        if len(chain_list) == 1:
            lines.append(f"{emoji} **{theme} — {chain_list[0]}**")
        else:
            lines.append(f"{emoji} **{theme}**")
            lines.append(f"Chains: {', '.join(chain_list)}")
        lines.append("")
        for chain_name in sorted(by_chain):
            events = by_chain[chain_name]
            lines.append(_synthesize_chain_events(chain_name, events))
        lines.append("")

    if other:
        theme, by_chain, _ = other
        chain_list = [_display_chain(c) for c in sorted(by_chain)]
        lines.append("📊 **Other Activity**")
        lines.append(f"Chains: {', '.join(chain_list)}")
        lines.append("")
        for chain_name in sorted(by_chain):
            events = by_chain[chain_name]
            lines.append(_synthesize_chain_events(chain_name, events))
        lines.append("")
        if lines and lines[-1] == "":
            lines.pop()
        lines.append("")

    digest = "\n".join(lines)
    AGENT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%d_%H%M%S")
    path = AGENT_INPUT_DIR / f"weekly_digest_{ts}.md"
    path.write_text(digest, encoding="utf-8")
    logger.info(f"[weekly] Digest: {path}")
    return digest


async def synthesize_weekly_digest(client=None, daily_digests=None) -> str:
    """Generate weekly from cache — no live scraping."""
    return build_digest()


class WeeklyDigestFormatter:
    def format(self, signals=None, narrative_tracker=None, source_health=None, client=None) -> str:
        try:
            return build_digest()
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            now = datetime.now(timezone.utc)
            ws = (now - timedelta(days=7)).strftime("%b %d")
            we = now.strftime("%b %d, %Y")
            return f"📈 Weekly Intelligence Brief — {ws} – {we}\n\nWeekly synthesis unavailable."
