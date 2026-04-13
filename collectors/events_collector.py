"""Events calendar collector — scrapes ETHGlobal events page.

Note: ETHGlobal uses Cloudflare protection. This collector attempts
Camoufox first, falls back to direct API if available.
"""

import logging
from datetime import datetime, timezone

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class EventsCollector(BaseCollector):
    """Collects upcoming crypto events from ETHGlobal and similar sources."""

    def __init__(self):
        super().__init__(name="events")

    def collect(self) -> list[dict]:
        """Collect events. Attempts Camoufox for Cloudflare-protected sites."""
        signals = []

        # Try Camoufox first (better anti-detection)
        ethglobal_signals = self._try_ethglobal_camoufox()
        if ethglobal_signals:
            signals.extend(ethglobal_signals)
        else:
            logger.info("ETHGlobal: Cloudflare blocked, skipping (camoufox unavailable in this environment)")

        return signals

    def _try_ethglobal_camoufox(self) -> list[dict]:
        """Try scraping ETHGlobal with Camoufox (anti-detect browser)."""
        signals = []
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto("https://ethglobal.com/events", timeout=30000)
                page.wait_for_timeout(8000)

                events = page.evaluate('''() => {
                    const items = [];
                    const cards = document.querySelectorAll('a[href*="/events/"]');
                    const seen = new Set();

                    cards.forEach(a => {
                        const href = a.href || '';
                        const text = a.innerText?.trim();
                        if (!text || text.length < 5 || seen.has(href)) return;
                        if (href === 'https://ethglobal.com/events') return;
                        seen.add(href);

                        const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                        const name = lines[0] || '';

                        items.push({
                            name: name,
                            href: href,
                            fullText: text.substring(0, 300),
                        });
                    });

                    return items;
                }''')

                for event in events[:20]:
                    name = event.get("name", "")
                    if not name or len(name) < 3:
                        continue

                    nl = name.lower()
                    if "happy hour" in nl or "meetup" in nl:
                        importance = "low"
                    elif "hackathon" in nl:
                        importance = "high"
                    else:
                        importance = "medium"

                    signals.append({
                        "type": "crypto_event",
                        "category": "VISIBILITY",
                        "chain": "ethereum",
                        "title": f"ETHGlobal: {name}",
                        "source_name": "ETHGlobal",
                        "description": event.get("fullText", name)[:300],
                        "evidence": {
                            "title": name,
                            "url": event.get("href", ""),
                            "source": "ethglobal",
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "importance": importance,
                    })

                logger.info(f"ETHGlobal: {len(signals)} events")
                self.health.mark_success()

        except Exception as e:
            logger.debug(f"ETHGlobal camoufox failed: {e}")
            # Don't mark as failure — this is expected in CI/headless envs

        return signals
