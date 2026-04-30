"""Shared fixtures for Chain Monitor test suite."""

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_signal_data():
    """Standard raw event dict for testing."""
    return {
        "chain": "ethereum",
        "category": "TECH_EVENT",
        "description": "Ethereum mainnet upgrade Pectra scheduled",
        "source": "GitHub",
        "reliability": 0.9,
        "evidence": {"metric": "new_release", "tag": "v1.14.0"},
    }


@pytest.fixture
def financial_event():
    """Financial raw event."""
    return {
        "chain": "solana",
        "category": "FINANCIAL",
        "description": "TVL crossed $10B milestone",
        "source": "DefiLlama",
        "reliability": 0.9,
        "evidence": {"metric": "tvl_milestone", "current_tvl": 10_500_000_000},
        "subcategory": "tvl_milestone",
    }


@pytest.fixture
def hack_event():
    """Risk alert raw event."""
    return {
        "chain": "ethereum",
        "category": "RISK_ALERT",
        "description": "Hack drained $15M from bridge",
        "source": "DefiLlama",
        "reliability": 0.95,
        "evidence": {"metric": "hack", "amount": 15_000_000},
        "subcategory": "hack",
        "value": 15_000_000,
    }


@pytest.fixture
def regulatory_event():
    """Regulatory raw event."""
    return {
        "chain": "hyperliquid",
        "category": "REGULATORY",
        "description": "SEC enforcement action filed",
        "source": "RSS",
        "reliability": 0.8,
        "evidence": {"metric": "regulatory"},
        "subcategory": "enforcement",
    }


@pytest.fixture
def partnership_event():
    """Partnership raw event."""
    return {
        "chain": "monad",
        "category": "PARTNERSHIP",
        "description": "Uniswap announces partnership with Monad",
        "source": "RSS",
        "reliability": 0.7,
        "evidence": {"metric": "partnership"},
        "subcategory": "collaboration",
    }


@pytest.fixture
def visibility_event():
    """Visibility raw event."""
    return {
        "chain": "ethereum",
        "category": "VISIBILITY",
        "description": "Vitalik keynote at ETH Denver conference",
        "source": "RSS",
        "reliability": 0.6,
        "evidence": {"metric": "visibility"},
        "subcategory": "keynote",
    }


@pytest.fixture
def make_signal():
    """Factory for creating Signal instances."""
    from processors.signal import Signal

    def _make(
        chain="ethereum",
        category="TECH_EVENT",
        description="Test event",
        impact=2,
        urgency=1,
        trader_context="",
        source="test",
        reliability=0.8,
    ):
        sig = Signal(
            id=Signal.generate_id(chain, category, description),
            chain=chain,
            category=category,
            description=description,
            impact=impact,
            urgency=urgency,
            priority_score=impact * urgency,
            trader_context=trader_context,
        )
        sig.add_activity(source, reliability, description)
        return sig

    return _make


@pytest.fixture
def mock_config(monkeypatch):
    """Mock config loader to avoid YAML file dependency in unit tests."""
    chains = {
        "ethereum": {"tier": 1, "category": "majors", "coingecko_id": "ethereum", "defillama_slug": "ethereum"},
        "bitcoin": {"tier": 1, "category": "majors", "coingecko_id": "bitcoin", "defillama_slug": None},
        "solana": {"tier": 1, "category": "majors", "coingecko_id": "solana", "defillama_slug": "solana"},
        "hyperliquid": {"tier": 1, "category": "cex_affiliated", "coingecko_id": "hyperliquid", "defillama_slug": "hyperliquid"},
        "monad": {"tier": 2, "category": "high_tps", "coingecko_id": "monad", "defillama_slug": "monad"},
    }
    baselines = {
        "ethereum": {
            "tvl_absolute_milestone": 60_000_000_000,
            "tvl_change_notable": 10,
            "tvl_change_spike": 25,
            "upgrade_impact_floor": 4,
        },
        "bitcoin": {
            "price_change_notable": 10,
            "price_change_spike": 20,
            "upgrade_impact_floor": 4,
        },
        "hyperliquid": {
            "tvl_absolute_milestone": 1_000_000_000,
            "tvl_change_notable": 20,
            "tvl_change_spike": 40,
            "regulatory_any_mention_impact": 5,
            "upgrade_impact_floor": 3,
        },
    }
    narratives = {
        "narratives": {
            "ai_agents": {"name": "AI/Agents", "keywords": ["ai", "agent", "autonomous", "llm"]},
            "defi": {"name": "DeFi", "keywords": ["lending", "dex", "yield", "swap", "liquidity"]},
            "l2_infrastructure": {"name": "L2 Infrastructure", "keywords": ["rollup", "sequencer", "bridge", "l2"]},
        },
        "velocity_thresholds": {"accelerating": 50, "fading": -30, "convergence": 3},
    }
    sources = {
        "defillama": {"chains_endpoint": "https://api.llama.fi/chains"},
        "coingecko": {"base_url": "https://api.coingecko.com/api/v3", "rate_limit_per_min": 30},
        "github": {"api_base": "https://api.github.com"},
    }

    import config.loader as loader_mod

    monkeypatch.setattr(loader_mod, "_chains", chains)
    monkeypatch.setattr(loader_mod, "_baselines", baselines)
    monkeypatch.setattr(loader_mod, "_narratives", narratives)
    monkeypatch.setattr(loader_mod, "_sources", sources)

    # Disable LLM digest generation in unit tests to avoid hanging on Ollama calls
    monkeypatch.setenv("LLM_DIGEST_ENABLED", "false")

    return {"chains": chains, "baselines": baselines, "narratives": narratives, "sources": sources}
