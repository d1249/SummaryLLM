"""
Test idempotency with T-48h rebuild window.
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from digest_core.run import run_digest


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for testing."""
    return tmp_path / "out"


@pytest.fixture
def temp_state_dir(tmp_path):
    """Temporary state directory for testing."""
    return tmp_path / "state"


def test_idempotency_within_48h(temp_output_dir, temp_state_dir):
    """Test that runs are skipped when artifacts are within 48h window."""
    # Create existing artifacts
    json_path = temp_output_dir / "digest-2024-01-15.json"
    md_path = temp_output_dir / "digest-2024-01-15.md"
    
    # Create files with recent timestamps (within 48h)
    json_path.touch()
    md_path.touch()
    
    # Mock the config and other dependencies
    with patch('digest_core.run.Config') as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        with patch('digest_core.run.EWSIngester') as mock_ews:
            with patch('digest_core.run.HTMLNormalizer') as mock_html:
                with patch('digest_core.run.QuoteCleaner') as mock_quotes:
                    with patch('digest_core.run.ThreadBuilder') as mock_threads:
                        with patch('digest_core.run.EvidenceSplitter') as mock_evidence:
                            with patch('digest_core.run.ContextSelector') as mock_selector:
                                with patch('digest_core.run.LLMGateway') as mock_llm:
                                    with patch('digest_core.run.JSONOutputWriter') as mock_json:
                                        with patch('digest_core.run.MarkdownOutputWriter') as mock_md:
                                            with patch('digest_core.run.MetricsCollector') as mock_metrics:
                                                with patch('digest_core.run.start_health_server'):
                                                    # Run should be skipped
                                                    result = run_digest(
                                                        from_date="2024-01-15",
                                                        sources=["ews"],
                                                        out=str(temp_output_dir),
                                                        model="gpt-4o-mini"
                                                    )
                                                    
                                                    # Should not call EWS or other components
                                                    mock_ews.assert_not_called()
                                                    mock_llm.assert_not_called()


def test_idempotency_outside_48h(temp_output_dir, temp_state_dir):
    """Test that runs proceed when artifacts are outside 48h window."""
    # Create existing artifacts
    json_path = temp_output_dir / "digest-2024-01-15.json"
    md_path = temp_output_dir / "digest-2024-01-15.md"
    
    # Create files with old timestamps (outside 48h)
    json_path.touch()
    md_path.touch()
    
    # Manually set old modification time (50 hours ago)
    old_time = datetime.now(timezone.utc).timestamp() - (50 * 3600)
    json_path.stat().st_mtime = old_time
    md_path.stat().st_mtime = old_time
    
    # Mock the config and other dependencies
    with patch('digest_core.run.Config') as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        with patch('digest_core.run.EWSIngester') as mock_ews:
            mock_ews_instance = Mock()
            mock_ews.return_value = mock_ews_instance
            mock_ews_instance.fetch_messages.return_value = []
            
            with patch('digest_core.run.HTMLNormalizer') as mock_html:
                with patch('digest_core.run.QuoteCleaner') as mock_quotes:
                    with patch('digest_core.run.ThreadBuilder') as mock_threads:
                        with patch('digest_core.run.EvidenceSplitter') as mock_evidence:
                            with patch('digest_core.run.ContextSelector') as mock_selector:
                                with patch('digest_core.run.LLMGateway') as mock_llm:
                                    with patch('digest_core.run.JSONOutputWriter') as mock_json:
                                        with patch('digest_core.run.MarkdownOutputWriter') as mock_md:
                                            with patch('digest_core.run.MetricsCollector') as mock_metrics:
                                                with patch('digest_core.run.start_health_server'):
                                                    # Run should proceed
                                                    result = run_digest(
                                                        from_date="2024-01-15",
                                                        sources=["ews"],
                                                        out=str(temp_output_dir),
                                                        model="gpt-4o-mini"
                                                    )
                                                    
                                                    # Should call EWS
                                                    mock_ews.assert_called_once()


def test_idempotency_missing_artifacts(temp_output_dir, temp_state_dir):
    """Test that runs proceed when artifacts are missing."""
    # Don't create any artifacts
    
    # Mock the config and other dependencies
    with patch('digest_core.run.Config') as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        with patch('digest_core.run.EWSIngester') as mock_ews:
            mock_ews_instance = Mock()
            mock_ews.return_value = mock_ews_instance
            mock_ews_instance.fetch_messages.return_value = []
            
            with patch('digest_core.run.HTMLNormalizer') as mock_html:
                with patch('digest_core.run.QuoteCleaner') as mock_quotes:
                    with patch('digest_core.run.ThreadBuilder') as mock_threads:
                        with patch('digest_core.run.EvidenceSplitter') as mock_evidence:
                            with patch('digest_core.run.ContextSelector') as mock_selector:
                                with patch('digest_core.run.LLMGateway') as mock_llm:
                                    with patch('digest_core.run.JSONOutputWriter') as mock_json:
                                        with patch('digest_core.run.MarkdownOutputWriter') as mock_md:
                                            with patch('digest_core.run.MetricsCollector') as mock_metrics:
                                                with patch('digest_core.run.start_health_server'):
                                                    # Run should proceed
                                                    result = run_digest(
                                                        from_date="2024-01-15",
                                                        sources=["ews"],
                                                        out=str(temp_output_dir),
                                                        model="gpt-4o-mini"
                                                    )
                                                    
                                                    # Should call EWS
                                                    mock_ews.assert_called_once()


def test_idempotency_partial_artifacts(temp_output_dir, temp_state_dir):
    """Test that runs proceed when only one artifact exists."""
    # Create only JSON file
    json_path = temp_output_dir / "digest-2024-01-15.json"
    json_path.touch()
    
    # Mock the config and other dependencies
    with patch('digest_core.run.Config') as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        with patch('digest_core.run.EWSIngester') as mock_ews:
            mock_ews_instance = Mock()
            mock_ews.return_value = mock_ews_instance
            mock_ews_instance.fetch_messages.return_value = []
            
            with patch('digest_core.run.HTMLNormalizer') as mock_html:
                with patch('digest_core.run.QuoteCleaner') as mock_quotes:
                    with patch('digest_core.run.ThreadBuilder') as mock_threads:
                        with patch('digest_core.run.EvidenceSplitter') as mock_evidence:
                            with patch('digest_core.run.ContextSelector') as mock_selector:
                                with patch('digest_core.run.LLMGateway') as mock_llm:
                                    with patch('digest_core.run.JSONOutputWriter') as mock_json:
                                        with patch('digest_core.run.MarkdownOutputWriter') as mock_md:
                                            with patch('digest_core.run.MetricsCollector') as mock_metrics:
                                                with patch('digest_core.run.start_health_server'):
                                                    # Run should proceed
                                                    result = run_digest(
                                                        from_date="2024-01-15",
                                                        sources=["ews"],
                                                        out=str(temp_output_dir),
                                                        model="gpt-4o-mini"
                                                    )
                                                    
                                                    # Should call EWS
                                                    mock_ews.assert_called_once()
