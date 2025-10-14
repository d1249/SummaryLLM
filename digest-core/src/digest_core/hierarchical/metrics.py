"""
Metrics for hierarchical processing.
"""
from typing import Dict, List


class HierarchicalMetrics:
    """Metrics for hierarchical processing."""
    
    def __init__(self):
        self.threads_summarized = 0
        self.threads_skipped_small = 0
        self.per_thread_tokens: List[float] = []
        self.final_input_tokens = 0
        self.parallel_time_ms = 0
        self.total_time_ms = 0
        self.timeouts = 0
        self.errors = 0
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "threads_summarized": self.threads_summarized,
            "threads_skipped_small": self.threads_skipped_small,
            "per_thread_avg_tokens": (
                sum(self.per_thread_tokens) / len(self.per_thread_tokens)
                if self.per_thread_tokens else 0
            ),
            "final_input_tokens": self.final_input_tokens,
            "parallel_time_ms": self.parallel_time_ms,
            "total_time_ms": self.total_time_ms,
            "timeouts": self.timeouts,
            "errors": self.errors
        }

