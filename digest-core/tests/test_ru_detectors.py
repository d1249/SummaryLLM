"""
Tests for Russian language detectors.
"""
import pytest
from digest_core.evidence.signals import extract_dates, extract_action_verbs


def test_deadline_ru_detection():
    """Test Russian deadline detection."""
    text = "Сделать до 3 ноября отчёт"
    dates = extract_dates(text)
    
    assert len(dates) > 0
    assert any("ноябр" in d.lower() for d in dates)


def test_deadline_ru_various_formats():
    """Test various Russian deadline formats."""
    texts = [
        "до 15 января",
        "к 3 марта",
        "не позднее 20 декабря"
    ]
    
    for text in texts:
        dates = extract_dates(text)
        assert len(dates) > 0, f"No dates found in: {text}"


def test_action_verb_detection():
    """Test Russian action verb detection."""
    text = "Прошу согласовать смету"
    verbs = extract_action_verbs(text)
    
    assert len(verbs) > 0
    assert "прошу" in verbs or "согласовать" in verbs


def test_multiple_action_verbs():
    """Test multiple action verbs detection."""
    text = "Нужно проверить и утвердить документ срочно"
    verbs = extract_action_verbs(text)
    
    # Should find multiple verbs
    assert len(verbs) >= 2
    expected = {"нужно", "проверить", "утвердить", "срочно"}
    assert any(v in verbs for v in expected)


def test_relative_dates_ru():
    """Test Russian relative dates."""
    texts = [
        "Сделать сегодня",
        "Встреча завтра",
        "Отчёт послезавтра"
    ]
    
    for text in texts:
        dates = extract_dates(text)
        assert len(dates) > 0, f"No dates found in: {text}"


def test_no_false_positives():
    """Test no false positives on regular text."""
    text = "Это обычный текст без дедлайнов и действий"
    dates = extract_dates(text)
    verbs = extract_action_verbs(text)
    
    # Should have minimal or no detections
    assert len(dates) == 0
    assert len(verbs) == 0

