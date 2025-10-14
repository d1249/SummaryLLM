"""
Tests for hierarchical mode thresholds.
"""
import pytest
from digest_core.hierarchical.processor import HierarchicalProcessor
from digest_core.config import HierarchicalConfig
from digest_core.llm.gateway import LLMGateway
from digest_core.config import LLMConfig


def test_hierarchy_not_activated_below_threshold():
    """Test hierarchical mode is NOT activated below threshold."""
    config = HierarchicalConfig(
        enable=True,
        enable_auto=True,
        threshold_threads=40,
        threshold_emails=200,
        min_threads_to_summarize=6
    )
    llm_config = LLMConfig(endpoint="http://test", model="test")
    llm_gateway = LLMGateway(llm_config)
    processor = HierarchicalProcessor(config, llm_gateway)
    
    # 37 threads, 61 emails - below threshold
    threads = [f"thread_{i}" for i in range(37)]
    emails = [f"email_{i}" for i in range(61)]
    
    should_use = processor.should_use_hierarchical(threads, emails)
    assert should_use is False


def test_hierarchy_activated_above_thread_threshold():
    """Test hierarchical mode IS activated above thread threshold."""
    config = HierarchicalConfig(
        enable=True,
        enable_auto=True,
        threshold_threads=40,
        threshold_emails=200,
        min_threads_to_summarize=6
    )
    llm_config = LLMConfig(endpoint="http://test", model="test")
    llm_gateway = LLMGateway(llm_config)
    processor = HierarchicalProcessor(config, llm_gateway)
    
    # 45 threads, 61 emails - above thread threshold
    threads = [f"thread_{i}" for i in range(45)]
    emails = [f"email_{i}" for i in range(61)]
    
    should_use = processor.should_use_hierarchical(threads, emails)
    assert should_use is True


def test_hierarchy_not_activated_below_min_threads():
    """Test hierarchical mode NOT activated if below min_threads_to_summarize."""
    config = HierarchicalConfig(
        enable=True,
        enable_auto=True,
        threshold_threads=10,  # Low threshold
        threshold_emails=50,
        min_threads_to_summarize=20  # High minimum
    )
    llm_config = LLMConfig(endpoint="http://test", model="test")
    llm_gateway = LLMGateway(llm_config)
    processor = HierarchicalProcessor(config, llm_gateway)
    
    # 15 threads - above threshold_threads but below min_threads_to_summarize
    threads = [f"thread_{i}" for i in range(15)]
    emails = [f"email_{i}" for i in range(100)]
    
    should_use = processor.should_use_hierarchical(threads, emails)
    assert should_use is False  # Not enough threads to summarize

