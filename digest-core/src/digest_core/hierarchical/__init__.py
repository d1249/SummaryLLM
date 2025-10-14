"""
Hierarchical digest processing module.

Provides per-thread summarization and final aggregation for large email volumes.
"""
from .processor import HierarchicalProcessor
from .metrics import HierarchicalMetrics

__all__ = ['HierarchicalProcessor', 'HierarchicalMetrics']

