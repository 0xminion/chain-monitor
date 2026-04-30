"""Tests for main.py v2.0 async pipeline (agent-native)."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from processors.pipeline_types import PipelineContext, RawEvent


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
            patch("main.synthesize_digest", new_callable=AsyncMock) as mock_synth,
            patch("main.TelegramSender") as mock_sender_cls,
        ):
            # Stage 1: collectors return raw events
            mock_collect_all.return_value = (
                [
                    RawEvent("solana", "TECH_EVENT", "upgrade", "v2", "rss", 0.7),
                    RawEvent("ethereum", "TECH_EVENT", "upgrade", "v3", "rss", 0.7),
                ],
                {"DefiLlama": {"status": "healthy"}},
                {},
            )

            # Stage 2: dedup returns same (no dups)
            mock_dedup.return_value = [
                RawEvent("solana", "TECH_EVENT", "upgrade", "v2", "rss", 0.7),
                RawEvent("ethereum", "TECH_EVENT", "upgrade", "v3", "rss", 0.7),
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
            from processors.chain_analyzer import ChainDigest
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

            # Stage 6: summary
            mock_synth.return_value = "📊 Chain Monitor — Apr 27, 2026\n\nSolana v2."

            # Stage 7: telegram
            mock_sender = AsyncMock()
            mock_sender.send.return_value = True
            mock_sender_cls.return_value = mock_sender

            from main import run_pipeline
            ctx = await run_pipeline()

            assert isinstance(ctx, PipelineContext)
            assert ctx.final_digest == "📊 Chain Monitor — Apr 27, 2026\n\nSolana v2."
            assert len(ctx.chain_digests) == 1
            mock_collect_all.assert_awaited_once()
            mock_analyze.assert_awaited_once()
            mock_synth.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_stops_at_agent_checkpoint(self, mock_config):
        """If no agent categorization output exists, pipeline should stop at checkpoint."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.synthesize_digest", new_callable=AsyncMock) as mock_synth,
            patch("main.TelegramSender") as mock_sender_cls,
        ):
            mock_collect_all.return_value = (
                [RawEvent("solana", "TECH_EVENT", "upgrade", "v2", "rss", 0.7)],
                {"DefiLlama": {"status": "healthy"}},
                {},
            )
            mock_dedup.return_value = [RawEvent("solana", "TECH_EVENT", "upgrade", "v2", "rss", 0.7)]

            # No agent output available
            mock_categorizer = MagicMock()
            mock_categorizer.try_load_results.return_value = None
            mock_categorizer.prepare_agent_task.return_value = MagicMock(name="task_path")
            mock_cat_cls.return_value = mock_categorizer

            mock_scorer = MagicMock()
            mock_scorer_cls.return_value = mock_scorer
            mock_reinf = MagicMock()
            mock_reinf_cls.return_value = mock_reinf
            mock_analyze.return_value = []
            mock_synth.return_value = "Quiet day."

            mock_sender = AsyncMock()
            mock_sender_cls.return_value = mock_sender

            from main import run_pipeline
            ctx = await run_pipeline()

            # Pipeline should stop at checkpoint, not send telegram
            mock_sender.send.assert_not_awaited()
            mock_scorer.score.assert_not_called()
            assert "Agent categorization required" in ctx.final_digest

    @pytest.mark.asyncio
    async def test_pipeline_skips_send_when_no_activity(self, mock_config):
        """If fewer than 3 chains have activity, don't send Telegram."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.synthesize_digest", new_callable=AsyncMock) as mock_synth,
            patch("main.TelegramSender") as mock_sender_cls,
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
            mock_synth.return_value = "Quiet day."

            mock_sender = AsyncMock()
            mock_sender_cls.return_value = mock_sender

            from main import run_pipeline
            ctx = await run_pipeline()

            mock_sender.send.assert_not_awaited()
        assert ctx.final_digest == "Quiet day."
