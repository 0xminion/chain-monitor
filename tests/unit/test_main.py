"""Tests for main.py v0.1.0 async pipeline (agent-native)."""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

from processors.pipeline_types import PipelineContext, RawEvent, ChainDigest


class TestRunPipeline:
    """Test the full v2 async pipeline orchestration with agent-native checkpoint."""

    @pytest.mark.asyncio
    async def test_pipeline_runs_all_stages(self, mock_config):
        """Verify all 7 stages execute and produce a digest."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
        ):
            # Stage 1: collectors return raw events
            mock_collect_all.return_value = (
                [
                    RawEvent(chain="solana", category="TECH_EVENT", subcategory="upgrade", description="v2", source="rss", reliability=0.7),
                    RawEvent(chain="ethereum", category="TECH_EVENT", subcategory="upgrade", description="v3", source="rss", reliability=0.7),
                ],
                {"DefiLlama": {"status": "healthy"}},
                {},
            )

            # Stage 2: dedup returns same (no dups)
            mock_dedup.return_value = [
                RawEvent(chain="solana", category="TECH_EVENT", subcategory="upgrade", description="v2", source="rss", reliability=0.7),
                RawEvent(chain="ethereum", category="TECH_EVENT", subcategory="upgrade", description="v3", source="rss", reliability=0.7),
            ]

            # Stage 3: agent categorizer mock
            mock_categorizer = MagicMock()
            # Simulate agent having already categorized events
            mock_categorizer.try_load_results.return_value = [
                {"id": 0, "category": "TECH_EVENT", "subcategory": "upgrade", "reasoning": "Agent", "is_noise": False, "primary_mentions": ["solana"]},
                {"id": 1, "category": "TECH_EVENT", "subcategory": "upgrade", "reasoning": "Agent", "is_noise": False, "primary_mentions": ["ethereum"]},
            ]
            mock_categorizer.apply_categories.return_value = [
                {"chain": "solana", "category": "TECH_EVENT", "subcategory": "upgrade", "description": "v2", "source": "rss", "reliability": 0.7, "semantic": {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.85, "reasoning": "Agent", "is_noise": False, "primary_mentions": ["solana"]}},
                {"chain": "ethereum", "category": "TECH_EVENT", "subcategory": "upgrade", "description": "v3", "source": "rss", "reliability": 0.7, "semantic": {"category": "TECH_EVENT", "subcategory": "upgrade", "confidence": 0.85, "reasoning": "Agent", "is_noise": False, "primary_mentions": ["ethereum"]}},
            ]
            mock_cat_cls.return_value = mock_categorizer

            # Stage 4: scorer mock
            from processors.signal import Signal
            mock_scorer = MagicMock()
            mock_signal = MagicMock(spec=Signal)
            mock_signal.priority_score = 7
            mock_signal.source_count = 1
            mock_signal.description = "v2"
            mock_signal.chain = "solana"
            mock_scorer.score.return_value = mock_signal
            mock_scorer_cls.return_value = mock_scorer

            # Stage 4b: reinforcer
            mock_reinforcer = MagicMock()
            mock_reinforcer.process.return_value = (mock_signal, "created")
            mock_reinf_cls.return_value = mock_reinforcer

            # Stage 5: chain analyzer
            mock_digest = ChainDigest(
                chain="solana",
                chain_tier=1,
                chain_category="majors",
                summary="Solana v2.",
                priority_score=8,
                dominant_topic="Mainnet v2",
                confidence=0.9,
                event_count=1,
                sources_seen=1,
            )
            mock_analyze.return_value = [mock_digest]

            # Stage 6: agent runner
            mock_runner = MagicMock()
            mock_runner.synthesize = AsyncMock(return_value="📊 Chain Monitor — Apr 27, 2026\n\nSolana v2.")
            mock_runner.synthesize_weekly = AsyncMock(return_value="📈 Weekly Brief")
            mock_runner_cls.return_value = mock_runner

            # Prevent alert injection from real disk state by passing a fresh metrics instance
            from processors.metrics import PipelineMetrics
            mock_metrics = PipelineMetrics()
            # Monkeypatch to prevent disk reads
            mock_metrics.get_collector_alert_lines = lambda health: []

            from main import run_pipeline
            ctx = await run_pipeline(metrics=mock_metrics)

            assert isinstance(ctx, PipelineContext)
            assert "📊 Chain Monitor — Apr 27, 2026" in ctx.final_digest
            assert "Solana v2." in ctx.final_digest
            # Stage 6 now returns prompt directly, so final_digest IS the digest
            assert "Agent synthesis required" not in str(ctx.final_digest)
            mock_collect_all.assert_awaited_once()
            mock_analyze.assert_awaited_once()
            mock_runner.synthesize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_continues_without_agent_categorization(self, mock_config):
        """Pipeline no longer blocks on agent categorization — falls through to source categories."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
        ):
            mock_collect_all.return_value = (
                [RawEvent(chain="solana", category="TECH_EVENT", subcategory="upgrade", description="v2", source="rss", reliability=0.7)],
                {"DefiLlama": {"status": "healthy"}},
                {},
            )
            mock_dedup.return_value = [RawEvent(chain="solana", category="TECH_EVENT", subcategory="upgrade", description="v2", source="rss", reliability=0.7)]

            # No agent output available
            mock_categorizer = MagicMock()
            mock_categorizer.try_load_results.return_value = None
            mock_cat_cls.return_value = mock_categorizer

            mock_scorer = MagicMock()
            mock_scorer_cls.return_value = mock_scorer
            mock_reinf = MagicMock()
            mock_reinf_cls.return_value = mock_reinf
            mock_analyze.return_value = []
            mock_runner = MagicMock()
            mock_runner.synthesize = AsyncMock(return_value="Quiet day.")
            mock_runner_cls.return_value = mock_runner

            # Prevent alert injection from real disk state
            from processors.metrics import PipelineMetrics
            mock_metrics = PipelineMetrics()
            mock_metrics.get_collector_alert_lines = lambda health: []

            from main import run_pipeline
            ctx = await run_pipeline(metrics=mock_metrics)

            # Pipeline should now continue to scoring instead of stopping
            mock_scorer.score.assert_called()
            mock_reinf.process.assert_called()
            assert "Agent synthesis required" not in str(ctx.final_digest)

    @pytest.mark.asyncio
    async def test_pipeline_skips_send_when_no_activity(self, mock_config):
        """If fewer than 3 chains have activity, digest notes quiet day."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
        ):
            mock_collect_all.return_value = ([], {"DefiLlama": {"status": "healthy"}}, {})
            mock_dedup.return_value = []

            mock_categorizer = MagicMock()
            mock_categorizer.try_load_results.return_value = []
            mock_categorizer.apply_categories.return_value = []
            mock_cat_cls.return_value = mock_categorizer

            mock_scorer = MagicMock()
            mock_scorer_cls.return_value = mock_scorer
            mock_reinf = MagicMock()
            mock_reinf_cls.return_value = mock_reinf
            mock_analyze.return_value = []
            mock_runner = MagicMock()
            mock_runner.synthesize = AsyncMock(return_value="Quiet day.")
            mock_runner_cls.return_value = mock_runner

            # Prevent alert injection from real disk state
            from processors.metrics import PipelineMetrics
            mock_metrics = PipelineMetrics()
            mock_metrics.get_collector_alert_lines = lambda health: []

            from main import run_pipeline
            ctx = await run_pipeline(metrics=mock_metrics)

        assert ctx.final_digest == "Quiet day."
