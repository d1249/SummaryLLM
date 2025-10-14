"""
Tests for PII masking.
"""
import pytest
from digest_core.privacy.masking import mask_text, assert_no_unmasked_pii, validate_llm_output


def test_mask_email():
    """Test email masking."""
    text = "Пишите на ivan.petrov@example.com для вопросов"
    masked = mask_text(text, enforce=True)
    
    assert "[[REDACT:EMAIL]]" in masked
    assert "ivan.petrov@example.com" not in masked


def test_mask_phone():
    """Test phone masking."""
    text = "Звоните +7 123 456-78-90"
    masked = mask_text(text, enforce=True)
    
    assert "[[REDACT:PHONE]]" in masked


def test_mask_card():
    """Test card number masking."""
    text = "Карта 1234 5678 9012 3456"
    masked = mask_text(text, enforce=True)
    
    # Note: card pattern may have false positives, be careful
    assert "[[REDACT:CARD]]" in masked


def test_assert_no_unmasked_pii_passes():
    """Test assert_no_unmasked_pii passes on clean text."""
    text = "Это чистый текст без PII"
    assert_no_unmasked_pii(text)  # Should not raise


def test_assert_no_unmasked_pii_fails():
    """Test assert_no_unmasked_pii fails on PII."""
    text = "Контакт: test@example.com"
    
    with pytest.raises(ValueError, match="PII leakage detected"):
        assert_no_unmasked_pii(text)


def test_validate_llm_output_clean():
    """Test validate_llm_output passes on clean output."""
    output = '{"summary": "Проверено", "actions": []}'
    validate_llm_output(output, enforce=True)  # Should not raise


def test_validate_llm_output_with_pii():
    """Test validate_llm_output detects PII in output."""
    output = '{"summary": "Написать на admin@test.com", "actions": []}'
    
    with pytest.raises(ValueError, match="PII leakage"):
        validate_llm_output(output, enforce=True)


def test_mask_multiple_pii():
    """Test masking multiple PII types."""
    text = "Контакты: email@test.com, тел +7 999 123-45-67, карта 4111 1111 1111 1111"
    masked = mask_text(text, enforce=True)
    
    assert "[[REDACT:EMAIL]]" in masked
    assert "[[REDACT:PHONE]]" in masked
    assert "email@test.com" not in masked

