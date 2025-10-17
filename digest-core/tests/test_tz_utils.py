"""
Test timezone utilities with metrics and rate-limited logging.
"""
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import Mock
from digest_core.utils.tz import ensure_aware, to_utc, ensure_aware_and_utc, get_suppressed_stats


def test_ensure_aware_with_naive_datetime():
    """Test ensure_aware with naive datetime."""
    naive_dt = datetime(2024, 1, 15, 10, 30, 0)
    mailbox_tz = "Europe/Moscow"
    
    # Should localize to mailbox timezone
    aware_dt = ensure_aware(naive_dt, mailbox_tz)
    
    assert aware_dt.tzinfo is not None
    assert aware_dt.year == 2024
    assert aware_dt.month == 1
    assert aware_dt.day == 15
    assert aware_dt.hour == 10
    assert aware_dt.minute == 30


def test_ensure_aware_with_already_aware_datetime():
    """Test ensure_aware with already aware datetime."""
    utc_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    mailbox_tz = "America/Sao_Paulo"
    
    # Should return as-is (not convert)
    result_dt = ensure_aware(utc_dt, mailbox_tz)
    
    assert result_dt.tzinfo is not None
    assert result_dt == utc_dt  # Should be exactly the same


def test_ensure_aware_with_metrics():
    """Test ensure_aware records metric for naive datetime."""
    naive_dt = datetime(2024, 1, 15, 10, 30, 0)
    mailbox_tz = "Europe/Moscow"
    
    # Mock metrics
    mock_metrics = Mock()
    
    # Call with metrics
    ensure_aware(naive_dt, mailbox_tz, metrics=mock_metrics)
    
    # Should have recorded metric
    mock_metrics.record_tz_naive.assert_called_once()


def test_ensure_aware_with_none_raises():
    """Test ensure_aware with None raises ValueError."""
    with pytest.raises(ValueError, match="Cannot ensure timezone awareness for None"):
        ensure_aware(None, "Europe/Moscow")


def test_to_utc_with_aware_datetime():
    """Test to_utc converts aware datetime to UTC."""
    moscow_tz = ZoneInfo("Europe/Moscow")
    moscow_dt = datetime(2024, 1, 15, 15, 0, 0, tzinfo=moscow_tz)
    
    # Convert to UTC
    utc_dt = to_utc(moscow_dt)
    
    assert utc_dt.tzinfo == timezone.utc
    # Moscow is UTC+3, so 15:00 MSK = 12:00 UTC
    assert utc_dt.hour == 12


def test_to_utc_with_naive_raises():
    """Test to_utc with naive datetime raises ValueError."""
    naive_dt = datetime(2024, 1, 15, 10, 30, 0)
    
    with pytest.raises(ValueError, match="Cannot convert naive datetime to UTC"):
        to_utc(naive_dt)


def test_to_utc_with_none_raises():
    """Test to_utc with None raises ValueError."""
    with pytest.raises(ValueError, match="Cannot convert None datetime to UTC"):
        to_utc(None)


def test_ensure_aware_and_utc_convenience():
    """Test ensure_aware_and_utc convenience function."""
    naive_dt = datetime(2024, 1, 15, 10, 30, 0)
    mailbox_tz = "America/Sao_Paulo"
    
    # Should localize and convert to UTC in one step
    utc_dt = ensure_aware_and_utc(naive_dt, mailbox_tz)
    
    assert utc_dt.tzinfo == timezone.utc


def test_ensure_aware_and_utc_with_already_aware():
    """Test ensure_aware_and_utc with already aware datetime."""
    moscow_tz = ZoneInfo("Europe/Moscow")
    moscow_dt = datetime(2024, 1, 15, 15, 0, 0, tzinfo=moscow_tz)
    
    # Should convert to UTC
    utc_dt = ensure_aware_and_utc(moscow_dt, "America/Sao_Paulo")
    
    assert utc_dt.tzinfo == timezone.utc
    assert utc_dt.hour == 12  # Moscow UTC+3, 15:00 MSK = 12:00 UTC


def test_rate_limiting_suppresses_repeated_logs():
    """Test that repeated naive datetime warnings are suppressed."""
    from digest_core.utils.tz import _tz_logger
    
    # Reset rate limiter
    _tz_logger.suppressed_count.clear()
    _tz_logger.last_log_time.clear()
    
    # Set very short cooldown for testing
    _tz_logger.cooldown_seconds = 0.1
    
    # First call should log
    naive_dt1 = datetime(2024, 1, 15, 10, 30, 0)
    ensure_aware(naive_dt1, "Europe/Moscow")
    
    # Second call immediately after should be suppressed
    naive_dt2 = datetime(2024, 1, 15, 11, 30, 0)
    ensure_aware(naive_dt2, "Europe/Moscow")
    
    # Check suppressed count
    assert _tz_logger.suppressed_count["naive_datetime"] >= 1
    
    # Wait for cooldown
    import time
    time.sleep(0.15)
    
    # Third call after cooldown should log again
    naive_dt3 = datetime(2024, 1, 15, 12, 30, 0)
    ensure_aware(naive_dt3, "Europe/Moscow")
    
    # Suppressed count should be reset
    assert _tz_logger.suppressed_count["naive_datetime"] == 0


def test_get_suppressed_stats():
    """Test get_suppressed_stats returns correct data."""
    stats = get_suppressed_stats()
    
    assert "suppressed_counts" in stats
    assert "last_log_times" in stats
    assert isinstance(stats["suppressed_counts"], dict)
    assert isinstance(stats["last_log_times"], dict)


def test_timezone_conversion_correctness():
    """Test timezone conversion maintains correct time."""
    # Create datetime in São Paulo (UTC-3)
    sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
    sp_dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=sao_paulo_tz)
    
    # Convert to UTC
    utc_dt = to_utc(sp_dt)
    
    # São Paulo UTC-3, so 10:00 BRT = 13:00 UTC
    assert utc_dt.hour == 13
    assert utc_dt.tzinfo == timezone.utc
    
    # Create datetime in Moscow (UTC+3)
    moscow_tz = ZoneInfo("Europe/Moscow")
    moscow_dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=moscow_tz)
    
    # Convert to UTC
    utc_dt2 = to_utc(moscow_dt)
    
    # Moscow UTC+3, so 10:00 MSK = 07:00 UTC
    assert utc_dt2.hour == 7
    assert utc_dt2.tzinfo == timezone.utc


