"""End-to-end regression test for the agent-native pipeline.

Verifies the full pipeline produces a valid digest (prompt or prose),
never emits meta-instructions, and saves required artifacts.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from processors.pipeline_types import RawEvent, ChainDigest


@pytest.fixture
def sample_raw_events():
    return [
        RawEvent(chain="solana", category="TECH_EVENT", subcategory="upgrade", description="v2 tagged", source="rss", reliability=0.7),
        RawEvent(chain="ethereum", category="VISIBILITY", subcategory="conference", description="Vitalik keynote", source="rss", reliability=0.6),
    ]


class TestE2EPipeline:

    @pytest.mark.asyncio
    async def test_pipeline_produces_non_empty_digest(self, mock_config, sample_raw_events):
        """Full pipeline must produce a non-empty digest with no meta-instructions."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
            patch("main.TelegramSender") as mock_sender_cls,
            patch("main._save_run_log") as mock_save_log,
            patch("main._persist_daily_digest") as mock_persist,
            patch("main.PipelineMetrics.write") as mock_metrics_write,
        ):
            # Stage 1
            mock_collect_all.return_value = (sample_raw_events, {"rss": {"status": "healthy"}}, {})
            # Stage 2
            mock_dedup.return_value = sample_raw_events
            # Stage 3
            mock_cat = MagicMock()
            mock_cat.try_load_results.return_value = None
            mock_cat_cls.return_value = mock_cat
            # Stage 4
            from processors.signal import Signal
            mock_scorer = MagicMock()
            mock_sig = MagicMock(spec=Signal)
            mock_sig.priority_score = 7
            mock_sig.source_count = 1
            mock_sig.description = "v2 tagged"
            mock_sig.chain = "solana"
            mock_sig.activity = [{"source": "rss", "reliability": 0.7}]
            mock_scorer.score.return_value = mock_sig
            mock_scorer_cls.return_value = mock_scorer
            # Stage 4b
            mock_reinf = MagicMock()
            mock_reinf.process.return_value = (mock_sig, "created")
            mock_reinf_cls.return_value = mock_reinf
            # Stage 5
            mock_digests = [
                ChainDigest(chain="solana", chain_tier=1, chain_category="majors", summary="Solana v2",
                            priority_score=8, dominant_topic="Mainnet v2", confidence=0.9, event_count=1, sources_seen=1),
                ChainDigest(chain="ethereum", chain_tier=1, chain_category="majors", summary="ETH conf",
                            priority_score=2, dominant_topic="Quiet", confidence=0.6, event_count=1, sources_seen=1),
            ]
            mock_analyze.return_value = mock_digests
            # Stage 6 — agent runner
            mock_runner = MagicMock()
            mock_runner.synthesize = AsyncMock(return_value="📊 Chain Monitor — Apr 27, 2026\n\nSolana v2 released. Ethereum quiet.")
            mock_runner.synthesize_weekly = AsyncMock(return_value="📈 Weekly Brief\n\nWeek summary.")
            mock_runner_cls.return_value = mock_runner
            # Stage 7
            mock_sender = AsyncMock()
            mock_sender.send = AsyncMock(return_value=True)
            mock_sender_cls.return_value = mock_sender

            from main import run_pipeline
            ctx = await run_pipeline()

            # Assertions
            assert ctx is not None
            assert ctx.final_digest
            assert isinstance(ctx.final_digest, str)
            assert len(ctx.final_digest) > 50
            assert "Agent synthesis required" not in ctx.final_digest
            assert "🤖" not in ctx.final_digest
            assert "📊 Chain Monitor" in ctx.final_digest
            mock_metrics_write.assert_called_once()
            mock_save_log.assert_called_once()
            mock_persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_weekly_flag(self, mock_config):
        """Pipeline with weekly=True should call synthesize_weekly."""
        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
            patch("main.TelegramSender") as mock_sender_cls,
            patch("main._save_run_log"),
            patch("main._persist_daily_digest"),
            patch("main.PipelineMetrics.write"),
        ):
            mock_collect_all.return_value = ([], {"rss": {"status": "healthy"}}, {})
            mock_dedup.return_value = []
            mock_cat = MagicMock()
            mock_cat.try_load_results.return_value = None
            mock_cat_cls.return_value = mock_cat
            mock_scorer_cls.return_value = MagicMock()
            mock_reinf_cls.return_value = MagicMock()
            mock_analyze.return_value = []
            mock_runner = MagicMock()
            mock_runner.synthesize_weekly = AsyncMock(return_value="📈 Weekly Brief — week summary")
            mock_runner.synthesize = AsyncMock()
            mock_runner_cls.return_value = mock_runner
            mock_sender = AsyncMock()
            mock_sender_cls.return_value = mock_sender

            from main import run_pipeline
            ctx = await run_pipeline(weekly=True)

            mock_runner.synthesize_weekly.assert_awaited_once()
            mock_runner.synthesize.assert_not_awaited()
            assert "📈 Weekly Brief" in ctx.final_digest

    @pytest.mark.asyncio
    async def test_pipeline_injects_collector_alerts(self, mock_config, sample_raw_events):
        """When collectors have consecutive empty runs, alerts are injected into digest."""
        from processors.metrics import PipelineMetrics

        # Seed previous run state with consecutive empties for defillama
        import json
        metrics_dir = Path(__file__).parent.parent / "storage" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        state_file = metrics_dir / "collector_run_state.json"
        seed_state = {"defillama": {"events": 0, "errors": 0, "consecutive_empty_runs": 2, "status": "healthy"}}
        state_file.write_text(json.dumps(seed_state))

        with (
            patch("main.collect_all", new_callable=AsyncMock) as mock_collect_all,
            patch("main.deduplicate_events") as mock_dedup,
            patch("main.EventCategorizer") as mock_cat_cls,
            patch("main.SignalScorer") as mock_scorer_cls,
            patch("main.SignalReinforcer") as mock_reinf_cls,
            patch("main.analyze_all_chains", new_callable=AsyncMock) as mock_analyze,
            patch("main.AgentDigestRunner") as mock_runner_cls,
            patch("main.TelegramSender") as mock_sender_cls,
            patch("main._save_run_log"),
            patch("main._persist_daily_digest"),
        ):
            mock_collect_all.return_value = (sample_raw_events, {"defillama": {"status": "healthy"}}, {})
            mock_dedup.return_value = sample_raw_events
            mock_cat = MagicMock()
            mock_cat.try_load_results.return_value = None
            mock_cat_cls.return_value = mock_cat
            from processors.signal import Signal
            mock_scorer = MagicMock()
            mock_sig = MagicMock(spec=Signal)
            mock_sig.priority_score = 7
            mock_sig.source_count = 1
            mock_sig.description = "v2"
            mock_sig.chain = "solana"
            mock_sig.activity = [{"source": "rss", "reliability": 0.7}]
            mock_scorer.score.return_value = mock_sig
            mock_scorer_cls.return_value = mock_scorer
            mock_reinf = MagicMock()
            mock_reinf.process.return_value = (mock_sig, "created")
            mock_reinf_cls.return_value = mock_reinf
            mock_digests = [
                ChainDigest(chain="solana", chain_tier=1, chain_category="majors", summary="v2",
                            priority_score=8, dominant_topic="Mainnet v2", confidence=0.9, event_count=1, sources_seen=1),
            ]
            mock_analyze.return_value = mock_digests
            mock_runner = MagicMock()
            mock_runner.synthesize = AsyncMock(return_value="📊 Chain Monitor — Apr 27\n\nSolana v2.")
            mock_runner_cls.return_value = mock_runner
            mock_sender = AsyncMock()
            mock_sender_cls.return_value = mock_sender

            # Build metrics manually to seed defillama as empty
            metrics = PipelineMetrics()
            metrics.record_collector("defillama", events=0, error=False)
            metrics.record_collector("rss", events=2, error=False)

            from main import run_pipeline
            ctx = await run_pipeline(metrics=metrics)

            assert "⚠️ Collector Alert" in ctx.final_digest
            assert "DefiLlama" in ctx.final_digest

        # Cleanup
        if state_file.exists():
            state_file.unlink()
