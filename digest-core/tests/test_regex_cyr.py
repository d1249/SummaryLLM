"""
Tests for safe Cyrillic regex patterns.
Ensures no "bad character range" errors.
"""
import pytest


def test_cyrillic_word_pattern_compiles():
    """Test that CYRILLIC_WORD pattern compiles without errors."""
    from digest_core.evidence import signals
    
    # Should not raise any compilation errors
    assert signals.CYRILLIC_WORD is not None


def test_cyrillic_word_pattern_matches():
    """Test that CYRILLIC_WORD pattern matches Cyrillic text correctly."""
    from digest_core.evidence import signals
    
    test_text = "Согласовать-отчёт до 3 ноября; Ёлки-ёлки, я-же просила."
    
    # Find all Cyrillic words
    matches = signals.CYRILLIC_WORD.findall(test_text)
    
    # Should find Cyrillic words
    assert len(matches) > 0
    
    # Check for specific patterns
    cyrillic_found = [m.lower() for m in matches]
    assert any("соглас" in word for word in cyrillic_found)
    assert any("отчёт" in word or "отчет" in word for word in cyrillic_found)


def test_cyrillic_word_with_hyphen():
    """Test hyphenated Cyrillic words are matched correctly."""
    from digest_core.evidence import signals
    
    test_text = "Ёлки-палки, что-то не работает"
    matches = signals.CYRILLIC_WORD.findall(test_text)
    
    # Should match hyphenated words
    assert len(matches) > 0
    
    # Check that hyphenated words are captured
    text_lower = [m.lower() for m in matches]
    assert any("ёлки" in word or "палки" in word for word in text_lower)


def test_cyrillic_date_pattern_safe():
    """Test that Russian date patterns compile and work safely."""
    from digest_core.evidence import signals
    
    test_text = "до 15 января, к 3 марта, не позднее 20 декабря, до 5 мая"
    
    # Extract dates
    dates = signals.extract_dates(test_text)
    
    # Should find Russian date patterns
    assert len(dates) > 0
    
    # Verify specific patterns
    dates_str = " ".join(dates)
    assert "15" in dates_str or "января" in dates_str or "до" in dates_str


def test_no_bad_character_range_error():
    """
    Test that NO pattern raises "bad character range" error.
    This is the main fix we're testing for.
    """
    from digest_core.evidence import signals
    
    # These texts previously caused issues with [я-й] range
    problematic_texts = [
        "ма[я-й] проблема",  # Contains literal brackets that could confuse
        "январ[ья] феврал[ья]",
        "Пожалуйста согласуйте до 5 декабря",
        "ЗАГОЛОВОК: Важное сообщение"
    ]
    
    for text in problematic_texts:
        # Should not raise any errors
        try:
            matches = signals.CYRILLIC_WORD.findall(text)
            dates = signals.extract_dates(text)
            # If we got here, no exceptions were raised
            assert True
        except Exception as e:
            # Should never get here
            pytest.fail(f"Pattern failed on text '{text}': {e}")


def test_caps_header_pattern_in_split():
    """Test that CAPS header pattern works in evidence split module."""
    from digest_core.evidence.split import CAPS_HEADER_PATTERN
    
    test_lines = [
        "ЗАГОЛОВОК: ",
        "ВАЖНОЕ СООБЩЕНИЕ: ",
        "HEADER: ",
        "not a header",
        "Normal text"
    ]
    
    # Should match CAPS headers with colon
    assert CAPS_HEADER_PATTERN.match(test_lines[0])
    assert CAPS_HEADER_PATTERN.match(test_lines[1])
    assert CAPS_HEADER_PATTERN.match(test_lines[2])
    
    # Should NOT match regular text
    assert not CAPS_HEADER_PATTERN.match(test_lines[3])
    assert not CAPS_HEADER_PATTERN.match(test_lines[4])

