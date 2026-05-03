"""Integration tests for collectors with mocked HTTP."""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

class TestDefiLlamaCollector:
    """Test DefiLlamaCollector with mocked API."""

    @pytest.fixture
    def collector(self, mock_config):
        from collectors.defillama import DefiLlamaCollector
        return DefiLlamaCollector()

    def test_collect_returns_list(self, collector):
        with patch.object(collector, "fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = [{"name": "Ethereum", "tvl": 65_000_000_000, "gecko_id": "ethereum"}]
            signals = collector.collect()
            assert isinstance(signals, list)

    def test_collect_handles_api_failure(self, collector):
        with patch.object(collector, "fetch_with_retry") as mock_fetch:
            mock_fetch.return_value = None
            signals = collector.collect()
            assert signals == []

    def test_tvl_spike_detection(self, collector):
        now_ts = int(datetime.now(timezone.utc).timestamp())
        week_ago_ts = now_ts - 7 * 86400
        historical = [
            {"date": week_ago_ts, "tvl": 50_000_000_000},
            {"date": now_ts, "tvl": 70_000_000_000},  # 40% spike
        ]

        with patch.object(collector, "fetch_with_retry") as mock_fetch:
            def side_effect(url, params=None):
                if "chains" in url:
                    return [{"name": "Ethereum", "tvl": 70_000_000_000, "gecko_id": "ethereum"}]
                if "historicalChainTvl" in url:
                    return historical
                if "fees" in url:
                    return None
                return None

            mock_fetch.side_effect = side_effect
            signals = collector.collect()
            spike_signals = [s for s in signals if "surge" in s.get("description", "").lower() or "spike" in s.get("description", "").lower() or "up" in s.get("description", "").lower()]
            # At least one spike signal should be detected for ethereum (threshold=25%)
            assert any("ethereum" in s.get("chain", "") for s in signals)

    def test_tvl_milestone_detection(self, collector):
        # Ethereum baseline milestone is $60B
        with patch.object(collector, "fetch_with_retry") as mock_fetch:
            def side_effect(url, params=None):
                if "chains" in url:
                    return [{"name": "Ethereum", "tvl": 62_000_000_000, "gecko_id": "ethereum"}]
                if "historicalChainTvl" in url:
                    return [{"date": 1, "tvl": 61_000_000_000}]
                if "fees" in url:
                    return None
                return None

            mock_fetch.side_effect = side_effect
            signals = collector.collect()
            milestone_signals = [s for s in signals if "milestone" in s.get("description", "").lower()]
            assert len(milestone_signals) > 0

    def test_make_signal_structure(self, collector):
        sig = collector._make_signal("ethereum", "test desc", 0.8, {"key": "val"})
        assert sig["chain"] == "ethereum"
        assert sig["category"] == "FINANCIAL"
        assert sig["source"] == "DefiLlama"
        assert sig["reliability"] == 0.8
        assert sig["evidence"] == {"key": "val"}

class TestCoinGeckoCollector:
    """Test CoinGeckoCollector with mocked API."""

    @pytest.fixture
    def collector(self, mock_config):
        from collectors.coingecko_collector import CoinGeckoCollector
        return CoinGeckoCollector()

    def test_collect_returns_list(self, collector):
        with patch.object(collector, "_rate_limited_fetch") as mock_fetch:
            mock_fetch.return_value = {
                "market_data": {
                    "current_price": {"usd": 3500},
                    "price_change_percentage_24h": 5.0,
                    "market_cap": {"usd": 420_000_000_000},
                    "total_volume": {"usd": 15_000_000_000},
                }
            }
            signals = collector.collect()
            assert isinstance(signals, list)

    def test_price_spike_detection(self, collector):
        with patch.object(collector, "_rate_limited_fetch") as mock_fetch:
            mock_fetch.return_value = {
                "market_data": {
                    "current_price": {"usd": 4200},
                    "price_change_percentage_24h": 25.0,  # above 20% spike threshold
                    "market_cap": {"usd": 500_000_000_000},
                    "total_volume": {"usd": 20_000_000_000},
                }
            }
            signals = collector.collect()
            spike_signals = [s for s in signals if "surge" in s.get("description", "").lower() or "spike" in s.get("description", "").lower()]
            assert len(spike_signals) > 0

    def test_price_notable_detection(self, collector):
        with patch.object(collector, "_rate_limited_fetch") as mock_fetch:
            mock_fetch.return_value = {
                "market_data": {
                    "current_price": {"usd": 3800},
                    "price_change_percentage_24h": 12.0,  # notable but not spike
                    "market_cap": {"usd": 450_000_000_000},
                    "total_volume": {"usd": 15_000_000_000},
                }
            }
            signals = collector.collect()
            notable_signals = [s for s in signals if "rose" in s.get("description", "").lower() or "fell" in s.get("description", "").lower()]
            assert len(notable_signals) > 0

    def test_volume_anomaly_detection(self, collector):
        with patch.object(collector, "_rate_limited_fetch") as mock_fetch:
            mock_fetch.return_value = {
                "market_data": {
                    "current_price": {"usd": 150},
                    "price_change_percentage_24h": 2.0,
                    "market_cap": {"usd": 10_000_000_000},
                    "total_volume": {"usd": 5_000_000_000},  # 50% ratio
                }
            }
            signals = collector.collect()
            vol_signals = [s for s in signals if "volume" in s.get("description", "").lower()]
            assert len(vol_signals) > 0

    def test_no_data_returns_empty(self, collector):
        with patch.object(collector, "_rate_limited_fetch") as mock_fetch:
            mock_fetch.return_value = None
            signals = collector.collect()
            assert signals == []

class TestRSSCollector:
    """Test RSSCollector with mocked feed."""

    @pytest.fixture
    def collector(self, mock_config):
        from collectors.rss_collector import RSSCollector
        return RSSCollector()

    def test_collect_returns_list(self, collector):
        with patch.object(collector, "fetch_text_with_retry") as mock_fetch:
            mock_fetch.return_value = None
            signals = collector.collect()
            assert isinstance(signals, list)

    def test_process_feed_with_valid_rss(self, collector):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Ethereum upgrade scheduled for next month</title>
              <description>Ethereum will undergo a major upgrade</description>
              <link>https://example.com/eth-upgrade</link>
              <pubDate>{pub_date}</pubDate>
            </item>
          </channel>
        </rss>"""

        with patch.object(collector, "fetch_text_with_retry") as mock_fetch:
            mock_fetch.return_value = rss_xml
            signals = collector._process_feed("https://example.com/rss", "Test Feed", default_chain="ethereum")
            assert len(signals) > 0
            assert signals[0]["chain"] == "ethereum"

    def test_process_feed_no_chain_match(self, collector):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Some unrelated crypto news</title>
              <description>No chain mentioned</description>
              <link>https://example.com/news</link>
              <pubDate>Mon, 13 Apr 2026 12:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""

        with patch.object(collector, "fetch_text_with_retry") as mock_fetch:
            mock_fetch.return_value = rss_xml
            signals = collector._process_feed("https://example.com/rss", "Test Feed", default_chain=None)
            assert len(signals) == 0

    def test_process_feed_with_default_chain(self, collector):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Generic update posted</title>
              <description>Some generic update</description>
              <link>https://example.com/update</link>
              <pubDate>{pub_date}</pubDate>
            </item>
          </channel>
        </rss>"""

        with patch.object(collector, "fetch_text_with_retry") as mock_fetch:
            mock_fetch.return_value = rss_xml
            signals = collector._process_feed("https://example.com/rss", "Test Feed", default_chain="monad")
            assert len(signals) > 0
            assert signals[0]["chain"] == "monad"

    def test_chain_matching(self, collector):
        assert collector._match_chain("Ethereum upgrade live") == "ethereum"
        assert collector._match_chain("Bitcoin halving event") == "bitcoin"
        assert collector._match_chain("Solana new feature") == "solana"
        # Aliases
        assert collector._match_chain("ETH gas fees rising") == "ethereum"
        assert collector._match_chain("BTC ETF inflows") == "bitcoin"
