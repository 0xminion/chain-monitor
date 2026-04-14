"""Events calendar collector — conferences, hackathons via Camoufox anti-detect browser.

Sources:
- ethereum.org/community/events/conferences/ (38+ conferences)
- ethglobal.com/events (84+ hackathons, meetups)

Uses Camoufox (anti-detect Firefox) to bypass Cloudflare protection.
Falls back gracefully if Camoufox unavailable.
"""

import logging
from datetime import datetime, timezone

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

ETH_ORG_URL = "https://ethereum.org/community/events/conferences/"
ETHGLOBAL_URL = "https://ethglobal.com/events"


class EventsCollector(BaseCollector):
    """Collects upcoming crypto events from ethereum.org and ETHGlobal."""

    def __init__(self):
        super().__init__(name="events")

    def collect(self) -> list[dict]:
        """Collect events from all sources using Camoufox."""
        signals = []

        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            logger.warning("Camoufox not available, skipping events collector")
            return signals

        try:
            with Camoufox(headless=True) as browser:
                # Source 1: ethereum.org conferences
                signals.extend(self._scrape_eth_org_conferences(browser))

                # Source 2: ETHGlobal events
                signals.extend(self._scrape_ethglobal(browser))

            logger.info(f"Events: {len(signals)} total events collected")
            self.health.mark_success()
        except Exception as e:
            logger.error(f"Events collector failed: {e}")
            self.health.mark_failure(str(e))

        return signals

    def _scrape_eth_org_conferences(self, browser) -> list[dict]:
        """Scrape ethereum.org/community/events/conferences/ for upcoming conferences."""
        signals = []
        try:
            page = browser.new_page()
            page.goto(ETH_ORG_URL, timeout=30000)
            page.wait_for_timeout(5000)

            conferences = page.evaluate("""() => {
                const items = [];
                const main = document.querySelector('main') || document.body;
                const text = main.innerText;
                const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

                let current = null;
                let inUpcoming = false;
                const monthRe = /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d/;

                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];

                    // Start collecting after "Upcoming Ethereum conferences"
                    if (line.includes('Upcoming Ethereum conferences')) {
                        inUpcoming = true;
                        continue;
                    }

                    if (!inUpcoming) continue;

                    if (monthRe.test(line)) {
                        if (current && current.name && current.name !== 'Upcoming Ethereum conferences') {
                            items.push(current);
                        }
                        current = { date: line, name: '', location: '', tags: [] };
                    } else if (current) {
                        if (!current.name && line !== 'CONFERENCE' && line !== 'HACKATHON' && !line.startsWith('(') && !line.startsWith('http')) {
                            current.name = line;
                        } else if (current.name && !current.location && line !== 'CONFERENCE' && line !== 'HACKATHON' && !line.startsWith('(') && !line.startsWith('http')) {
                            current.location = line;
                        } else if (line === 'CONFERENCE' || line === 'HACKATHON') {
                            current.tags.push(line);
                        }
                    }
                }
                if (current && current.name && current.name !== 'Upcoming Ethereum conferences') {
                    items.push(current);
                }

                return items;
            }""")

            page.close()

            for conf in conferences:
                name = conf.get("name", "")
                if not name or len(name) < 3:
                    continue

                date = conf.get("date", "")
                location = conf.get("location", "")
                tags = conf.get("tags", [])

                # Classify
                is_hackathon = "HACKATHON" in tags
                importance = "high" if is_hackathon else "medium"

                signal = {
                    "type": "crypto_event",
                    "category": "VISIBILITY",
                    "chain": "ethereum",
                    "title": name,
                    "source_name": "Ethereum.org",
                    "description": f"{name} — {date}, {location}" + (" (Hackathon)" if is_hackathon else " (Conference)"),
                    "evidence": {
                        "title": name,
                        "date": date,
                        "location": location,
                        "event_type": "hackathon" if is_hackathon else "conference",
                        "tags": tags,
                        "url": ETH_ORG_URL,
                        "source": "ethereum_org",
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "importance": importance,
                }
                signals.append(signal)

            logger.info(f"Ethereum.org conferences: {len(signals)} events")
            self.health.mark_success()

        except Exception as e:
            logger.error(f"Ethereum.org scraper failed: {e}")
            self.health.mark_failure(str(e))

        return signals

    def _scrape_ethglobal(self, browser) -> list[dict]:
        """Scrape ethglobal.com/events for hackathons and meetups."""
        signals = []
        try:
            page = browser.new_page()
            page.goto(ETHGLOBAL_URL, timeout=30000)
            page.wait_for_timeout(8000)

            events = page.evaluate("""() => {
                const items = [];
                const links = document.querySelectorAll('a[href*="/events/"]');
                const seen = new Set();

                links.forEach(a => {
                    const href = a.href || '';
                    const text = a.innerText?.trim();
                    if (!text || text.length < 5 || seen.has(href)) return;
                    if (href === 'https://ethglobal.com/events') return;
                    seen.add(href);

                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                    const name = lines[0] || '';
                    const date = lines.find(l => l.match(/\\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/i)) || '';

                    items.push({
                        name: name,
                        date: date,
                        href: href,
                        fullText: text.substring(0, 300),
                    });
                });

                return items;
            }""")

            page.close()

            for event in events:
                name = event.get("name", "")
                if not name or len(name) < 3:
                    continue

                nl = name.lower()

                # Skip month-only entries (e.g., "APRIL—MAY", "JUL", "SEP")
                if re.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', nl) and len(nl) < 20:
                    continue

                # Skip past events (anything before 2026)
                date_str = event.get("date", "")
                full_text = f"{name} {date_str}"
                if any(y in full_text for y in ["2022", "2023", "2024", "2025"]):
                    continue

                # Classify event type
                if "happy hour" in nl or "meetup" in nl or "cowork" in nl:
                    event_type = "meetup"
                    importance = "low"
                elif "hackathon" in nl or "buildathon" in nl:
                    event_type = "hackathon"
                    importance = "high"
                elif "pragma" in nl or "summit" in nl or "conference" in nl:
                    event_type = "conference"
                    importance = "high"
                elif nl.startswith("ethglobal ") and not any(m in nl for m in ["happy hour", "meetup"]):
                    # ETHGlobal + city = hackathon (e.g., "ETHGlobal Cannes 2026")
                    event_type = "hackathon"
                    importance = "high"
                elif "online" in nl or "trifecta" in nl or "unite" in nl:
                    event_type = "hackathon"
                    importance = "medium"
                else:
                    event_type = "event"
                    importance = "medium"

                signal = {
                    "type": "crypto_event",
                    "category": "VISIBILITY",
                    "chain": "ethereum",
                    "title": f"ETHGlobal: {name}",
                    "source_name": "ETHGlobal",
                    "description": event.get("fullText", name)[:300],
                    "evidence": {
                        "title": name,
                        "url": event.get("href", ""),
                        "date": event.get("date", ""),
                        "event_type": event_type,
                        "source": "ethglobal",
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "importance": importance,
                }
                signals.append(signal)

            logger.info(f"ETHGlobal: {len(signals)} events")
            self.health.mark_success()

        except Exception as e:
            logger.error(f"ETHGlobal scraper failed: {e}")
            self.health.mark_failure(str(e))

        return signals
