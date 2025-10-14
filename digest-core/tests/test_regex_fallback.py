"""
Tests for fallback to stdlib re when regex module is unavailable.
"""
import sys
import pytest


def test_fallback_when_regex_unavailable(monkeypatch):
    """Test that patterns work when regex module is not available."""
    # Remove regex from sys.modules to simulate it being unavailable
    if 'regex' in sys.modules:
        monkeypatch.setitem(sys.modules, 'regex', None)
    
    # Force reimport of signals module
    import importlib
    from digest_core.evidence import signals
    importlib.reload(signals)
    
    # CYRILLIC_WORD should still exist and work
    assert signals.CYRILLIC_WORD is not None
    
    # Test basic matching
    test_text = "Пришлите, пожалуйста, до 5 декабря"
    matches = signals.CYRILLIC_WORD.findall(test_text)
    
    # Should still find Cyrillic words using stdlib re fallback
    assert len(matches) > 0
    assert any("пришлите" in m.lower() for m in matches)


def test_fallback_date_extraction(monkeypatch):
    """Test that date extraction works with fallback."""
    # Simulate regex unavailable
    if 'regex' in sys.modules:
        monkeypatch.setitem(sys.modules, 'regex', None)
    
    import importlib
    from digest_core.evidence import signals
    importlib.reload(signals)
    
    test_text = "до 15 января, к 3 марта"
    dates = signals.extract_dates(test_text)
    
    # Should extract dates even with fallback
    assert len(dates) > 0


def test_fallback_caps_pattern(monkeypatch):
    """Test that CAPS header pattern works with fallback."""
    if 'regex' in sys.modules:
        monkeypatch.setitem(sys.modules, 'regex', None)
    
    import importlib
    from digest_core.evidence import split
    importlib.reload(split)
    
    # CAPS_HEADER_PATTERN should work
    assert split.CAPS_HEADER_PATTERN is not None
    
    # Test matching
    assert split.CAPS_HEADER_PATTERN.match("ЗАГОЛОВОК: ")
    assert split.CAPS_HEADER_PATTERN.match("HEADER: ")
    assert not split.CAPS_HEADER_PATTERN.match("not a header")

