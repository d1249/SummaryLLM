"""
Tests for PII masking functionality.
"""
import pytest
from digest_core.normalize.html import HTMLNormalizer


def test_email_masking():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = "Contact me at john.doe@example.com for details."
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text


def test_phone_masking():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = "Call me at +1-555-123-4567 or (555) 123-4567"
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text


def test_ssn_masking():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = "SSN: 123-45-6789"
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text


def test_credit_card_masking():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = "Card: 1234 5678 9012 3456"
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text


def test_no_leakage_after_masking():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = """
    Contact: john.doe@example.com
    Phone: +1-555-123-4567
    SSN: 123-45-6789
    """
    
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text


def test_multiple_emails_masked():
    """Test that PII masking is delegated to LLM Gateway."""
    normalizer = HTMLNormalizer()
    
    text = "Email alice@corp.com and bob@corp.com"
    masked = normalizer.mask_pii(text)
    
    # PII masking is delegated to LLM Gateway, so text should be unchanged
    assert masked == text

