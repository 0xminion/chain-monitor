"""System tests — verify config loading, imports, and class instantiation."""

import pytest

class TestConfigFilesLoad:
    """Verify all config files load."""

    def test_chains_yaml_loads(self):
        from config.loader import load_yaml
        data = load_yaml("chains.yaml")
        assert data is not None
        assert len(data) > 0

    def test_baselines_yaml_loads(self):
        from config.loader import load_yaml
        data = load_yaml("baselines.yaml")
        assert data is not None
        assert len(data) > 0

    def test_narratives_yaml_loads(self):
        from config.loader import load_yaml
        data = load_yaml("narratives.yaml")
        assert data is not None
        assert "narratives" in data

    def test_sources_yaml_loads(self):
        from config.loader import load_yaml
        data = load_yaml("sources.yaml")
        assert data is not None

    def test_chains_and_baselines_aligned(self):
        """Every chain in chains.yaml should have a baseline."""
        from config.loader import get_chains, get_baselines
        chains = get_chains()
        baselines = get_baselines()
        for chain_name in chains:
            assert chain_name in baselines, f"Missing baseline for chain: {chain_name}"

class TestImportsWork:
    """Verify all imports work."""

    def test_import_processors(self):
        from processors.signal import Signal, ActivityEntry
        from processors.scoring import SignalScorer
        from processors.reinforcement import SignalReinforcer
        from processors.categorizer import EventCategorizer
        from processors.narrative_tracker import NarrativeTracker
        assert Signal is not None
        assert SignalScorer is not None

    def test_import_collectors(self):
        from collectors.base import BaseCollector, SourceHealth
        from collectors.defillama import DefiLlamaCollector
        from collectors.coingecko_collector import CoinGeckoCollector
        
        from collectors.rss_collector import RSSCollector
        assert BaseCollector is not None

    def test_import_output(self):
        from processors.summary_engine import synthesize_digest
        assert synthesize_digest is not None

    def test_import_config(self):
        from config.loader import (
            get_chains, get_baselines, get_narratives, get_sources,
            get_chain, get_baseline, get_active_chains, get_chains_by_tier,
            get_env, reload_configs,
        )
        assert get_chains is not None

    def test_import_collectors_package(self):
        import collectors
        assert hasattr(collectors, "DefiLlamaCollector")
        assert hasattr(collectors, "CoinGeckoCollector")

        assert hasattr(collectors, "RSSCollector")

class TestCollectorInstantiation:
    """Verify collector classes can be instantiated."""

    def test_defillama_collector(self):
        from collectors.defillama import DefiLlamaCollector
        c = DefiLlamaCollector()
        assert c.name == "DefiLlama"
        assert c.health is not None

    def test_coingecko_collector(self):
        from collectors.coingecko_collector import CoinGeckoCollector
        c = CoinGeckoCollector()
        assert c.name == "CoinGecko"
        assert c.health is not None

    def test_rss_collector(self):
        from collectors.rss_collector import RSSCollector
        c = RSSCollector()
        assert c.name == "RSS"
        assert c.health is not None

class TestProcessorInstantiation:
    """Verify processor classes can be instantiated."""

    def test_scorer(self):
        from processors.scoring import SignalScorer
        s = SignalScorer()
        assert s.baselines is not None
        assert s.chains is not None

    def test_categorizer(self):
        from processors.categorizer import EventCategorizer
        c = EventCategorizer()
        assert c is not None

    def test_agent_native_synthesis(self):
        from processors.summary_engine import synthesize_digest
        assert synthesize_digest is not None

class TestSourceHealth:
    """Verify SourceHealth works."""

    def test_source_health_healthy(self):
        from collectors.base import SourceHealth
        h = SourceHealth(source_name="test")
        assert h.status == "healthy"
        h.mark_success()
        assert h.status == "healthy"

    def test_source_health_degraded(self):
        from collectors.base import SourceHealth
        h = SourceHealth(source_name="test")
        h.mark_failure("err1")
        h.mark_failure("err2")
        assert h.status == "degraded"

    def test_source_health_down(self):
        from collectors.base import SourceHealth
        h = SourceHealth(source_name="test")
        for _ in range(5):
            h.mark_failure("err")
        assert h.status == "down"

    def test_source_health_to_dict(self):
        from collectors.base import SourceHealth
        h = SourceHealth(source_name="test")
        d = h.to_dict()
        assert d["source_name"] == "test"
        assert "status" in d
