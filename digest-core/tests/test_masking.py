"""
Tests for PII masking functionality.
"""
import pytest
from digest_core.normalize.html import HTMLNormalizer


def test_email_masking():
    """Test that emails are properly masked."""
    normalizer = HTMLNormalizer()
    
    text = "Contact me at john.doe@example.com for details."
    masked = normalizer.mask_pii(text)
    
    assert "john.doe@example.com" not in masked
    assert "[[REDACT:EMAIL]]" in masked


def test_phone_masking():
    """Test that phone numbers are properly masked."""
    normalizer = HTMLNormalizer()
    
    text = "Call me at +1-555-123-4567 or (555) 123-4567"
    masked = normalizer.mask_pii(text)
    
    assert "555-123-4567" not in masked
    assert "[[REDACT:PHONE]]" in masked


def test_ssn_masking():
    """Test that SSNs are properly masked."""
    normalizer = HTMLNormalizer()
    
    text = "SSN: 123-45-6789"
    masked = normalizer.mask_pii(text)
    
    assert "123-45-6789" not in masked
    assert "[[REDACT:SSN]]" in masked


def test_credit_card_masking():
    """Test that credit card numbers are properly masked."""
    normalizer = HTMLNormalizer()
    
    text = "Card: 1234 5678 9012 3456"
    masked = normalizer.mask_pii(text)
    
    assert "1234 5678 9012 3456" not in masked
    assert "[[REDACT:CARD]]" in masked


def test_no_leakage_after_masking():
    """Test that no PII leaks after masking."""
    normalizer = HTMLNormalizer()
    
    text = """
    Contact: john.doe@example.com
    Phone: +1-555-123-4567
    SSN: 123-45-6789
    """
    
    masked = normalizer.mask_pii(text)
    
    # Verify no raw PII remains
    assert "@example.com" not in masked
    assert "555-123-4567" not in masked
    assert "123-45-6789" not in masked
    
    # Verify redaction markers present
    assert "[[REDACT:EMAIL]]" in masked
    assert "[[REDACT:PHONE]]" in masked
    assert "[[REDACT:SSN]]" in masked


def test_multiple_emails_masked():
    """Test that multiple emails in same text are all masked."""
    normalizer = HTMLNormalizer()
    
    text = "Email alice@corp.com and bob@corp.com"
    masked = normalizer.mask_pii(text)
    
    assert "alice@corp.com" not in masked
    assert "bob@corp.com" not in masked
    assert masked.count("[[REDACT:EMAIL]]") == 2

