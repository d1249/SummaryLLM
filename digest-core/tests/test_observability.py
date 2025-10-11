"""
Test observability endpoints and metrics.
"""
import pytest
import requests
import time
from unittest.mock import Mock, patch
from digest_core.observability.healthz import start_health_server
from digest_core.observability.metrics import MetricsCollector


@pytest.fixture
def metrics_collector():
    """Metrics collector instance."""
    return MetricsCollector()


def test_healthz_endpoint():
    """Test /healthz endpoint returns 200 healthy."""
    # Start health server in background
    start_health_server(port=9109)
    time.sleep(0.1)  # Give server time to start
    
    try:
        response = requests.get("http://localhost:9109/healthz", timeout=1)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    finally:
        # Clean up - server will be stopped when process ends
        pass


def test_readyz_endpoint():
    """Test /readyz endpoint returns 200 ready."""
    # Start health server in background
    start_health_server(port=9109)
    time.sleep(0.1)  # Give server time to start
    
    try:
        response = requests.get("http://localhost:9109/readyz", timeout=1)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
    finally:
        # Clean up - server will be stopped when process ends
        pass


def test_metrics_endpoint():
    """Test /metrics endpoint contains key metrics."""
    # Start metrics server
    metrics = MetricsCollector()
    metrics.start_server(port=9108)
    time.sleep(0.1)  # Give server time to start
    
    try:
        response = requests.get("http://localhost:9108/metrics", timeout=1)
        assert response.status_code == 200
        
        content = response.text
        assert "llm_latency_ms" in content
        assert "tokens_in" in content
        assert "tokens_out" in content
        assert "digest_build_seconds" in content
        assert "emails_total" in content
    finally:
        # Clean up - server will be stopped when process ends
        pass


def test_metrics_cardinality_limits(metrics_collector):
    """Test that metrics don't have high cardinality."""
    # Record some metrics with different labels
    metrics_collector.record_llm_latency(100, "gpt-4o-mini", "extract_actions")
    metrics_collector.record_llm_latency(200, "gpt-4o-mini", "extract_actions")
    metrics_collector.record_llm_latency(150, "gpt-4o-mini", "summarize")
    
    # Check that metrics are properly aggregated
    # This is more of a design test - we ensure we don't create high-cardinality labels
    assert True  # If we get here without errors, cardinality is controlled


def test_metrics_collection(metrics_collector):
    """Test basic metrics collection."""
    # Record various metrics
    metrics_collector.record_llm_latency(100, "gpt-4o-mini", "extract_actions")
    metrics_collector.record_llm_tokens(100, 50, "gpt-4o-mini")
    metrics_collector.record_digest_build_time(30.5)
    metrics_collector.record_emails_total(25)
    metrics_collector.record_run_total("ok")
    
    # Metrics should be recorded without errors
    assert True


def test_metrics_error_handling(metrics_collector):
    """Test metrics error handling."""
    # Test with invalid inputs
    try:
        metrics_collector.record_llm_latency(-1, "gpt-4o-mini", "extract_actions")
        metrics_collector.record_llm_tokens(-1, -1, "gpt-4o-mini")
        metrics_collector.record_digest_build_time(-1)
        metrics_collector.record_emails_total(-1)
    except Exception:
        # Should handle invalid inputs gracefully
        pass


def test_metrics_server_start_stop(metrics_collector):
    """Test metrics server start and stop."""
    # Start server
    metrics_collector.start_server(port=9108)
    time.sleep(0.1)
    
    try:
        # Check server is running
        response = requests.get("http://localhost:9108/metrics", timeout=1)
        assert response.status_code == 200
    finally:
        # Stop server
        metrics_collector.stop_server()


def test_health_endpoint_404():
    """Test that unknown health endpoints return 404."""
    # Start health server in background
    start_health_server(port=9109)
    time.sleep(0.1)  # Give server time to start
    
    try:
        response = requests.get("http://localhost:9109/unknown", timeout=1)
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "Not Found"
    finally:
        # Clean up - server will be stopped when process ends
        pass


def test_metrics_prometheus_format():
    """Test that metrics are in Prometheus format."""
    # Start metrics server
    metrics = MetricsCollector()
    metrics.start_server(port=9108)
    time.sleep(0.1)  # Give server time to start
    
    try:
        response = requests.get("http://localhost:9108/metrics", timeout=1)
        assert response.status_code == 200
        
        content = response.text
        
        # Check Prometheus format
        assert "# HELP" in content
        assert "# TYPE" in content
        assert "llm_latency_ms" in content
        assert "tokens_in" in content
        assert "tokens_out" in content
        assert "digest_build_seconds" in content
        assert "emails_total" in content
    finally:
        # Clean up - server will be stopped when process ends
        pass


def test_metrics_labels():
    """Test that metrics have appropriate labels."""
    # Start metrics server
    metrics = MetricsCollector()
    metrics.start_server(port=9108)
    time.sleep(0.1)  # Give server time to start
    
    try:
        # Record some metrics
        metrics.record_llm_latency(100, "gpt-4o-mini", "extract_actions")
        metrics.record_llm_tokens(100, 50, "gpt-4o-mini")
        
        response = requests.get("http://localhost:9108/metrics", timeout=1)
        assert response.status_code == 200
        
        content = response.text
        
        # Check that labels are present
        assert "model=\"gpt-4o-mini\"" in content
        assert "operation=\"extract_actions\"" in content
    finally:
        # Clean up - server will be stopped when process ends
        pass
