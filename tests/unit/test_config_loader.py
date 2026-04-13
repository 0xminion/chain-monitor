"""Tests for config loader."""

import pytest
import config.loader as loader_mod
from config.loader import (
    get_chains, get_baselines, get_narratives, get_sources,
    get_chain, get_baseline, get_active_chains, get_chains_by_tier,
    get_chains_by_category, get_env, reload_configs, load_yaml, CONFIG_DIR,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset config singletons before each test."""
    reload_configs()
    yield
    reload_configs()


class TestLoadYaml:
    """Test loading each YAML file."""

    def test_load_chains_yaml(self):
        data = load_yaml("chains.yaml")
        assert isinstance(data, dict)
        assert "ethereum" in data

    def test_load_baselines_yaml(self):
        data = load_yaml("baselines.yaml")
        assert isinstance(data, dict)
        assert "ethereum" in data

    def test_load_narratives_yaml(self):
        data = load_yaml("narratives.yaml")
        assert isinstance(data, dict)
        assert "narratives" in data

    def test_load_sources_yaml(self):
        data = load_yaml("sources.yaml")
        assert isinstance(data, dict)
        assert "defillama" in data

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_yaml("nonexistent.yaml")


class TestGetChains:
    """Test get_chains."""

    def test_returns_dict(self):
        chains = get_chains()
        assert isinstance(chains, dict)

    def test_has_known_chains(self):
        chains = get_chains()
        assert "ethereum" in chains
        assert "bitcoin" in chains
        assert "solana" in chains
        assert "arbitrum" in chains
        assert "hyperliquid" in chains

    def test_chain_has_expected_keys(self):
        chains = get_chains()
        eth = chains["ethereum"]
        assert "tier" in eth
        assert "category" in eth
        assert "coingecko_id" in eth

    def test_singleton_behavior(self):
        c1 = get_chains()
        c2 = get_chains()
        assert c1 is c2


class TestGetBaselines:
    """Test get_baselines."""

    def test_returns_dict(self):
        baselines = get_baselines()
        assert isinstance(baselines, dict)

    def test_has_known_chains(self):
        baselines = get_baselines()
        assert "ethereum" in baselines
        assert "bitcoin" in baselines

    def test_baseline_has_thresholds(self):
        eth = get_baselines()["ethereum"]
        assert "tvl_absolute_milestone" in eth
        assert "tvl_change_notable" in eth
        assert "tvl_change_spike" in eth


class TestGetNarratives:
    """Test get_narratives."""

    def test_returns_dict(self):
        narratives = get_narratives()
        assert isinstance(narratives, dict)

    def test_has_narratives_key(self):
        narratives = get_narratives()
        assert "narratives" in narratives
        assert "velocity_thresholds" in narratives

    def test_narratives_have_keywords(self):
        narratives = get_narratives()["narratives"]
        for key, val in narratives.items():
            assert "keywords" in val
            assert isinstance(val["keywords"], list)
            assert len(val["keywords"]) > 0


class TestGetSources:
    """Test get_sources."""

    def test_returns_dict(self):
        sources = get_sources()
        assert isinstance(sources, dict)

    def test_has_defillama(self):
        sources = get_sources()
        assert "defillama" in sources
        assert "chains_endpoint" in sources["defillama"]

    def test_has_coingecko(self):
        sources = get_sources()
        assert "coingecko" in sources


class TestGetChain:
    """Test get_chain."""

    def test_existing_chain(self):
        chain = get_chain("ethereum")
        assert chain is not None
        assert chain["tier"] == 1

    def test_nonexistent_chain(self):
        chain = get_chain("nonexistent_chain")
        assert chain is None


class TestGetBaseline:
    """Test get_baseline."""

    def test_existing_baseline(self):
        baseline = get_baseline("ethereum")
        assert baseline is not None
        assert "tvl_absolute_milestone" in baseline

    def test_nonexistent_baseline(self):
        baseline = get_baseline("nonexistent_chain")
        assert baseline is None


class TestGetActiveChains:
    """Test get_active_chains."""

    def test_returns_list(self):
        chains = get_active_chains()
        assert isinstance(chains, list)

    def test_contains_known_chains(self):
        chains = get_active_chains()
        assert "ethereum" in chains
        assert "bitcoin" in chains

    def test_all_keys(self):
        chains = get_active_chains()
        all_chains = get_chains()
        assert set(chains) == set(all_chains.keys())


class TestGetChainsByTier:
    """Test get_chains_by_tier."""

    def test_tier1_chains(self):
        chains = get_chains_by_tier(1)
        assert "ethereum" in chains
        assert "bitcoin" in chains
        assert "solana" in chains
        assert "arbitrum" in chains

    def test_tier2_chains(self):
        chains = get_chains_by_tier(2)
        assert "monad" in chains

    def test_tier3_chains(self):
        chains = get_chains_by_tier(3)
        assert "megaeth" in chains

    def test_invalid_tier_empty(self):
        chains = get_chains_by_tier(99)
        assert chains == []


class TestGetChainsByCategory:
    """Test get_chains_by_category."""

    def test_majors(self):
        chains = get_chains_by_category("majors")
        assert "ethereum" in chains
        assert "bitcoin" in chains
        assert "solana" in chains

    def test_cex_affiliated(self):
        chains = get_chains_by_category("cex_affiliated")
        assert "base" in chains
        assert "hyperliquid" in chains

    def test_invalid_category_empty(self):
        chains = get_chains_by_category("nonexistent")
        assert chains == []


class TestGetEnv:
    """Test get_env."""

    def test_existing_env(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "test_value")
        assert get_env("TEST_VAR") == "test_value"

    def test_missing_env_default(self):
        assert get_env("NONEXISTENT_VAR_12345") == ""

    def test_missing_env_custom_default(self):
        assert get_env("NONEXISTENT_VAR_12345", "fallback") == "fallback"


class TestReloadConfigs:
    """Test config reloading."""

    def test_reload_resets_singletons(self):
        c1 = get_chains()
        reload_configs()
        c2 = get_chains()
        assert c1 is not c2
        assert c1 == c2
