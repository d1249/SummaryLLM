"""
Test LLM gateway with retry logic and token usage.
"""
import pytest
from unittest.mock import Mock, patch
from digest_core.llm.gateway import LLMGateway
from digest_core.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for LLM testing."""
    config = Mock(spec=Config)
    config.llm.endpoint = "https://api.openai.com/v1/chat/completions"
    config.llm.headers = {"Authorization": "Bearer test-token"}
    config.llm.model = "gpt-4o-mini"
    config.llm.max_retries = 3
    config.llm.timeout = 30
    return config


@pytest.fixture
def gateway(mock_config):
    """LLM gateway with mocked configuration."""
    return LLMGateway(mock_config)


def test_invalid_json_retry(gateway):
    """Test retry logic for invalid JSON responses."""
    # Mock first response with invalid JSON
    invalid_response = Mock()
    invalid_response.json.return_value = {"invalid": "json"}
    invalid_response.status_code = 200
    
    # Mock second response with valid JSON
    valid_response = Mock()
    valid_response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": [{"title": "Test", "items": []}]}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    valid_response.status_code = 200
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.side_effect = [invalid_response, valid_response]
        
        result = gateway.extract_actions([], "test-trace-id")
        
        assert result["trace_id"] == "test-trace-id"
        assert result["data"]["sections"] == [{"title": "Test", "items": []}]
        assert mock_post.call_count == 2


def test_quality_retry_empty_sections(gateway):
    """Test quality retry for empty sections with positive evidence."""
    # Mock response with empty sections
    empty_response = Mock()
    empty_response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": []}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    empty_response.status_code = 200
    
    # Mock second response with content
    content_response = Mock()
    content_response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": [{"title": "Test", "items": []}]}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    content_response.status_code = 200
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.side_effect = [empty_response, content_response]
        
        # Provide positive evidence
        evidence = [Mock(content="Important action item")]
        
        result = gateway.extract_actions(evidence, "test-trace-id")
        
        assert result["trace_id"] == "test-trace-id"
        assert result["data"]["sections"] == [{"title": "Test", "items": []}]
        assert mock_post.call_count == 2


def test_token_usage_extraction(gateway):
    """Test extraction of token usage from response."""
    # Mock response with token usage
    response = Mock()
    response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": [{"title": "Test", "items": []}]}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    response.status_code = 200
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = response
        
        result = gateway.extract_actions([], "test-trace-id")
        
        assert result["meta"]["tokens_in"] == 100
        assert result["meta"]["tokens_out"] == 50


def test_latency_measurement(gateway):
    """Test latency measurement."""
    response = Mock()
    response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": [{"title": "Test", "items": []}]}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    response.status_code = 200
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = response
        
        result = gateway.extract_actions([], "test-trace-id")
        
        assert "latency_ms" in result
        assert result["latency_ms"] > 0


def test_http_error_handling(gateway):
    """Test handling of HTTP errors."""
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            gateway.extract_actions([], "test-trace-id")


def test_rate_limit_handling(gateway):
    """Test handling of rate limit errors."""
    # Mock rate limit response
    rate_limit_response = Mock()
    rate_limit_response.status_code = 429
    rate_limit_response.json.return_value = {"error": "Rate limit exceeded"}
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = rate_limit_response
        
        with pytest.raises(Exception):
            gateway.extract_actions([], "test-trace-id")


def test_authentication_error(gateway):
    """Test handling of authentication errors."""
    # Mock auth error response
    auth_response = Mock()
    auth_response.status_code = 401
    auth_response.json.return_value = {"error": "Unauthorized"}
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = auth_response
        
        with pytest.raises(Exception):
            gateway.extract_actions([], "test-trace-id")


def test_timeout_handling(gateway):
    """Test handling of timeout errors."""
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.side_effect = Exception("Timeout")
        
        with pytest.raises(Exception, match="Timeout"):
            gateway.extract_actions([], "test-trace-id")


def test_evidence_formatting(gateway):
    """Test formatting of evidence for LLM."""
    evidence = [
        Mock(content="First evidence chunk", evidence_id="ev-1"),
        Mock(content="Second evidence chunk", evidence_id="ev-2")
    ]
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = Mock(
            json=lambda: {
                "choices": [{"message": {"content": '{"sections": []}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}
            },
            status_code=200
        )
        
        gateway.extract_actions(evidence, "test-trace-id")
        
        # Check that evidence was formatted correctly
        call_args = mock_post.call_args
        assert "messages" in call_args[1]["json"]
        messages = call_args[1]["json"]["messages"]
        
        # Should have system and user messages
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


def test_trace_id_preservation(gateway):
    """Test that trace_id is preserved through the call."""
    response = Mock()
    response.json.return_value = {
        "choices": [{"message": {"content": '{"sections": [{"title": "Test", "items": []}]}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    response.status_code = 200
    
    with patch('digest_core.llm.gateway.httpx.post') as mock_post:
        mock_post.return_value = response
        
        trace_id = "unique-trace-id-123"
        result = gateway.extract_actions([], trace_id)
        
        assert result["trace_id"] == trace_id
