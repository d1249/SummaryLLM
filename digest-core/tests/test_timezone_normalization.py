"""
Tests for timezone normalization.
"""
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from digest_core.ingest.timezone import ensure_tz_aware, get_current_tz_aware


def test_naive_to_aware():
    """Test naive datetime conversion to aware."""
    naive_dt = datetime(2025, 10, 14, 23, 59, 0)
    aware_dt = ensure_tz_aware(naive_dt, "Europe/Moscow", fail_on_naive=False)
    
    assert aware_dt.tzinfo is not None
    assert aware_dt.tzinfo == ZoneInfo("Europe/Moscow")


def test_naive_fails_in_strict_mode():
    """Test naive datetime fails in strict mode."""
    naive_dt = datetime(2025, 10, 14, 23, 59, 0)
    
    with pytest.raises(ValueError, match="Naive datetime encountered"):
        ensure_tz_aware(naive_dt, "Europe/Moscow", fail_on_naive=True)


def test_aware_conversion():
    """Test aware datetime conversion between timezones."""
    utc_dt = datetime(2025, 10, 14, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
    moscow_dt = ensure_tz_aware(utc_dt, "Europe/Moscow", fail_on_naive=True)
    
    assert moscow_dt.tzinfo == ZoneInfo("Europe/Moscow")
    # UTC+3 for Moscow
    assert moscow_dt.hour == 23  # 20:00 UTC = 23:00 Moscow


def test_get_current_tz_aware():
    """Test get_current_tz_aware returns aware datetime."""
    dt = get_current_tz_aware("America/Sao_Paulo")
    
    assert dt.tzinfo is not None
    assert dt.tzinfo == ZoneInfo("America/Sao_Paulo")

