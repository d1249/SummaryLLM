"""
Test CLI functionality and exit codes.
"""
import pytest
from unittest.mock import Mock, patch
from digest_core.cli import app
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_run_help(runner):
    """Test CLI run command help."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "from-date" in result.output
    assert "sources" in result.output
    assert "out" in result.output
    assert "model" in result.output


def test_cli_run_dry_run(runner):
    """Test CLI run with dry-run flag."""
    with patch('digest_core.cli.run_digest') as mock_run:
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "--dry-run"
        ])
        
        # Dry-run should exit with code 2
        assert result.exit_code == 2
        assert "dry-run" in result.output.lower()


def test_cli_run_success(runner):
    """Test CLI run success path."""
    with patch('digest_core.cli.run_digest') as mock_run:
        mock_run.return_value = None
        
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
        ])
        
        # Should exit with code 0
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_with_window(runner):
    """Test CLI run with window parameter."""
    with patch('digest_core.cli.run_digest') as mock_run:
        mock_run.return_value = None
        
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "--window", "rolling_24h"
        ])
        
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_with_state(runner):
    """Test CLI run with state parameter."""
    with patch('digest_core.cli.run_digest') as mock_run:
        mock_run.return_value = None
        
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "--state", "/tmp/state"
        ])
        
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_invalid_date(runner):
    """Test CLI run with invalid date."""
    result = runner.invoke(app, [
        "run",
        "--from-date", "invalid-date",
        "--sources", "ews",
        "--out", "/tmp/test",
        "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
    ])
    
    # Should exit with error code
    assert result.exit_code != 0


def test_cli_run_missing_required_args(runner):
    """Test CLI run with missing required arguments."""
    result = runner.invoke(app, [
        "run",
        "--from-date", "2024-01-15"
        # Missing sources, out, model
    ])
    
    # Should exit with error code
    assert result.exit_code != 0


def test_cli_run_multiple_sources(runner):
    """Test CLI run with multiple sources."""
    with patch('digest_core.cli.run_digest') as mock_run:
        mock_run.return_value = None
        
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews,slack",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
        ])
        
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_exception_handling(runner):
    """Test CLI run exception handling."""
    with patch('digest_core.cli.run_digest') as mock_run:
        mock_run.side_effect = Exception("Test error")
        
        result = runner.invoke(app, [
            "run",
            "--from-date", "2024-01-15",
            "--sources", "ews",
            "--out", "/tmp/test",
            "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
        ])
        
        # Should exit with error code
        assert result.exit_code != 0
        assert "Test error" in result.output


def test_cli_run_config_loading(runner):
    """Test CLI run config loading."""
    with patch('digest_core.cli.Config') as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        with patch('digest_core.cli.run_digest') as mock_run:
            mock_run.return_value = None
            
            result = runner.invoke(app, [
                "run",
                "--from-date", "2024-01-15",
                "--sources", "ews",
                "--out", "/tmp/test",
                "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
            ])
            
            assert result.exit_code == 0
            mock_config_class.assert_called_once()


def test_cli_run_logging(runner):
    """Test CLI run logging setup."""
    with patch('digest_core.cli.setup_logging') as mock_logging:
        with patch('digest_core.cli.run_digest') as mock_run:
            mock_run.return_value = None
            
            result = runner.invoke(app, [
                "run",
                "--from-date", "2024-01-15",
                "--sources", "ews",
                "--out", "/tmp/test",
                "--model", "Qwen/Qwen3-30B-A3B-Instruct-2507"
            ])
            
            assert result.exit_code == 0
            mock_logging.assert_called_once()
