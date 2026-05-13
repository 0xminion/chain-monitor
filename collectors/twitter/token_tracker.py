"""Token usage tracking — cumulative stats for pipeline run."""

import time
from dataclasses import dataclass, field

from collectors.twitter.provider import TokenUsage


@dataclass
class PipelineTokenTracker:
    """Tracks cumulative token usage across all provider calls in a run."""

    total_input: int = 0
    total_output: int = 0
    total_cached: int = 0
    call_count: int = 0
    error_count: int = 0
    start_time: float = field(default_factory=time.time)

    def record(self, usage: TokenUsage, had_error: bool = False) -> None:
        self.total_input += usage.input_tokens
        self.total_output += usage.output_tokens
        self.total_cached += usage.cached_tokens
        self.call_count += 1
        if had_error:
            self.error_count += 1

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def total_tokens(self) -> int:
        return self.total_input + self.total_output + self.total_cached

    def summary(self) -> dict:
        return {
            "calls": self.call_count,
            "errors": self.error_count,
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "cached_tokens": self.total_cached,
            "total_tokens": self.total_tokens,
            "duration_seconds": round(self.duration_seconds, 2),
            "avg_input_per_call": (
                self.total_input // self.call_count if self.call_count else 0
            ),
            "avg_output_per_call": (
                self.total_output // self.call_count if self.call_count else 0
            ),
        }
