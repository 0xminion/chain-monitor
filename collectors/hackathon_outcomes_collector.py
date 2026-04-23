"""Hackathon outcomes collector — scrapes winners, results, and recordings.

Sources:
- Solana: solana.com/news (hackathon winners like Hyperdrive, Radar)
- ETHGlobal: event pages (prize details, themes)
- Devpost: web3 hackathon listings
- Chain blogs via RSS (hackathon result announcements)
"""

import logging

from datetime import datetime, timezone

from collectors.base import BaseCollector


logger = logging.getLogger(__name__)

# Solana hackathon results URL pattern
SOLANA_NEWS_URL = "https://solana.com/news"

# Devpost web3 hackathons
DEVPOST_WEB3_URL = "https://devpost.com/hackathons?themes%5B%5D=web3&themes%5B%5D=blockchain"

# Known hackathon result pages per chain
HACKATHON_RESULT_PAGES = {
    "solana": [
        {
            "url": "https://solana.com/news/solana-radar-winners",
            "name": "Solana Radar Hackathon",
            "date": "2024-11-12",
        },
        {
            "url": "https://solana.com/news/solana-hyperdrive-hackathon-winners",
            "name": "Solana Hyperdrive Hackathon",
            "date": "2024-01-01",
        },
    ],
}


class HackathonOutcomesCollector(BaseCollector):
    """Collects hackathon results, winners, and conference recordings."""

    def __init__(self):
        super().__init__(name="hackathon_outcomes")

    def collect(self) -> list[dict]:
        """Collect hackathon outcomes from all sources."""
        signals = []

        # Source 1: ETHGlobal past events (via Camoufox)
        signals.extend(self._collect_ethglobal_past_events())

        # Source 2: Solana hackathon results
        signals.extend(self._collect_solana_hackathon_results())

        # Source 3: Devpost web3 hackathons
        signals.extend(self._collect_devpost())

        return signals

    def _collect_ethglobal_past_events(self) -> list[dict]:
        """Scrape ETHGlobal event pages for past hackathon prize/theme info."""
        signals = []
        try:
            from camoufox.sync_api import Camoufox

            # Known past ETHGlobal events with results
            past_events = [
                "newyork2025", "istanbul2025", "london2025",
                "paris2025", "tokyo2025", "lisbon2025",
                "cannes2026", "waterloo2025",
            ]

            with Camoufox(headless=True) as browser:
                for event_slug in past_events:
                    try:
                        url = f"https://ethglobal.com/events/{event_slug}"
                        page = browser.new_page()
                        page.goto(url, timeout=20000)
                        page.wait_for_timeout(4000)

                        data = page.evaluate("""() => {
                            const main = document.querySelector('main') || document.body;
                            const text = main.innerText || '';

                            // Extract event name from title
                            const title = document.title.replace(' | ETHGlobal', '').trim();

                            // Extract date
                            const dateMatch = text.match(/((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{1,2}(?:\\s*[–-]\\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\\s*\\d{1,2})?,?\\s*\\d{4})/);
                            const date = dateMatch ? dateMatch[1] : '';

                            // Extract location
                            const locMatch = text.match(/(?:Attendees|Workshops)\\n([^\\n]+(?:,\\s*[^\\n]+)?)/);
                            const location = locMatch ? '' : ''; // Skip complex parsing

                            // Extract prize total
                            const prizeMatch = text.match(/\\$(\\d[\\d,]+)\\nAvailable in prizes/);
                            const totalPrize = prizeMatch ? prizeMatch[1] : '';

                            // Extract partner prizes
                            const partners = [];
                            const prizeSection = text.match(/Available in prizes\\n([\\s\\S]*?)(?:See prize|Make the most)/);
                            if (prizeSection) {
                                const lines = prizeSection[1].split('\\n').filter(l => l.trim());
                                for (let i = 0; i < lines.length - 1; i += 2) {
                                    const name = lines[i]?.trim();
                                    const amount = lines[i+1]?.trim();
                                    if (name && amount && amount.startsWith('$')) {
                                        partners.push({name, amount});
                                    }
                                }
                            }

                            // Extract themes
                            const themesMatch = text.match(/Themes and Topics\\n([\\s\\S]*?)\\$\\d/);
                            const themes = themesMatch ? themesMatch[1].split('\\n').filter(l => l.trim()).map(l => l.trim()) : [];

                            return {title, date, totalPrize, partners: partners.slice(0, 10), themes};
                        }""")

                        page.close()

                        if data.get("title") and data.get("totalPrize"):
                            # Build description with winners info
                            desc_parts = [f"{data['title']} — ${data['totalPrize']} in prizes"]
                            if data.get("date"):
                                desc_parts.append(f"({data['date']})")
                            if data.get("themes"):
                                desc_parts.append(f"Themes: {', '.join(data['themes'][:5])}")
                            if data.get("partners"):
                                top_partners = ", ".join(f"{p['name']} ({p['amount']})" for p in data["partners"][:5])
                                desc_parts.append(f"Sponsors: {top_partners}")

                            signal = {
                                "type": "hackathon_outcome",
                                "category": "VISIBILITY",
                                "chain": "ethereum",
                                "title": data["title"],
                                "source_name": "ETHGlobal",
                                "description": " — ".join(desc_parts),
                                "evidence": {
                                    "title": data["title"],
                                    "url": url,
                                    "date": data.get("date", ""),
                                    "total_prize": data.get("totalPrize", ""),
                                    "themes": data.get("themes", []),
                                    "top_sponsors": [p["name"] for p in data.get("partners", [])[:5]],
                                    "event_type": "hackathon",
                                    "source": "ethglobal",
                                },
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "importance": "high",
                            }
                            signals.append(signal)

                    except Exception as e:
                        logger.debug(f"ETHGlobal {event_slug}: {e}")
                        continue

            logger.info(f"ETHGlobal past events: {len(signals)} outcomes")
            self.health.mark_success()

        except Exception as e:
            logger.error(f"ETHGlobal outcomes failed: {e}")
            self.health.mark_failure(str(e))

        return signals

    def _collect_solana_hackathon_results(self) -> list[dict]:
        """Scrape Solana hackathon results from solana.com/news."""
        signals = []
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(headless=True) as browser:
                # Scrape known results pages
                for event in HACKATHON_RESULT_PAGES.get("solana", []):
                    try:
                        page = browser.new_page()
                        page.goto(event["url"], timeout=20000)
                        page.wait_for_timeout(4000)

                        data = page.evaluate("""() => {
                            const main = document.querySelector('main') || document.body;
                            const text = main.innerText || '';

                            // Extract winners - look for track names and winners
                            const winners = [];
                            const tracks = text.split(/(?:Consumer|Crypto|Gaming|DePIN|DAOs|DeFi|Payments|Infrastructure)\\s*(?:Apps?)?\\s*Track/i);

                            // Get first 2000 chars for summary
                            const summary = text.substring(0, 2000);

                            // Extract grand champion
                            const grandMatch = text.match(/Grand Champion[\\s\\S]*?\\n([^\\n]+)/);

                            return {
                                title: document.title.split('|')[0].trim(),
                                summary: summary,
                                grandChampion: grandMatch ? grandMatch[1].trim() : '',
                                url: window.location.href,
                            };
                        }""")

                        page.close()

                        if data.get("summary"):
                            # Extract key winners from summary
                            summary = data["summary"]
                            title = data.get("title", event["name"])

                            signal = {
                                "type": "hackathon_outcome",
                                "category": "VISIBILITY",
                                "chain": "solana",
                                "title": title,
                                "source_name": "Solana",
                                "description": summary[:300],
                                "evidence": {
                                    "title": title,
                                    "url": event["url"],
                                    "date": event.get("date", ""),
                                    "grand_champion": data.get("grandChampion", ""),
                                    "event_type": "hackathon",
                                    "source": "solana_news",
                                },
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "importance": "high",
                            }
                            signals.append(signal)

                    except Exception as e:
                        logger.debug(f"Solana hackathon {event['name']}: {e}")
                        continue

            logger.info(f"Solana hackathon results: {len(signals)} outcomes")
            self.health.mark_success()

        except Exception as e:
            logger.error(f"Solana hackathon results failed: {e}")
            self.health.mark_failure(str(e))

        return signals

    def _collect_devpost(self) -> list[dict]:
        """Scrape Devpost for web3 hackathon listings."""
        signals = []
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto(DEVPOST_WEB3_URL, timeout=20000)
                page.wait_for_timeout(5000)

                hackathons = page.evaluate("""() => {
                    const items = [];
                    const cards = document.querySelectorAll('[class*="hackathon"], [class*="challenge"], article, .gallery-item, .challenge-card');

                    cards.forEach(el => {
                        const text = el.innerText?.trim();
                        if (!text || text.length < 20) return;

                        const link = el.querySelector('a');
                        const href = link ? link.href : '';

                        const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

                        items.push({
                            title: lines[0] || '',
                            status: lines.find(l => l.match(/active|upcoming|ended|open/i)) || '',
                            prize: lines.find(l => l.match(/\\$\\d/)) || '',
                            href: href,
                            fullText: text.substring(0, 300),
                        });
                    });

                    return items.slice(0, 15);
                }""")

                page.close()

                for hack in hackathons:
                    title = hack.get("title", "")
                    if not title or len(title) < 5:
                        continue

                    # Classify
                    status = hack.get("status", "").lower()
                    if "ended" in status or "closed" in status:
                        importance = "medium"
                    else:
                        importance = "high"

                    signal = {
                        "type": "hackathon_outcome",
                        "category": "VISIBILITY",
                        "chain": "general",
                        "title": f"Devpost: {title}",
                        "source_name": "Devpost",
                        "description": hack.get("fullText", title)[:300],
                        "evidence": {
                            "title": title,
                            "url": hack.get("href", ""),
                            "status": status,
                            "prize": hack.get("prize", ""),
                            "event_type": "hackathon",
                            "source": "devpost",
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "importance": importance,
                    }
                    signals.append(signal)

                logger.info(f"Devpost: {len(signals)} hackathons")
                self.health.mark_success()

        except Exception as e:
            logger.error(f"Devpost scraper failed: {e}")
            self.health.mark_failure(str(e))

        return signals
